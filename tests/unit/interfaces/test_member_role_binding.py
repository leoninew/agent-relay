import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

import httpx2
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from conflua.application.dto.members import SessionInfo
from conflua.bootstrap.http import create_app
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.dependencies import create_database
from conflua.infrastructure.persistence.models import MemberRecord

ROLE_PATH = "/api/member-role"


def request(app: FastAPI, method: str, path: str, body: object = None) -> httpx2.Response:
    async def send() -> httpx2.Response:
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body)

    return asyncio.run(send())


def default_channel(app: FastAPI, room: str) -> tuple[str, str]:
    response = request(app, "GET", f"{room}/channel")
    assert response.status_code == 200
    channels = response.json()
    defaults = [channel for channel in channels if channel["isDefault"]]
    assert len(defaults) == 1
    channel_id = defaults[0]["id"]
    return f"{room}/channel/{channel_id}", channel_id


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
    app, database, room, _ = binding_api
    channel, default_id = default_channel(app, room)
    issued = request(app, "POST", f"{room}/channel/issue-id")
    assert issued.status_code == 200
    channel_id = issued.json()["channelId"]
    before = request(app, "GET", f"{room}/channel").json()
    assert all(item["id"] != channel_id for item in before)
    created_channel = request(
        app, "POST", f"{room}/channel", {"name": "Other", "channelId": channel_id}
    )
    assert created_channel.status_code == 201
    assert created_channel.json()["id"] == channel_id
    assert not created_channel.json()["isDefault"]
    other = f"{room}/channel/{channel_id}"
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
    with database.read() as session:
        human_id = session.scalar(
            select(MemberRecord.id).where(
                MemberRecord.room_id == room.rsplit("/", maxsplit=1)[-1],
                MemberRecord.channel_id == default_id,
                MemberRecord.kind == "human",
            )
        )
    assert human_id is not None and message["senderId"] == human_id
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


def test_issued_channel_and_human_role_message_use_discovered_ids(
    binding_api: tuple[FastAPI, Database, str, Mock],
) -> None:
    app, database, room, _ = binding_api
    default_path, default_id = default_channel(app, room)
    issued = request(app, "POST", f"{room}/channel/issue-id")
    assert issued.status_code == 200
    channel_id = issued.json()["channelId"]
    assert [item["id"] for item in request(app, "GET", f"{room}/channel").json()] == [default_id]

    created_channel = request(
        app, "POST", f"{room}/channel", {"name": "Other", "channelId": channel_id}
    )
    assert created_channel.status_code == 201
    other_path = f"{room}/channel/{channel_id}"
    role = request(app, "POST", ROLE_PATH, {"name": "Reviewer", "prompt": "Review"})
    assert role.status_code == 201
    member = request(
        app,
        "POST",
        f"{default_path}/member",
        {"name": "Worker", "sessionId": "worker", "topicIds": [], "roleId": role.json()["id"]},
    )
    assert member.status_code == 201

    (message,) = request(app, "GET", f"{default_path}/message").json()["messages"]
    with database.read() as session:
        human_id = session.scalar(
            select(MemberRecord.id).where(
                MemberRecord.room_id == room.rsplit("/", maxsplit=1)[-1],
                MemberRecord.channel_id == default_id,
                MemberRecord.kind == "human",
            )
        )
        other_human_id = session.scalar(
            select(MemberRecord.id).where(
                MemberRecord.room_id == room.rsplit("/", maxsplit=1)[-1],
                MemberRecord.channel_id == channel_id,
                MemberRecord.kind == "human",
            )
        )
    assert human_id is not None and message["senderId"] == human_id
    assert other_human_id is not None and other_human_id != human_id
    assert message["content"] == "Review"
    assert message["mentionedMemberIds"] == [member.json()["id"]]
    assert message["recipientIds"] == [member.json()["id"]]
    assert request(app, "GET", f"{other_path}/message").json()["messages"] == []


def test_invalid_and_deleted_roles_do_not_bind_members(
    binding_api: tuple[FastAPI, Database, str, Mock],
) -> None:
    app, _, room, driver = binding_api
    channel, _ = default_channel(app, room)
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
    channel, _ = default_channel(app, room)
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
