import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from room_fixtures import create_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver

from agent_relay.application.delivery.service import DeliveryService
from agent_relay.application.members.service import MemberSessions
from agent_relay.application.members.sessions import SessionInfo
from agent_relay.application.rooms.contracts import CreateMember, CreateMessage, CreateRoom
from agent_relay.application.rooms.service import RoomService
from agent_relay.bootstrap.http import create_app
from agent_relay.domain.rooms.models import Member
from agent_relay.infrastructure.persistence.context import SQLiteMemberContext as MemberContext
from agent_relay.infrastructure.persistence.queries import SQLiteRoomQueries as RoomQueries


def test_fixed_user_cannot_be_edited_removed_or_bound_to_a_session(tmp_path: Path) -> None:
    store = create_room_store(tmp_path / "user.sqlite3")
    service = RoomService(store)
    room = service.create_room(CreateRoom(name="Project", project_path="D:/project"))
    user = service.snapshot(room.id).members[0]
    assert (user.id, user.kind, user.name, user.session_id) == ("user", "human", "你", None)
    with pytest.raises(ValidationError, match="Human members cannot bind"):
        Member.model_validate({**user.model_dump(), "session_id": "codex-session"})
    with pytest.raises(ValidationError, match="Agent members require"):
        Member.model_validate({**user.model_dump(), "kind": "agent"})
    client = TestClient(
        create_app(
            logging.getLogger("tests.fixed-user"),
            store=store,
            session_driver=FakeSessionDriver(),
            queue_driver=FakeQueueDriver(),
        )
    )
    route = f"/api/room/{room.id}/member/user"
    assert client.patch(route, json={"name": "Changed", "topicIds": []}).status_code == 422
    assert client.delete(route).status_code == 422
    assert service.snapshot(room.id).members == [user]
    client.close()


def test_user_only_publication_never_enters_the_codex_queue(tmp_path: Path) -> None:
    store = create_room_store(tmp_path / "queue.sqlite3")
    service = RoomService(store)
    room = service.create_room(CreateRoom(name="Project", project_path="D:/project"))
    sessions = MemberSessions(
        store,
        FakeSessionDriver([SessionInfo("original", "D:/project", "codex", "Original", "idle")]),
    )
    agent = sessions.add(room.id, CreateMember(name="Agent", session_id="original", topic_ids=[]))
    user = next(member for member in service.snapshot(room.id).members if member.kind == "human")
    catalog = MemberContext(store).catalog(room.id, agent.id)
    assert next(member for member in catalog.members if member.kind == "human").name == "你"
    sessions.record_observations(room.id, [], datetime.now(UTC))
    assert (
        next(member for member in service.snapshot(room.id).members if member.id == "user") == user
    )

    request = CreateMessage(
        publication_id="user-only", content="测试完成", mentioned_member_ids=[user.id]
    )
    published = service.post_message(room.id, request, member_id=agent.id)
    driver = FakeQueueDriver()
    submitter = DeliveryService(store, driver, logging.getLogger("tests.user-queue"))
    while work := store.claim_delivery():
        submitter.submit(work)

    assert published.recipient_ids == [user.id]
    assert published.deliveries == []
    assert driver.calls == []
    assert driver.activations == []
    assert service.post_message(room.id, request, member_id=agent.id) == published
    assert RoomQueries(store).page(room.id, member_id=agent.id).messages == [published]
    with store.read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0] == 0
        assert RoomQueries.joined_members_in(connection, room.id) == {"original": agent.id}


def test_mixed_recipients_queue_only_the_other_agent_once(tmp_path: Path) -> None:
    store = create_room_store(tmp_path / "mixed.sqlite3")
    service = RoomService(store)
    room = service.create_room(CreateRoom(name="Project", project_path="D:/project"))
    sessions = MemberSessions(
        store,
        FakeSessionDriver(
            [
                SessionInfo("sender", "D:/project", "codex", "Sender", "idle"),
                SessionInfo("target", "D:/project", "codex", "Target", "idle"),
            ]
        ),
    )
    sender = sessions.add(room.id, CreateMember(name="Sender", session_id="sender", topic_ids=[]))
    target = sessions.add(room.id, CreateMember(name="Target", session_id="target", topic_ids=[]))
    published = service.post_message(
        room.id,
        CreateMessage(
            publication_id="mixed",
            content="用户与 Agent 同步",
            mentioned_member_ids=["user", sender.id, target.id, "user", target.id],
        ),
        member_id=sender.id,
    )
    driver = FakeQueueDriver()
    submitter = DeliveryService(store, driver, logging.getLogger("tests.mixed-queue"))
    while work := store.claim_delivery():
        submitter.submit(work)

    assert set(published.recipient_ids) == {"user", target.id}
    assert [delivery.target_member_id for delivery in published.deliveries] == [target.id]
    assert [session_id for session_id, _, _ in driver.calls] == ["target"]
