"""N5 shared-daemon delivery probe, using only a new temporary test session.

Exercise normal busy queueing, a user interrupt, and starting the existing FIFO
head without adding it again. Persist only synthetic input identities and runtime
facts. Never resume, submit to, or change a user's existing work session.
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

from codex_capabilities import Client, tool_spec

from agent_relay.config import load_settings
from agent_relay.drivers.codex import _launch_command


def snapshot(client: Client, thread_id: str) -> dict[str, Any]:
    metadata = client.call("thread/read", {"threadId": thread_id, "includeTurns": False})
    pending = client.call("thread/queue/list", {"threadId": thread_id, "limit": 100})
    return {
        "observedAt": datetime.now(UTC).isoformat(),
        "status": metadata["thread"]["status"],
        "pending": [
            {key: item.get(key) for key in ("id", "clientUserMessageId")}
            for item in pending["data"]
        ],
    }


def run(output: Path) -> dict[str, Any]:
    workspace = Path(tempfile.mkdtemp(prefix="agent-relay-n5-probe-"))
    client = Client(_launch_command(load_settings().codex.command), proxy=True)
    thread_id: str | None = None
    result: dict[str, Any] = {
        "observedAt": datetime.now(UTC).isoformat(),
        "workspace": str(workspace),
        "scope": "New owned shared-daemon session, synthetic messages only",
        "queueAdds": 0,
        "queueStarts": 0,
    }
    try:
        client.initialize()
        started = client.call(
            "thread/start",
            {
                "cwd": str(workspace),
                "historyMode": "paginated",
                "serviceName": "agent-relay-n5-probe",
                "baseInstructions": (
                    "Synthetic protocol probe. Do not read files, run commands, access networks, "
                    "or use any tool except room_publish_probe when explicitly requested. "
                    "For a new input, follow only its synthetic instruction."
                ),
                "dynamicTools": [tool_spec()],
            },
        )
        thread_id = started["thread"]["id"]
        result["threadId"] = thread_id
        result["initialStatus"] = started["thread"]["status"]
        client.call("thread/name/set", {"threadId": thread_id, "name": "[Relay N5 probe]"})
        lead_id = "n5-lead-" + uuid4().hex
        client.call(
            "thread/queue/add",
            {
                "threadId": thread_id,
                "clientUserMessageId": lead_id,
                "input": [
                    {
                        "type": "text",
                        "text": "Call room_publish_probe once with "
                        "content='synthetic gate', topicIds=['probe'], "
                        "mentionedMemberIds=[]. After it returns reply READY.",
                    }
                ],
            },
        )
        result["queueAdds"] += 1
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                message = client.receive(timeout=min(10, deadline - time.monotonic()))
            except queue.Empty:
                continue
            if message.get("method") == "item/tool/call":
                gate = message["params"]
                assert gate["threadId"] == thread_id
                result["gate"] = {key: gate[key] for key in ("threadId", "turnId", "callId")}
                break
        else:
            raise TimeoutError("Synthetic gate was not reached")

        receipts = []
        for index in range(2):
            client_id = "n5-pending-" + uuid4().hex
            response = client.call(
                "thread/queue/add",
                {
                    "threadId": thread_id,
                    "clientUserMessageId": client_id,
                    "input": [{"type": "text", "text": f"Reply exactly N5_RECEIVED_{index}."}],
                },
            )
            result["queueAdds"] += 1
            receipts.append(
                {key: response["queuedSubmission"][key] for key in ("id", "clientUserMessageId")}
            )
        result["receipts"] = receipts
        result["busy"] = snapshot(client, thread_id)
        client.call("turn/interrupt", {"threadId": thread_id, "turnId": result["gate"]["turnId"]})
        observations = []
        for _ in range(4):
            observations.append(snapshot(client, thread_id))
            time.sleep(0.5)
        result["afterUserInterrupt"] = observations
        state = snapshot(client, thread_id)
        if state["status"]["type"] == "idle" and state["pending"]:
            # Omitting queuedSubmissionId asks the daemon to take the FIFO head;
            # it must not select the newer Relay message and bypass older work.
            response = client.call("thread/queue/start", {"threadId": thread_id})
            result["queueStarts"] += 1
            result["startedTurn"] = {
                key: response["turn"].get(key) for key in ("id", "status", "error")
            }

        expected = {lead_id, *(receipt["clientUserMessageId"] for receipt in receipts)}
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            history = client.call(
                "thread/items/list",
                {"threadId": thread_id, "limit": 100, "sortDirection": "asc"},
            )
            inputs = [
                {
                    "turnId": row["turnId"],
                    "itemId": row["item"]["id"],
                    "clientId": row["item"].get("clientId"),
                    "startedAtMs": row.get("startedAtMs"),
                    "completedAtMs": row.get("completedAtMs"),
                }
                for row in history["data"]
                if row["item"]["type"] == "userMessage"
            ]
            if expected <= {entry["clientId"] for entry in inputs}:
                result["receivedInputs"] = inputs
                result["allInputsReceived"] = True
                break
            time.sleep(0.5)
        else:
            raise TimeoutError("Owned queued inputs did not enter history")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            final = snapshot(client, thread_id)
            if final["status"]["type"] != "active":
                result["final"] = final
                break
            time.sleep(0.5)
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if thread_id is not None:
            with suppress(Exception):
                client.call("thread/archive", {"threadId": thread_id})
                result["archivedOwnedSession"] = True
        client.close()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-model", action="store_true", required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "error": result.get("error"),
                "allInputsReceived": result.get("allInputsReceived"),
            },
            ensure_ascii=False,
        )
    )
    if result.get("error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
