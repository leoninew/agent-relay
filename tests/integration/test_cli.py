import json
import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest
from fastapi.testclient import TestClient
from room_fixtures import DemoRoomService, create_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.members.sessions import SessionInfo
from agent_relay.bootstrap.http import create_app
from agent_relay.infrastructure.persistence.queries import SQLiteRoomQueries as RoomQueries
from agent_relay.infrastructure.persistence.store import SQLiteRoomStore
from agent_relay.interfaces.cli import main
from agent_relay.interfaces.client import HttpResponse, RelayClient

ROOM = "agent-relay"


@pytest.fixture(autouse=True)
def operator_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("AGENT_RELAY_SESSION_ID", raising=False)


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
    service: DemoRoomService
    sessions: FakeSessionDriver
    capsys: pytest.CaptureFixture[str]
    calls: list[tuple[Request, float]] = field(default_factory=list)

    def open(self, request: Request, *, timeout: float) -> HttpResponse:
        self.calls.append((request, timeout))
        body = request.data
        assert body is None or isinstance(body, bytes)
        response = self.client.request(
            request.get_method(),
            request.full_url,
            headers=dict(request.header_items()),
            content=body,
        )
        return BufferedResponse(response.status_code, response.headers, response.content)

    def run(self, *args: str) -> Any:
        assert main(["--base-url", "http://testserver", *args], opener=self.open) == 0
        captured = self.capsys.readouterr()
        assert captured.err == ""
        payload = json.loads(captured.out)
        assert payload["requestId"]
        assert set(payload) == {"requestId", "data"}
        return payload["data"]


@pytest.fixture
def cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Iterator[CliHarness]:
    service = DemoRoomService(create_room_store(tmp_path / "cli.sqlite3"))
    sessions = FakeSessionDriver(
        [
            SessionInfo(
                "candidate", service.snapshot(ROOM).room.project_path, "codex", "候选会话", "idle"
            )
        ]
    )
    # No lifespan/dispatcher: CLI queries only committed records; submissions below are explicit.
    client = TestClient(
        create_app(
            logging.getLogger("tests.cli"),
            store=service.store,
            session_driver=sessions,
            queue_driver=FakeQueueDriver(),
        )
    )
    yield CliHarness(client, service, sessions, capsys)
    client.close()


def test_room_creation_is_shared_by_cli_queries_and_reopened_store(cli: CliHarness) -> None:
    created = cli.run(
        "room", "create", "--name", "文档协作", "--project-path", "D:/work/文档 project"
    )
    room_id = created["id"]
    assert created in cli.run("room", "list")
    snapshot = cli.run("room", "get", room_id)
    assert snapshot["room"] == created
    assert snapshot["messages"] == []
    assert cli.run("room", "metadata", room_id)["room"] == created
    reopened = RoomQueries(SQLiteRoomStore(cli.service.store.path))
    assert reopened.metadata(room_id).room.name == "文档协作"


def test_topic_create_edit_and_delete_share_metadata(cli: CliHarness) -> None:
    topic = cli.run(
        "topic", "create", ROOM, "--name", "接口协作", "--description", "约定 HTTP 行为"
    )
    topic_id = topic["id"]
    assert topic.pop("metadata") == cli.run("room", "metadata", ROOM)
    assert topic in cli.run("topic", "list", ROOM)
    updated = cli.run(
        "topic", "update", ROOM, topic_id, "--name", "接口讨论", "--description", "更新说明"
    )
    assert updated["description"] == "更新说明"
    assert updated.pop("metadata") == cli.run("room", "metadata", ROOM)
    assert updated in cli.run("room", "metadata", ROOM)["topics"]
    deleted = cli.run("topic", "delete", ROOM, topic_id)
    assert deleted["deletedAt"]
    assert deleted.pop("metadata") == cli.run("room", "metadata", ROOM)
    assert deleted in cli.run("topic", "list", ROOM)


def test_member_discovery_binding_edit_and_delete_use_existing_sessions(cli: CliHarness) -> None:
    candidates = cli.run("member", "sessions", ROOM)
    assert [candidate["id"] for candidate in candidates] == ["candidate"]
    created = cli.run(
        "member",
        "add",
        ROOM,
        "--session-id",
        candidates[0]["id"],
        "--name",
        "联调成员",
        "--topic-id",
        "frontend",
        "--topic-id",
        "backend",
    )
    assert created["sessionId"] == "candidate"
    assert created["topicIds"] == ["frontend", "backend"]
    assert cli.sessions.inspected == ["candidate"]
    member_id = created["id"]
    assert cli.run("member", "sessions", ROOM)[0]["memberId"] == member_id
    updated = cli.run(
        "member",
        "update",
        ROOM,
        member_id,
        "--name",
        "接口成员",
        "--topic-id",
        "backend",
    )
    assert updated["sessionId"] == "candidate"
    assert updated["topicIds"] == ["backend"]
    assert updated.pop("metadata") == cli.run("room", "metadata", ROOM)
    assert updated in cli.run("member", "list", ROOM)
    deleted = cli.run("member", "delete", ROOM, member_id)
    assert deleted["deletedAt"]
    assert deleted.pop("metadata") == cli.run("room", "metadata", ROOM)
    assert deleted in cli.run("member", "list", ROOM)


def test_member_can_join_and_clear_subscriptions_without_topic_arguments(cli: CliHarness) -> None:
    created = cli.run("member", "add", ROOM, "--session-id", "candidate", "--name", "直接协作成员")
    assert created["topicIds"] == []
    member_id = created["id"]
    cli.run("member", "update", ROOM, member_id, "--name", "协作成员", "--topic-id", "frontend")
    updated = cli.run("member", "update", ROOM, member_id, "--name", "直接协作成员")
    assert updated["topicIds"] == []
    assert updated["metadata"] == cli.run("room", "metadata", ROOM)
    message = cli.run(
        "message",
        "publish",
        ROOM,
        "--publication-id",
        "cli-zero-subscriptions",
        "--content",
        "直接协作",
        "--mention",
        member_id,
    )
    assert message["recipientIds"] == [member_id]
    assert message["deliveries"][0]["targetSessionId"] == "candidate"


@pytest.mark.parametrize(
    ("targets", "recipients"),
    [
        (["--topic-id", "backend"], ["coordinator", "backend-worker", "test-worker"]),
        (["--mention", "frontend-worker"], ["frontend-worker"]),
        (
            ["--topic-id", "frontend", "--topic-id", "backend", "--mention", "test-worker"],
            ["coordinator", "frontend-worker", "backend-worker", "test-worker"],
        ),
    ],
)
def test_publication_routes_explicit_targets_and_is_recoverable_without_new_delivery(
    cli: CliHarness, targets: list[str], recipients: list[str]
) -> None:
    args = [
        "message",
        "publish",
        ROOM,
        "--publication-id",
        "cli-publication-1",
        "--content",
        "请核对接口与路由",
        "--reply-to",
        "agent-relay-msg-0004",
        *targets,
    ]
    published = cli.run(*args)
    assert published["recipientIds"] == recipients
    assert published["senderId"] == "user"
    assert published["replyToMessageId"] == "agent-relay-msg-0004"
    assert cli.run("message", "publication", ROOM, "cli-publication-1") == published
    assert cli.calls[-1][0].get_method() == "GET"
    assert cli.run(*args) == published
    assert cli.run("message", "get", ROOM, published["id"]) == published
    assert cli.run("room", "metadata", ROOM)["summary"]["totalMessages"] == 7


def test_cli_can_mention_the_user_without_agent_targets(cli: CliHarness) -> None:
    message = cli.run(
        "message",
        "publish",
        ROOM,
        "--publication-id",
        "cli-console-only",
        "--content",
        "流程测试已就绪",
        "--mention",
        "user",
        "--as-member",
        "coordinator",
    )

    assert message["senderId"] == "coordinator"
    assert message["mentionedMemberIds"] == ["user"]
    assert message["recipientIds"] == ["user"]
    assert message["deliveries"] == []


def test_message_history_and_event_cursors_read_same_persistent_facts(cli: CliHarness) -> None:
    snapshot = cli.run(
        "room",
        "get",
        ROOM,
        "--topic-id",
        "frontend",
        "--member-id",
        "coordinator",
        "--limit",
        "1",
    )
    first = snapshot["messages"][0]
    assert first["senderId"] == "coordinator" and "frontend" in first["topicIds"]
    previous = cli.run(
        "message",
        "list",
        ROOM,
        "--topic-id",
        "frontend",
        "--member-id",
        "coordinator",
        "--before-seq",
        str(snapshot["nextBeforeSeq"]),
        "--limit",
        "1",
    )
    assert previous["messages"][0]["seq"] < first["seq"]
    assert previous["hasNewer"]
    topic = cli.run("topic", "create", ROOM, "--name", "事件检查")
    events = cli.run(
        "room", "events", ROOM, "--after-event-id", str(snapshot["eventId"]), "--limit", "1"
    )
    assert events["events"][0]["entityId"] == topic["id"]
    assert events["nextEventId"] > snapshot["eventId"]


def test_delivery_queries_read_current_queued_receipts(cli: CliHarness) -> None:
    message = cli.run(
        "message",
        "publish",
        ROOM,
        "--publication-id",
        "cli-queued",
        "--content",
        "核对回执",
        "--mention",
        "frontend-worker",
        "--mention",
        "backend-worker",
    )
    submitter = DeliveryService(
        cli.service.store,
        FakeQueueDriver(),
        logging.getLogger("tests.cli.queue"),
    )
    while work := cli.service.store.claim_delivery():
        submitter.submit(work)
    rows = cli.run("delivery", "list", ROOM, message["id"])
    assert rows["messageId"] == message["id"]
    assert len(rows["deliveries"]) == 2
    filtered = cli.run(
        "delivery",
        "list",
        ROOM,
        message["id"],
        "--status",
        "queued",
        "--member-id",
        "frontend-worker",
    )
    assert len(filtered["deliveries"]) == 1
    delivery = filtered["deliveries"][0]
    assert delivery["receipt"]["clientUserMessageId"] == delivery["clientMessageId"]
    assert cli.run("delivery", "get", ROOM, message["id"], delivery["id"]) == delivery


def test_queue_list_paginates_and_applies_topic_and_related_member_scope(cli: CliHarness) -> None:
    first = cli.run(
        "queue",
        "list",
        ROOM,
        "--topic-id",
        "backend",
        "--member-id",
        "backend-worker",
        "--limit",
        "2",
    )
    assert [message["seq"] for message in first["messages"]] == [6, 5]
    assert first["totalMessages"] == 4
    assert first["hasMore"] and first["nextBeforeSeq"] == 5
    query = parse_qs(urlsplit(cli.calls[-1][0].full_url).query)
    assert query == {
        "topic_id": ["backend"],
        "member_id": ["backend-worker"],
        "limit": ["2"],
    }

    older = cli.run(
        "queue",
        "list",
        ROOM,
        "--topic-id",
        "backend",
        "--member-id",
        "backend-worker",
        "--before-seq",
        "5",
        "--limit",
        "2",
    )
    assert [message["seq"] for message in older["messages"]] == [4, 3]
    assert not older["hasMore"]


def test_cli_query_keyword_and_clear_preserve_queued_history(cli: CliHarness) -> None:
    room = cli.run(
        "room",
        "get",
        ROOM,
        "--member-id",
        "backend-worker",
        "--keyword",
        "跨话题",
    )
    assert [message["seq"] for message in room["messages"]] == [4, 5]

    message_page = cli.run(
        "message",
        "list",
        ROOM,
        "--topic-id",
        "frontend",
        "--member-id",
        "backend-worker",
        "--keyword",
        "跨话题",
    )
    assert [message["seq"] for message in message_page["messages"]] == [4, 5]
    query = parse_qs(urlsplit(cli.calls[-1][0].full_url).query)
    assert query["keyword"] == ["跨话题"]
    assert query["member_id"] == ["backend-worker"]

    with cli.service.store.write() as connection:
        connection.execute("UPDATE deliveries SET status = 'queued'")
    cleared = cli.run("queue", "clear", ROOM, "--member-id", "frontend-worker")
    assert cleared == {"removedMessages": 5}
    assert cli.calls[-1][0].get_method() == "DELETE"
    assert cli.run("queue", "list", ROOM, "--member-id", "frontend-worker")["messages"] == []
    remaining = cli.run("queue", "list", ROOM, "--member-id", "backend-worker")
    assert [message["seq"] for message in remaining["messages"]] == [3]

    history = cli.run("delivery", "list", ROOM, "agent-relay-msg-0006", "--status", "queued")
    assert len(history["deliveries"]) == 3
    assert all(
        delivery["status"] == "queued" and delivery["deletedAt"]
        for delivery in history["deliveries"]
    )


def test_queue_clear_unknown_transport_result_is_not_retried(
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = 0

    def fail_request(request: Request, *, timeout: float) -> HttpResponse:
        nonlocal calls
        calls += 1
        assert timeout == 10
        assert request.get_method() == "DELETE"
        raise URLError("connection lost")

    assert (
        main(["queue", "clear", ROOM, "--member-id", "frontend-worker"], opener=fail_request) == 5
    )
    output = capsys.readouterr()
    payload = json.loads(output.err)
    assert payload["error"]["code"] == "transport_error"
    assert payload["error"]["outcome"] == "unknown"
    assert calls == 1


def test_queue_clear_codex_flag_is_opt_in(cli: CliHarness) -> None:
    assert cli.run("queue", "clear", ROOM, "--topic-id", "frontend") == {"removedMessages": 3}
    assert parse_qs(urlsplit(cli.calls[-1][0].full_url).query) == {"topic_id": ["frontend"]}
    result = cli.run("queue", "clear", ROOM, "--topic-id", "frontend", "--clear-codex")
    assert result["removedMessages"] == 0
    assert result["codexQueue"]["deleted"] == 0
    assert parse_qs(urlsplit(cli.calls[-1][0].full_url).query) == {
        "topic_id": ["frontend"],
        "clear_codex": ["true"],
    }


def test_clear_codex_rejects_old_relay_response(capsys: pytest.CaptureFixture[str]) -> None:
    def old_service(request: Request, *, timeout: float) -> HttpResponse:
        assert request.get_method() == "DELETE"
        return BufferedResponse(200, {"X-Request-Id": "old-relay"}, b'{"removedMessages": 1}')

    assert main(["queue", "clear", ROOM, "--clear-codex"], opener=old_service) == 4
    payload = json.loads(capsys.readouterr().err)
    assert payload["requestId"] == "old-relay"
    assert payload["error"]["outcome"] == "unknown"


def test_message_query_validates_http_bounds_before_sending(cli: CliHarness) -> None:
    before = len(cli.calls)
    assert main(["message", "list", ROOM, "--before-seq", "0"], opener=cli.open) == 2
    cli.capsys.readouterr()
    assert main(["message", "list", ROOM, "--keyword", "x" * 201], opener=cli.open) == 2
    cli.capsys.readouterr()
    assert len(cli.calls) == before


def test_cli_address_and_timeout_configuration_precedence(
    cli: CliHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENT_RELAY_URL", "http://configured-relay")
    monkeypatch.setenv("AGENT_RELAY_HTTP_TIMEOUT", "3.5")
    assert main(["room", "list"], opener=cli.open) == 0
    assert cli.calls[-1][0].full_url == "http://configured-relay/api/room"
    assert cli.calls[-1][1] == 3.5
    cli.capsys.readouterr()
    assert (
        main(["--base-url", "http://testserver", "--timeout", "7", "room", "list"], opener=cli.open)
        == 0
    )
    assert cli.calls[-1][0].full_url == "http://testserver/api/room"
    assert cli.calls[-1][1] == 7
    cli.capsys.readouterr()


def test_client_encodes_base_path_and_query_values() -> None:
    calls: list[Request] = []

    def open_request(request: Request, *, timeout: float) -> HttpResponse:
        calls.append(request)
        assert timeout == 4
        return BufferedResponse(200, {"x-request-id": "request-encoding"}, b"[]")

    client = RelayClient("http://localhost/relay/", 4, opener=open_request)
    result = client.request("GET", "/api/room", params={"topic_id": "话题 +&", "limit": 10})
    url = urlsplit(calls[0].full_url)
    assert url.path == "/relay/api/room"
    assert parse_qs(url.query) == {"topic_id": ["话题 +&"], "limit": ["10"]}
    assert result.request_id == "request-encoding"


def test_member_publication_preserves_identity_targets_and_lookup(cli: CliHarness) -> None:
    published = cli.run(
        "message",
        "publish",
        ROOM,
        "--as-member",
        "coordinator",
        "--publication-id",
        "member-cli",
        "--content",
        "成员通过 CLI 协作",
        "--topic-id",
        "frontend",
        "--mention",
        "backend-worker",
        "--reply-to",
        "agent-relay-msg-0004",
    )
    assert published["senderId"] == "coordinator"
    assert published["recipientIds"] == ["frontend-worker", "backend-worker", "test-worker"]
    assert published["replyToMessageId"] == "agent-relay-msg-0004"
    assert cli.run("message", "publication", ROOM, "member-cli", "--as-member", "coordinator") == (
        published
    )
    assert cli.calls[-1][0].full_url.endswith("/member/coordinator/publication/member-cli")


def test_member_catalog_context_and_positions_use_the_member_scope(cli: CliHarness) -> None:
    member_id = "frontend-worker"
    catalog = cli.run("member", "catalog", ROOM, member_id)
    assert catalog["memberId"] == member_id
    assert {topic["id"] for topic in catalog["topics"] if topic["subscribed"]} == {
        "frontend",
        "summary",
    }
    initial = cli.run("member", "positions", ROOM, member_id)
    assert all(row["seq"] == 0 for row in initial)
    page = cli.run(
        "member",
        "context",
        ROOM,
        member_id,
        "--topic-id",
        "frontend",
        "--after-seq",
        "0",
        "--limit",
        "2",
    )
    assert page["queryId"] and page["hasMore"]
    assert len(page["messages"]) == 2
    following = cli.run(
        "member",
        "context",
        ROOM,
        member_id,
        "--topic-id",
        "frontend",
        "--after-seq",
        str(page["nextAfterSeq"]),
        "--limit",
        "2",
    )
    assert not following["hasMore"]
    assert following["messages"][0]["seq"] > page["messages"][-1]["seq"]
    current = cli.run("member", "positions", ROOM, member_id)
    assert (
        next(row["seq"] for row in current if row["topicId"] == "frontend")
        == (following["messages"][-1]["seq"])
    )
    single = cli.run("member", "context", ROOM, member_id, "--message-id", "agent-relay-msg-0002")
    assert [row["id"] for row in single["messages"]] == ["agent-relay-msg-0002"]
    recent = cli.run("member", "context", ROOM, member_id, "--limit", "2")
    assert recent["queryId"] and len(recent["messages"]) == 2


def test_cli_uses_current_codex_session_for_member_collaboration(
    cli: CliHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_THREAD_ID", "agent-relay-frontend")
    assert cli.run("member", "catalog", ROOM)["memberId"] == "frontend-worker"
    claim = cli.run(
        "message",
        "publish",
        ROOM,
        "--publication-id",
        "bound-claim",
        "--content",
        "我认领联调",
        "--mention",
        "backend-worker",
    )
    assert claim["senderId"] == "frontend-worker"
    assert cli.run("message", "publication", ROOM, "bound-claim") == claim
    recent = cli.run("member", "context", ROOM, "--limit", "1")
    assert recent["messages"][0]["id"] == claim["id"]
    assert cli.run("member", "positions", ROOM)
