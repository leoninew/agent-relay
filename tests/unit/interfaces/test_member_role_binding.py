import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

import httpx2
import pytest
from fastapi import FastAPI

from conflua.application.dto.members import SessionInfo
from conflua.bootstrap.http import create_app
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.dependencies import create_database

ROLE_PATH = "/api/member-role"


def request(app: FastAPI, method: str, path: str, body: object = None) -> httpx2.Response:
    async def send() -> httpx2.Response:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body)

    return asyncio.run(send())


@pytest.fixture
def binding_api(tmp_path: Path) -> Iterator[tuple[FastAPI, Database, str, Mock]]:
    database = create_database(tmp_path / "bindings.sqlite3")
    driver = Mock()
    driver.inspect.side_effect = lambda session_id: SessionInfo(
        id=session_id, provider="codex", name=session_id, status="active"
    )
    try:
        app = create_app(
            Mock(),
            database=database,
            static_directory=tmp_path,
            session_driver=driver,
            queue_driver=Mock(),
            capability_driver=Mock(),
            preferences_service=Mock(),
        )
        room = request(app, "POST", "/api/room", {"name": "Test", "workspacePath": str(tmp_path)})
        assert room.status_code == 201
        yield app, database, f"/api/room/{room.json()['id']}", driver
    finally:
        database.close()


def test_add_member_posts_only_to_new_member_and_copies_current_role(
    binding_api: tuple[FastAPI, Database, str, Mock],
) -> None:
    app, _, room, _ = binding_api
    channel = f"{room}/channel/channel-default"
    archive = request(app, "POST", f"{room}/channel", {"name": "Other"})
    assert archive.status_code == 201
    other = f"{room}/channel/{archive.json()['id']}"
    topic = request(app, "POST", f"{channel}/topic", {"name": "Backend"})
    assert topic.status_code == 201
    topic_ids = [topic.json()["id"]]
    existing = {"name": "Existing", "sessionId": "existing", "topicIds": topic_ids}
    assert request(app, "POST", f"{channel}/member", existing).status_code == 201
    assert request(app, "GET", f"{channel}/message").json()["messages"] == []
    role = request(app, "POST", ROLE_PATH, {"name": "Reviewer", "prompt": "First version"})
    assert role.status_code == 201
    role_id = role.json()["id"]
    role_path = f"{ROLE_PATH}/{role_id}"
    assert (
        request(
            app, "PATCH", role_path, {"name": "Reviewer", "prompt": "Current\nversion"}
        ).status_code
        == 200
    )

    member = {"name": "New", "sessionId": "new", "topicIds": topic_ids, "roleId": role_id}
    result = request(app, "POST", f"{channel}/member", member)
    assert result.status_code == 201
    created = result.json()
    assert not {"roleId", "messageId", "deliveryStatus"}.intersection(created)
    assert created["topicIds"] == topic_ids
    assert (
        request(app, "POST", f"{channel}/member", {**member, "name": "Duplicate session"}).json()[
            "code"
        ]
        == "session_already_joined"
    )

    patch = {"name": "Renamed", "topicIds": []}
    member_path = f"{channel}/member/{created['id']}"
    assert request(app, "PATCH", member_path, {**patch, "roleId": role_id}).status_code == 422
    assert request(app, "PATCH", member_path, patch).status_code == 200
    assert request(app, "DELETE", role_path).status_code == 204

    (message,) = request(app, "GET", f"{channel}/message").json()["messages"]
    assert message["senderId"] == "user"
    assert message["content"] == "Current\nversion"
    assert message["topicIds"] == []
    assert message["mentionedMemberIds"] == message["recipientIds"] == [created["id"]]
    (delivery,) = message["deliveries"]
    assert (delivery["targetMemberId"], delivery["targetSessionId"], delivery["status"]) == (
        created["id"],
        "new",
        "pending",
    )
    assert request(app, "GET", f"{other}/message").json()["messages"] == []


def test_invalid_and_deleted_roles_do_not_bind_members(
    binding_api: tuple[FastAPI, Database, str, Mock],
) -> None:
    app, _, room, driver = binding_api
    channel = f"{room}/channel/channel-default"
    member = {"name": "New", "sessionId": "new", "topicIds": []}
    invalid = request(app, "POST", f"{channel}/member", {**member, "roleId": ["role"]})
    assert invalid.status_code == 422
    assert not driver.inspect.called
    role = request(app, "POST", ROLE_PATH, {"name": "Reviewer", "prompt": "Read"}).json()
    assert request(app, "DELETE", f"{ROLE_PATH}/{role['id']}").status_code == 204
    missing = request(app, "POST", f"{channel}/member", {**member, "roleId": role["id"]})
    assert missing.status_code == 404 and missing.json()["code"] == "member_role_not_found"
    created = request(app, "POST", f"{channel}/member", {**member, "roleId": None})
    assert created.status_code == 201
    assert request(app, "GET", f"{channel}/message").json()["messages"] == []


def test_delivery_event_failure_rolls_back_member_message_and_delivery(
    binding_api: tuple[FastAPI, Database, str, Mock],
) -> None:
    app, database, room, driver = binding_api
    channel = f"{room}/channel/channel-default"
    role = request(app, "POST", ROLE_PATH, {"name": "Reviewer", "prompt": "Read"}).json()
    member = {"name": "New", "sessionId": "new", "topicIds": [], "roleId": role["id"]}
    baseline = request(app, "GET", f"{channel}/metadata").json()
    driver.inspect.side_effect = None
    driver.inspect.return_value = SessionInfo(
        id="new", provider="codex", name="Unusable", status="unavailable"
    )
    unavailable = request(app, "POST", f"{channel}/member", member)
    assert unavailable.status_code == 409
    assert unavailable.json()["code"] == "session_not_connected"
    driver.inspect.return_value = SessionInfo(id="new", provider="codex", name="New", status="idle")

    with database.write() as session:
        session.connection().exec_driver_sql(
            "CREATE TRIGGER reject_role_delivery BEFORE INSERT ON room_events "
            "WHEN NEW.kind = 'delivery' BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
        )
    failed = request(app, "POST", f"{channel}/member", member)
    assert failed.status_code == 500 and failed.json()["code"] == "internal_error"
    assert "forced failure" not in failed.text
    assert request(app, "GET", f"{channel}/metadata").json() == baseline
    assert request(app, "GET", f"{channel}/message").json()["messages"] == []
    with database.read() as session:
        assert session.connection().exec_driver_sql("SELECT count(*) FROM deliveries").scalar() == 0
    with database.write() as session:
        session.connection().exec_driver_sql("DROP TRIGGER reject_role_delivery")
    assert request(app, "POST", f"{channel}/member", member).status_code == 201
