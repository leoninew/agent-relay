import json
import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest
from fastapi.testclient import TestClient
from support.databases import MemoryDatabases
from support.room_fixtures import DemoRoomService
from support.session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.members.sessions import SessionInfo
from agent_relay.bootstrap.http import create_app
from agent_relay.interfaces.cli import main
from agent_relay.interfaces.client import HttpResponse


@dataclass
class BufferedResponse:
    status: int
    headers: Mapping[str, str]
    content: bytes

    def read(self) -> bytes:
        return self.content

    def close(self) -> None:
        pass


@dataclass
class CliHarness:
    client: TestClient
    capsys: pytest.CaptureFixture[str]

    def open(self, request: Request, *, timeout: float) -> HttpResponse:
        assert request.data is None or isinstance(request.data, bytes)
        response = self.client.request(
            request.get_method(),
            request.full_url,
            headers=dict(request.header_items()),
            content=request.data,
        )
        return BufferedResponse(response.status_code, response.headers, response.content)

    def run(self, *arguments: str) -> Any:
        assert main(["--base-url", "http://testserver", *arguments], opener=self.open) == 0
        captured = self.capsys.readouterr()
        assert captured.err == ""
        payload = json.loads(captured.out)
        assert payload["requestId"]
        return payload["data"]


@pytest.fixture
def cli(
    tmp_path: Path,
    databases: MemoryDatabases,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[CliHarness]:
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("AGENT_RELAY_SESSION_ID", raising=False)
    service = DemoRoomService(databases.store(tmp_path / "cli.sqlite3"))
    driver = FakeSessionDriver(
        [
            SessionInfo(
                "candidate",
                service.snapshot("agent-relay").room.project_path,
                "codex",
                "Original",
                "idle",
            )
        ]
    )
    client = TestClient(
        create_app(
            logging.getLogger("tests.cli"),
            database=service.store.database,
            session_driver=driver,
            queue_driver=FakeQueueDriver(),
        )
    )
    yield CliHarness(client, capsys)
    client.close()


def test_cli_manages_resources_through_http(cli: CliHarness) -> None:
    room = cli.run("room", "create", "--name", "Tool room", "--project-path", "D:/tools")
    assert room in cli.run("room", "list")
    topic = cli.run("topic", "create", "agent-relay", "--name", "Tool topic")
    member = cli.run(
        "member",
        "add",
        "agent-relay",
        "--session-id",
        "candidate",
        "--name",
        "Worker",
        "--topic-id",
        topic["id"],
    )
    assert member["topicIds"] == [topic["id"]]
    assert cli.run("member", "delete", "agent-relay", member["id"])["deletedAt"]
    assert cli.run("topic", "delete", "agent-relay", topic["id"])["deletedAt"]


def test_cli_binds_the_current_session_for_publish_lookup_and_context(
    cli: CliHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_THREAD_ID", "agent-relay-frontend")
    assert cli.run("member", "catalog", "agent-relay")["memberId"] == "frontend-worker"
    message = cli.run(
        "message",
        "publish",
        "agent-relay",
        "--publication-id",
        "claim",
        "--content",
        "I will take this",
        "--mention",
        "backend-worker",
    )
    assert message["senderId"] == "frontend-worker"
    assert cli.run("message", "publication", "agent-relay", "claim") == message
    recent = cli.run("member", "context", "agent-relay", "--limit", "1")
    assert recent["messages"][0]["id"] == message["id"]
