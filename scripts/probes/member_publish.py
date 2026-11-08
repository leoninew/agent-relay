"""Verify native skill onboarding, MCP identity and CLI collaboration in an isolated Relay."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Any, cast
from uuid import uuid4

from codex_capabilities import Client
from relay_runtime_integration import running_relay

from agent_relay.client import RelayClient
from agent_relay.config import load_settings
from agent_relay.drivers.codex import _launch_command
from agent_relay.migrations import run_migrations


def run(output: Path) -> None:
    workspace = Path(tempfile.mkdtemp(prefix="agent-relay-skill-"))
    settings = load_settings()
    database = settings.database.model_copy(update={"path": workspace / "relay.sqlite3"})
    run_migrations(database.path)
    settings = settings.model_copy(update={"database": database})
    owned: list[str] = []
    lifecycle: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {
        "observedAt": datetime.now(UTC).isoformat(),
        "workspace": str(workspace),
        "threadIds": owned,
        "lifecycle": lifecycle,
        "scope": "Only newly owned threads, temporary SQLite and an isolated HTTP service",
    }

    control = Client(_launch_command(settings.codex.command), proxy=True)

    def rpc_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        return cast(dict[str, Any], control.call(method, params, settings.codex.rpc_timeout))

    try:
        # Retain the owner connection, like a running Codex client. A detached
        # headless thread may unload before the other member finishes its work.
        control.initialize()
        discovered = rpc_call("skills/list", {"cwds": [str(workspace)], "forceReload": True})
        skills = [
            skill
            for entry in discovered["data"]
            for skill in entry["skills"]
            if skill.get("name") == "agent-relay:agent-relay"
        ]
        assert len(skills) == 1 and skills[0]["enabled"]
        assert skills[0]["pluginId"] == "agent-relay@agent-relay-local"
        evidence["installedSkill"] = skills[0]
        with running_relay(settings, lifecycle) as base_url:
            http = RelayClient(base_url, 15)
            try:
                for name in ("Sender", "Receiver"):
                    started = rpc_call(
                        "thread/start",
                        {
                            "cwd": str(workspace),
                            "approvalPolicy": "never",
                            "sandbox": "danger-full-access",
                            "historyMode": "paginated",
                            "serviceName": "agent-relay-skill-probe",
                            "baseInstructions": (
                                "这是隔离的协作验收。按消息与附带 skill 完成工作，"
                                "仅操作本次临时聊天室。"
                                if name == "Sender"
                                else "这是隔离的协作验收。收到认领和进度通知只需在原会话"
                                "简短确认，不再发布。"
                            ),
                            "config": {
                                "model_reasoning_effort": "low",
                                "mcp_servers": {
                                    "agent-relay": {
                                        "command": sys.executable,
                                        "args": [
                                            "-m",
                                            "agent_relay.cli",
                                            "--base-url",
                                            base_url,
                                            "mcp",
                                        ],
                                    }
                                },
                            },
                        },
                    )
                    thread_id = started["thread"]["id"]
                    owned.append(thread_id)
                    rpc_call(
                        "thread/name/set",
                        {"threadId": thread_id, "name": f"[Relay skill owned] {name}"},
                    )

                room = http.room_create("Skill collaboration", str(workspace)).data
                assert isinstance(room, dict)
                room_id = room["id"]
                topic = http.topic_create(room_id, "Collaboration").data
                assert isinstance(topic, dict)
                members = []
                for name, session_id in zip(("Sender", "Receiver"), owned, strict=True):
                    member = http.member_add(room_id, session_id, name, [topic["id"]]).data
                    assert isinstance(member, dict)
                    members.append(member)

                catalog = rpc_call(
                    "mcpServer/tool/call",
                    {
                        "threadId": owned[0],
                        "server": "agent-relay",
                        "tool": "member_catalog",
                        "arguments": {"room_id": room_id},
                    },
                )
                assert not catalog.get("isError"), catalog
                catalog_payload = json.loads(catalog["content"][0]["text"])
                assert catalog_payload["data"]["memberId"] == members[0]["id"]
                evidence["mcpResolvedCaller"] = True

                environment = {
                    **os.environ,
                    "CODEX_THREAD_ID": owned[0],
                    "AGENT_RELAY_URL": base_url,
                }
                environment.pop("AGENT_RELAY_SESSION_ID", None)
                command = subprocess.run(
                    [sys.executable, "-m", "agent_relay.cli", "member", "catalog", room_id],
                    env=environment,
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                assert command.returncode == 0, command.stderr
                assert json.loads(command.stdout)["data"]["memberId"] == members[0]["id"]
                evidence["cliResolvedCaller"] = True

                claim_id, progress_id = uuid4().hex, uuid4().hex
                expected = {
                    claim_id: "我认领本轮协作验证",
                    progress_id: "聊天室目录已核对，协作验证完成",
                }
                request = http.message_publish(
                    room_id,
                    uuid4().hex,
                    "请认领本轮协作验证，向名为 Receiver 的成员发布“"
                    f"{expected[claim_id]}”（发布编号 {claim_id}）；"
                    "然后核对聊天室目录，再向 Receiver 汇报“"
                    f"{expected[progress_id]}”（发布编号 {progress_id}）。两条均引用当前消息。",
                    mentioned_member_ids=[members[0]["id"]],
                ).data
                assert isinstance(request, dict)
                evidence["consoleMessageId"] = request["id"]
                deadline = monotonic() + 300
                messages = []
                while monotonic() < deadline:
                    page = http.message_list(room_id).data
                    assert isinstance(page, dict)
                    messages = [m for m in page["messages"] if m["publicationId"] in expected]
                    if len(messages) == 2 and all(
                        d["status"] == "received" for m in messages for d in m["deliveries"]
                    ):
                        break
                    sleep(0.25)
                evidence["memberMessages"] = messages
                assert len(messages) == 2, f"See {output}"
                for message in messages:
                    assert message["senderId"] == members[0]["id"]
                    assert message["recipientIds"] == [members[1]["id"]]
                    assert message["replyToMessageId"] == request["id"]
                    assert message["content"] == expected[message["publicationId"]]
                    assert all(d["status"] == "received" for d in message["deliveries"])
                history = rpc_call(
                    "thread/items/list",
                    {"threadId": owned[0], "limit": 100, "sortDirection": "desc"},
                )
                tool_calls = [
                    {"tool": item.get("tool"), "server": item.get("server")}
                    for row in history.get("data", [])
                    for item in [row["item"]]
                    if item.get("type") == "mcpToolCall"
                ]
                evidence["memberToolCalls"] = tool_calls
                assert any(
                    call["tool"] == "message_publish" and call["server"] == "agent-relay"
                    for call in tool_calls
                )
                evidence["passed"] = True
            finally:
                for thread_id in owned:
                    turns = rpc_call("thread/turns/list", {"threadId": thread_id, "limit": 10})
                    for turn in turns.get("data", []):
                        if turn.get("status") == "inProgress":
                            rpc_call(
                                "turn/interrupt", {"threadId": thread_id, "turnId": turn["id"]}
                            )
                    rpc_call("thread/archive", {"threadId": thread_id})
                evidence["ownedThreadsArchived"] = True
    finally:
        control.close()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "passed": True,
                "output": str(output),
                "mcpResolvedCaller": True,
                "cliResolvedCaller": True,
                "memberPublished": 2,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-model", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.output)
