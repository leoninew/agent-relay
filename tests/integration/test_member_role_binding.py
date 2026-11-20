import asyncio
from pathlib import Path
from unittest.mock import Mock

import httpx2
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from conflua.application.dto.members import SessionInfo
from conflua.bootstrap.http import create_app
from conflua.infrastructure.persistence.database import Database
from conflua.infrastructure.persistence.models import MemberRecord

pytestmark = pytest.mark.integration

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
def binding_api(tmp_path: Path, database: Database) -> tuple[FastAPI, Database, str]:
    driver = Mock()
    driver.inspect.side_effect = lambda session_id: SessionInfo(
        id=session_id, provider="codex", name=session_id, status="active"
    )
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
    return app, database, f"/api/room/{room.json()['id']}"


def test_add_member_posts_only_to_new_member_and_copies_current_role(
    binding_api: tuple[FastAPI, Database, str],
) -> None:
    app, database, room = binding_api
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
    patch = {"name": "Renamed", "topicIds": []}
    member_path = f"{channel}/member/{created['id']}"
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
    binding_api: tuple[FastAPI, Database, str],
) -> None:
    app, database, room = binding_api
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
