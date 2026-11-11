import json
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest

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


def test_queue_clear_unknown_transport_result_is_not_retried(
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = 0

    def fail_request(request: Request, *, timeout: float) -> HttpResponse:
        nonlocal calls
        calls += 1
        assert timeout == 10 and request.get_method() == "DELETE"
        raise URLError("connection lost")

    assert (
        main(["queue", "clear", ROOM, "--member-id", "frontend-worker"], opener=fail_request) == 5
    )
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "transport_error"
    assert payload["error"]["outcome"] == "unknown" and calls == 1


def test_clear_codex_rejects_old_relay_response(capsys: pytest.CaptureFixture[str]) -> None:
    def old_service(request: Request, *, timeout: float) -> HttpResponse:
        assert request.get_method() == "DELETE"
        return BufferedResponse(200, {"X-Request-Id": "old-relay"}, b'{"removedMessages": 1}')

    assert main(["queue", "clear", ROOM, "--clear-codex"], opener=old_service) == 4
    payload = json.loads(capsys.readouterr().err)
    assert payload["requestId"] == "old-relay" and payload["error"]["outcome"] == "unknown"


def test_message_query_validates_http_bounds_before_sending(
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[Request] = []

    def open_request(request: Request, *, timeout: float) -> HttpResponse:
        calls.append(request)
        return BufferedResponse(200, {}, b"[]")

    assert main(["message", "list", ROOM, "--before-seq", "0"], opener=open_request) == 2
    capsys.readouterr()
    assert main(["message", "list", ROOM, "--keyword", "x" * 201], opener=open_request) == 2
    assert not calls


def test_cli_address_and_timeout_configuration_precedence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[Request, float]] = []

    def open_request(request: Request, *, timeout: float) -> HttpResponse:
        calls.append((request, timeout))
        return BufferedResponse(200, {}, b"[]")

    monkeypatch.setenv("AGENT_RELAY_URL", "http://configured-relay")
    monkeypatch.setenv("AGENT_RELAY_HTTP_TIMEOUT", "3.5")
    assert main(["room", "list"], opener=open_request) == 0
    assert calls[-1][0].full_url == "http://configured-relay/api/room" and calls[-1][1] == 3.5
    capsys.readouterr()
    assert (
        main(
            ["--base-url", "http://testserver", "--timeout", "7", "room", "list"],
            opener=open_request,
        )
        == 0
    )
    assert calls[-1][0].full_url == "http://testserver/api/room" and calls[-1][1] == 7


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


@pytest.mark.parametrize(
    ("targets", "topic_ids", "mentions", "publisher"),
    [
        (["--topic-id", "backend"], ["backend"], [], None),
        (["--mention", "frontend-worker"], [], ["frontend-worker"], None),
        (
            ["--topic-id", "frontend", "--topic-id", "backend", "--mention", "test-worker"],
            ["frontend", "backend"],
            ["test-worker"],
            None,
        ),
        (["--mention", "user", "--as-member", "coordinator"], [], ["user"], "coordinator"),
    ],
)
def test_publish_encodes_explicit_targets_and_publisher(
    targets: list[str],
    topic_ids: list[str],
    mentions: list[str],
    publisher: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[Request] = []

    def open_request(request: Request, *, timeout: float) -> HttpResponse:
        calls.append(request)
        return BufferedResponse(201, {"X-Request-Id": "req_publish"}, b'{"id":"saved"}')

    assert (
        main(
            [
                "message",
                "publish",
                ROOM,
                "--publication-id",
                "publication",
                "--content",
                "请核对接口与路由",
                "--reply-to",
                "original",
                *targets,
            ],
            opener=open_request,
        )
        == 0
    )
    assert len(calls) == 1 and calls[0].get_method() == "POST"
    suffix = f"/member/{publisher}" if publisher is not None else ""
    assert urlsplit(calls[0].full_url).path == f"/api/room/{ROOM}{suffix}/message"
    assert isinstance(calls[0].data, bytes)
    assert json.loads(calls[0].data) == {
        "publicationId": "publication",
        "content": "请核对接口与路由",
        "topicIds": topic_ids,
        "mentionedMemberIds": mentions,
        "replyToMessageId": "original",
    }
    assert json.loads(capsys.readouterr().out) == {
        "requestId": "req_publish",
        "data": {"id": "saved"},
    }


def test_queue_clear_codex_flag_is_opt_in(capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[Request] = []

    def open_request(request: Request, *, timeout: float) -> HttpResponse:
        calls.append(request)
        return BufferedResponse(200, {}, b'{"removedMessages":0,"codexQueue":{"deleted":0}}')

    for options in ([], ["--clear-codex"]):
        assert (
            main(["queue", "clear", ROOM, "--topic-id", "frontend", *options], opener=open_request)
            == 0
        )
        capsys.readouterr()
    assert all(request.get_method() == "DELETE" for request in calls)
    assert parse_qs(urlsplit(calls[0].full_url).query) == {"topic_id": ["frontend"]}
    assert parse_qs(urlsplit(calls[1].full_url).query) == {
        "topic_id": ["frontend"],
        "clear_codex": ["true"],
    }


@pytest.mark.parametrize("action", ["add", "update"])
def test_member_commands_send_empty_subscriptions_when_topics_are_omitted(
    action: str, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[Request] = []

    def open_request(request: Request, *, timeout: float) -> HttpResponse:
        calls.append(request)
        return BufferedResponse(200, {}, b'{"id":"member"}')

    identity = ["--session-id", "candidate"] if action == "add" else ["member"]
    assert main(["member", action, ROOM, *identity, "--name", "协作成员"], opener=open_request) == 0
    capsys.readouterr()
    assert len(calls) == 1
    assert calls[0].get_method() == ("POST" if action == "add" else "PATCH")
    assert isinstance(calls[0].data, bytes)
    payload = json.loads(calls[0].data)
    assert payload["name"] == "协作成员" and payload["topicIds"] == []
    if action == "add":
        assert payload["sessionId"] == "candidate"
