"""Probe pending queue survival after an owned app-server process is killed.

Requires --run-model. Only creates/resumes its own temporary thread, disables
external integrations, and uses synthetic dynamic tools. No Relay product data
or existing work sessions are used. Evidence contains only this probe's facts.
"""

from __future__ import annotations

import argparse
import json
import queue
import tempfile
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from codex_capabilities import Client, disabled_integrations, tool_spec


def summarize_history(page: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "turnId": entry["turnId"],
            "type": entry["item"]["type"],
            "id": entry["item"]["id"],
            "clientId": entry["item"].get("clientId"),
            "status": entry["item"].get("status"),
        }
        for entry in page["data"]
    ]


def run(codex: str, output: Path) -> dict[str, Any]:
    workspace = Path(tempfile.mkdtemp(prefix="agent-relay-t01-queue-recovery-"))
    command = [codex, "app-server", *disabled_integrations()]
    client = Client(command)
    thread_id: str | None = None
    result: dict[str, Any] = {
        "observedAt": datetime.now(UTC).isoformat(),
        "workspace": str(workspace),
        "scope": "Owned temporary thread; abrupt process exit; no existing work sessions.",
        "queueAddsAfterRestart": 0,
    }
    try:
        client.initialize()
        started = client.call(
            "thread/start",
            {
                "cwd": str(workspace),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "historyMode": "paginated",
                "serviceName": "agent-relay-t01-probe",
                "baseInstructions": (
                    "Isolated synthetic protocol probe. Never execute commands, read or write "
                    "files, access networks, or spawn agents. Only use room_publish_probe."
                ),
                "dynamicTools": [tool_spec()],
            },
        )
        thread_id = started["thread"]["id"]
        result["ownedThread"] = thread_id
        result["effectiveModel"] = started.get("model")
        client.call(
            "thread/name/set", {"threadId": thread_id, "name": "[T01 queue recovery probe]"}
        )
        lead_client_id = f"t01-recovery-lead-{uuid4()}"
        result["leadReceipt"] = client.call(
            "thread/queue/add",
            {
                "threadId": thread_id,
                "clientUserMessageId": lead_client_id,
                "input": [
                    {
                        "type": "text",
                        "text": (
                            "Call room_publish_probe exactly once with content='recovery gate', "
                            "topicIds=['probe'], mentionedMemberIds=[]. Then reply 'done'."
                        ),
                    }
                ],
            },
        )["queuedSubmission"]
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            try:
                message = client.receive(timeout=min(15, deadline - time.monotonic()))
            except queue.Empty:
                continue
            if message.get("method") == "item/tool/call":
                params = message["params"]
                if params["threadId"] != thread_id or params["tool"] != "room_publish_probe":
                    raise RuntimeError("Unexpected dynamic tool context")
                result["heldCall"] = {
                    key: params[key] for key in ("threadId", "turnId", "callId", "tool")
                }
                break
            if "id" in message and "method" in message:
                client.send(
                    {
                        "id": message["id"],
                        "error": {"code": -32601, "message": "Probe forbids this request"},
                    }
                )
        else:
            raise TimeoutError("No synthetic tool callback received")

        result["statusBeforeKill"] = client.call(
            "thread/read", {"threadId": thread_id, "includeTurns": False}
        )["thread"]["status"]
        receipts = []
        for index in range(2):
            client_id = f"t01-recovery-pending-{uuid4()}"
            receipt = client.call(
                "thread/queue/add",
                {
                    "threadId": thread_id,
                    "clientUserMessageId": client_id,
                    "input": [{"type": "text", "text": f"Reply exactly 'recovered {index}'."}],
                },
            )["queuedSubmission"]
            assert receipt["id"] and receipt["clientUserMessageId"] == client_id
            receipts.append(receipt)
        result["pendingReceipts"] = receipts
        result["queueBeforeKill"] = client.call("thread/queue/list", {"threadId": thread_id})
        assert {row["id"] for row in result["queueBeforeKill"]["data"]} == {
            row["id"] for row in receipts
        }
        client.process.kill()
        client.process.wait(timeout=10)
        with suppress(BrokenPipeError, OSError):
            client.close()

        client = Client(command)
        client.initialize()
        metadata = client.call("thread/read", {"threadId": thread_id, "includeTurns": False})
        assert Path(metadata["thread"]["cwd"]).resolve() == workspace.resolve()
        client.call(
            "thread/resume",
            {
                "threadId": thread_id,
                "excludeTurns": True,
                "approvalPolicy": "never",
                "sandbox": "read-only",
            },
        )
        observations = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            observations.append(
                {
                    "queue": client.call("thread/queue/list", {"threadId": thread_id}),
                    "history": summarize_history(
                        client.call("thread/items/list", {"threadId": thread_id, "limit": 100})
                    ),
                    "status": client.call(
                        "thread/read", {"threadId": thread_id, "includeTurns": False}
                    )["thread"]["status"],
                }
            )
            time.sleep(1)
        result["afterRestart"] = observations
        result["serverRequestsAfterRestart"] = [
            {"method": row["method"], "params": row.get("params")}
            for row in client.requests
            if row["method"] == "item/tool/call"
        ]
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if thread_id is not None and client.process.poll() is None:
            try:
                pending = client.call("thread/queue/list", {"threadId": thread_id})
                for entry in pending["data"]:
                    client.call(
                        "thread/queue/delete",
                        {"threadId": thread_id, "queuedSubmissionId": entry["id"]},
                    )
                client.call("thread/archive", {"threadId": thread_id})
                result["archivedOwnedThread"] = True
            except Exception as exc:
                result["cleanupError"] = str(exc)
        with suppress(BrokenPipeError, OSError):
            client.close()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-model", action="store_true", required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = run(args.codex, args.output)
    print(json.dumps({"output": str(args.output), "error": result.get("error")}))
    if result.get("error") or result.get("cleanupError"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
