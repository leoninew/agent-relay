"""Exercise local HTTP/Click delivery and restart with owned, isolated data.

Runs the production application in two successive child processes using the same
temporary SQLite database and the existing shared Codex daemon. Only the newly
created, labelled test session receives synthetic messages. No containers,
development servers, user databases or existing work sessions are changed.
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import asdict
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.request import urlopen
from uuid import uuid4

import click
import uvicorn
from codex_capabilities import Client
from websockets.sync.client import connect

from agent_relay.api import create_app
from agent_relay.client import RelayClient
from agent_relay.config import Settings, load_settings
from agent_relay.delivery_service import SubmitterLock
from agent_relay.drivers.codex import CodexDriver, _launch_command
from agent_relay.migrations import run_migrations


def serve(settings: Settings, listener: socket.socket, control: Connection) -> None:
    """Child process: use normal ASGI startup/shutdown, without OS signal tricks."""
    log_path = settings.database.path.parent / f"relay-runtime-{os.getpid()}.log"
    logging.basicConfig(filename=log_path, encoding="utf-8", level=logging.WARNING, force=True)
    app = create_app(logging.getLogger("relay.t11.http"), settings=settings)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            loop="asyncio:SelectorEventLoop",
            log_config=None,
            access_log=False,
            timeout_graceful_shutdown=10,
        )
    )
    worker = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + 20
        while not server.started:
            if not worker.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Isolated HTTP service did not start")
            time.sleep(0.05)
        control.send({"started": True, "pid": os.getpid()})
        assert control.recv() == "stop"
    finally:
        stopped_at = time.monotonic()
        server.should_exit = True
        worker.join(timeout=settings.codex.rpc_timeout * 2 + 15)
        logging.shutdown()
        control.send(
            {
                "httpThreadStopped": not worker.is_alive(),
                "dispatchThreadStopped": not app.state.delivery_service.thread.is_alive(),
                "shutdownSeconds": time.monotonic() - stopped_at,
                "remainingConnections": len(server.server_state.connections),
                "remainingTasks": len(server.server_state.tasks),
                "logPath": str(log_path),
                "shutdownErrors": [
                    line
                    for line in log_path.read_text(encoding="utf-8").splitlines()
                    if line.startswith("ERROR:")
                ],
            }
        )
        listener.close()
        control.close()


@contextmanager
def running_relay(settings: Settings, lifecycle: list[dict[str, Any]]) -> Iterator[str]:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    isolated = settings.model_copy(
        update={
            "server": settings.server.model_copy(
                update={"host": "127.0.0.1", "port": port, "reload": False}
            )
        }
    )
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=serve, args=(isolated, listener, child), daemon=True)
    process.start()
    child.close()
    listener.close()
    record: dict[str, Any] = {"baseUrl": base_url, "pid": process.pid}
    lifecycle.append(record)
    try:
        assert parent.poll(25), "Isolated HTTP startup timed out"
        started = parent.recv()
        assert started.get("started"), started
        yield base_url
    finally:
        if process.is_alive():
            parent.send("stop")
            assert parent.poll(settings.codex.rpc_timeout * 2 + 20), "HTTP shutdown timed out"
            record.update(parent.recv())
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        parent.close()
        record["exitCode"] = process.exitcode
        assert record.get("httpThreadStopped") and record.get("dispatchThreadStopped"), record
        assert process.exitcode == 0, record
        assert not record["remainingConnections"] and not record["remainingTasks"], record
        assert not record["shutdownErrors"], record
        lock = SubmitterLock(settings.database.path)
        try:
            record["submitterLockReleased"] = lock.acquire()
            assert record["submitterLockReleased"]
        finally:
            lock.release()


def cli(base_url: str, *args: str) -> Any:
    environment = dict(os.environ)
    environment.pop("CODEX_THREAD_ID", None)
    environment.pop("AGENT_RELAY_SESSION_ID", None)
    completed = subprocess.run(
        [sys.executable, "-m", "agent_relay.cli", "--base-url", base_url, *args],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout)
    assert response["requestId"], "CLI must preserve the HTTP request ID"
    return response["data"]


def inputs(driver: CodexDriver, thread_id: str) -> list[dict[str, Any]]:
    """Read only input identities; discard assistant output in the driver."""
    result: list[dict[str, Any]] = []
    cursor = None
    while True:
        page = driver.read_input_page(thread_id, cursor)
        result.extend(asdict(item) for item in page.inputs)
        if page.next_cursor is None:
            return sorted(result, key=lambda row: row["client_message_id"])
        cursor = page.next_cursor


def exercise(settings: Settings, thread_id: str, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    driver = CodexDriver(settings.codex.command, settings.codex.rpc_timeout)
    lifecycle: list[dict[str, Any]] = []
    evidence["services"] = lifecycle
    with running_relay(settings, lifecycle) as base_url:
        room = cli(
            base_url,
            "room",
            "create",
            "--name",
            "T11 isolated",
            "--project-path",
            evidence["workspace"],
        )
        room_id = room["id"]
        evidence["room"] = room
        candidates = cli(base_url, "member", "sessions", room_id)
        candidate = next(row for row in candidates if row["id"] == thread_id)
        assert (
            candidate["usable"] and Path(candidate["projectPath"]) == settings.database.path.parent
        )
        evidence["candidate"] = candidate
        member = cli(
            base_url, "member", "add", room_id, "--session-id", thread_id, "--name", "T11 target"
        )
        member_id = member["id"]
        assert member["topicIds"] == member["metadata"]["members"][0]["topicIds"] == []
        evidence["zeroSubscriptionMember"] = member
        publications = []

        def publish(mode: str, *targets: str) -> None:
            publication_id = "t11-" + uuid4().hex
            args = (
                "message",
                "publish",
                room_id,
                "--publication-id",
                publication_id,
                "--content",
                "T11_" + mode.upper() + "_" + uuid4().hex[:8],
                *targets,
            )
            message = cli(base_url, *args)
            assert message["senderId"] is None and message["recipientIds"] == [member_id]
            assert len(message["deliveries"]) == 1
            assert cli(base_url, *args)["id"] == message["id"]
            publications.append(publication_id)

        publish("zero_subscription_mention", "--mention", member_id)
        topic = cli(base_url, "topic", "create", room_id, "--name", "T11 topic")
        topic_id = topic["id"]
        assert topic["metadata"]["topics"][0]["id"] == topic_id
        subscribed = cli(
            base_url,
            "member",
            "update",
            room_id,
            member_id,
            "--name",
            "T11 subscribed",
            "--topic-id",
            topic_id,
        )
        assert subscribed["metadata"]["members"][0]["topicIds"] == [topic_id]
        publish("topic", "--topic-id", topic_id)
        publish("both", "--topic-id", topic_id, "--mention", member_id)
        deadline = time.monotonic() + 300
        while True:
            messages = [
                cli(base_url, "message", "publication", room_id, key) for key in publications
            ]
            evidence["messages"] = messages
            if all(row["deliveries"][0]["status"] == "received" for row in messages):
                break
            assert time.monotonic() < deadline, "Original input confirmation timed out"
            time.sleep(1)
        evidence["allOriginalInputsConfirmed"] = True
        for message in messages:
            delivery = message["deliveries"][0]
            assert delivery["targetSessionId"] == thread_id
            assert delivery["receipt"]["clientUserMessageId"] == delivery["clientMessageId"]
            assert delivery["receivedItemId"] and delivery["receivedTurnId"]
            assert (
                cli(base_url, "delivery", "get", room_id, message["id"], delivery["id"]) == delivery
            )
        http = RelayClient(base_url, 10)
        context = http.request(
            "POST",
            f"/api/room/{room_id}/member/{member_id}/context",
            body={"topicId": topic_id, "afterSeq": 0, "limit": 20},
        ).data
        assert isinstance(context, dict)
        assert [row["id"] for row in context["messages"]] == [row["id"] for row in messages[1:]]
        assert context["queryId"] and context["positions"][0]["seq"] == messages[-1]["seq"]
        evidence["memberContext"] = context
        latest = cli(base_url, "message", "list", room_id, "--limit", "2")
        earlier = cli(
            base_url,
            "message",
            "list",
            room_id,
            "--before-seq",
            str(latest["nextBeforeSeq"]),
            "--limit",
            "2",
        )
        assert earlier["messages"] + latest["messages"] == messages
        events = cli(base_url, "room", "events", room_id)
        with connect(
            base_url.replace("http:", "ws:") + f"/api/room/{room_id}/event/stream", proxy=None
        ) as stream:
            assert json.loads(stream.recv(timeout=10)) == events
        evidence["events"] = events
        evidence["httpWebSocketCatchupMatches"] = True
        before = cli(base_url, "room", "get", room_id)
        assert before["summary"]["totalMessages"] == before["summary"]["receivedCount"] == 3
        evidence["beforeRestart"] = before
        original_inputs = inputs(driver, thread_id)
        assert len(original_inputs) == 3
        assert {row["client_message_id"] for row in original_inputs} == {
            row["deliveries"][0]["clientMessageId"] for row in messages
        }
        evidence["inputsBeforeRestart"] = original_inputs
        # Fetch the built SPA and its assets over this same real HTTP listener.
        with urlopen(base_url + "/static/", timeout=10) as response:
            assert response.status == 200
            html = response.read().decode("utf-8")
        assert "/static/assets/" in html
        assets = re.findall(r'(?:src|href)="(/static/assets/[^\"]+)"', html)
        assert assets
        for asset in assets:
            with urlopen(base_url + asset, timeout=10) as response:
                assert response.status == 200 and response.read()
        evidence["builtSpaAssets"] = assets
        evidence["builtSpaServed"] = True
    with running_relay(settings, lifecycle) as base_url:
        # Allow the actual restarted dispatcher several cycles to run.
        time.sleep(3)
        after = cli(base_url, "room", "get", room_id)
        assert after == before
        assert cli(base_url, "room", "list") == [room]
        assert cli(base_url, "room", "events", room_id) == events
        assert inputs(driver, thread_id) == original_inputs
        evidence["afterRestart"] = after
        evidence["recordsUnchangedAfterRestart"] = True
        evidence["noDuplicateInputsAfterRestart"] = True
    return messages


def run(output: Path) -> dict[str, Any]:
    workspace = Path(tempfile.mkdtemp(prefix="agent-relay-t11-runtime-"))
    settings = load_settings()
    static_directory = Path("web/dist").resolve()
    if not (static_directory / "index.html").is_file():
        raise FileNotFoundError("Build the existing Web application before this probe")
    isolated = settings.model_copy(
        update={
            "static": settings.static.model_copy(update={"directory": static_directory}),
            "database": settings.database.model_copy(
                update={"path": workspace / "relay.sqlite3", "migrate_on_startup": False}
            ),
        }
    )
    control = Client(_launch_command(settings.codex.command), proxy=True)
    thread_id = None
    evidence: dict[str, Any] = {
        "observedAt": datetime.now(UTC).isoformat(),
        "scope": "Local HTTP, Click CLI, separate Relay processes, owned shared-daemon session",
        "workspace": str(workspace),
        "containerTests": False,
    }
    try:
        control.initialize()
        started = control.call(
            "thread/start",
            {
                "cwd": str(workspace),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "historyMode": "paginated",
                "serviceName": "agent-relay-t11-runtime",
                "baseInstructions": (
                    "You are an isolated synthetic Relay delivery fixture. Do not read or change "
                    "files, execute commands, call tools, access networks, publish messages or "
                    "spawn agents. For each incoming chatroom JSON message, reply with its content "
                    "token in one short sentence. No other actions."
                ),
            },
        )
        thread_id = started["thread"]["id"]
        evidence["threadId"] = thread_id
        assert Path(started["thread"]["cwd"]) == workspace
        control.call(
            "thread/name/set", {"threadId": thread_id, "name": "[Relay T11 runtime probe]"}
        )
        run_migrations(isolated.database.path)
        exercise(isolated, thread_id, evidence)
    except Exception as exc:
        evidence["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if thread_id is not None:
            try:
                # Cleanup is restricted to the exact session created above.
                state = control.call("thread/read", {"threadId": thread_id, "includeTurns": False})
                assert Path(state["thread"]["cwd"]) == workspace
                for message in evidence.get("messages", []):
                    turn_id = message["deliveries"][0].get("receivedTurnId")
                    if turn_id:
                        with suppress(Exception):
                            control.call(
                                "turn/interrupt", {"threadId": thread_id, "turnId": turn_id}
                            )
                control.call("thread/archive", {"threadId": thread_id})
                evidence["archivedOwnedSession"] = True
            except Exception as exc:
                evidence["cleanupError"] = str(exc)
        control.close()
        evidence["ownedProxyExited"] = control.process.poll() is not None
        evidence["completedAt"] = datetime.now(UTC).isoformat()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return evidence


@click.command(help=__doc__)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--run-model", is_flag=True, required=True, help="Allow synthetic session inference")
def main(output: Path, run_model: bool) -> None:
    assert run_model
    result = run(output)
    click.echo(
        json.dumps(
            {
                "output": str(output),
                "error": result.get("error"),
                "received": result.get("allOriginalInputsConfirmed"),
                "restart": result.get("recordsUnchangedAfterRestart"),
                "cleanupError": result.get("cleanupError"),
            },
            ensure_ascii=False,
        )
    )
    if result.get("error") or result.get("cleanupError"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
