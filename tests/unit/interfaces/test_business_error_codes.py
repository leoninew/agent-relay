import asyncio
import json
from types import SimpleNamespace
from typing import Literal
from unittest.mock import Mock

import pytest
from starlette.requests import Request

from agent_relay.application.dto.members import SessionCandidate, SessionInfo
from agent_relay.application.members.sessions import SessionUnavailableError
from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError, RoomNotFoundError
from agent_relay.domain.rooms.rules import normalize_project_path
from agent_relay.interfaces.http.exception_handlers import (
    room_exception_handler,
    session_unavailable_handler,
)


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (RoomNotFoundError("原文", code="room_not_found"), 404, "room_not_found"),
        (RoomConflictError("原文", code="topic_name_conflict"), 409, "topic_name_conflict"),
        (RoomInputError("原文", code="no_recipients"), 422, "no_recipients"),
    ],
)
def test_business_error_retains_message_and_status(
    error: RoomNotFoundError | RoomConflictError | RoomInputError, status: int, code: str
) -> None:
    request = Request({"type": "http", "headers": [(b"x-request-id", b"req1")]})
    response = asyncio.run(room_exception_handler(request, error))
    assert response.status_code == status
    assert json.loads(bytes(response.body)) == {"code": code, "error": "原文", "requestId": "req1"}
    assert str(error) == "原文"


def test_metadata_error_does_not_expose_details() -> None:
    request = Request(
        {
            "type": "http",
            "headers": [],
            "app": SimpleNamespace(state=SimpleNamespace(logger=Mock())),
        }
    )
    error = SessionUnavailableError("private diagnostic", code="session_identity_mismatch")
    response = asyncio.run(session_unavailable_handler(request, error))
    body = json.loads(bytes(response.body))
    assert response.status_code == 503
    assert body["code"] == "session_identity_mismatch"
    assert "private diagnostic" not in str(body)
    assert body["requestId"] == response.headers["X-Request-Id"]


def test_domain_raises_explicit_code() -> None:
    with pytest.raises(RoomInputError) as caught:
        normalize_project_path("relative")
    assert caught.value.code == "project_path_not_absolute"
    assert str(caught.value) == "请输入项目的绝对路径"


@pytest.mark.parametrize(
    ("status", "archived", "code"),
    [
        ("idle", False, None),
        ("active", True, "session_archived"),
        ("error", False, "session_error"),
        ("unavailable", False, "session_not_connected"),
    ],
)
def test_session_reasons(
    status: Literal["idle", "active", "error", "unavailable"],
    archived: bool,
    code: str | None,
) -> None:
    info = SessionInfo(
        id="id", cwd="/project", provider="codex", name="name", status=status, archived=archived
    )
    assert info.unavailable_reason_code == code
    candidate = SessionCandidate(
        id=info.id,
        name=info.name,
        provider=info.provider,
        project_path=info.cwd,
        presence=info.presence,
        observed_at=None,
        archived=info.archived,
        usable=info.usable,
        unavailable_reason=info.unavailable_reason,
        unavailable_reason_code=info.unavailable_reason_code,
    )
    assert candidate.model_dump(by_alias=True)["unavailableReasonCode"] == code
