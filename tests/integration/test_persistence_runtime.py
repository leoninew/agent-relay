import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from room_fixtures import RoomTestStore, create_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver
from sqlalchemy import event, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.pool import QueuePool

from agent_relay.application.members.sessions import SessionInfo
from agent_relay.application.rooms.contracts import CreateRoom, CreateTopic
from agent_relay.application.rooms.service import RoomService
from agent_relay.bootstrap.http import create_app
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.models import RoomEventRecord
from agent_relay.interfaces.http.rooms.dependencies import RoomServiceDependency

pytestmark = pytest.mark.integration
LOGGER = logging.getLogger("tests.persistence.runtime")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[RoomTestStore]:
    store = create_room_store(tmp_path / "runtime.sqlite3")
    try:
        yield store
    finally:
        store.database.close()


def assert_released(database: Database) -> None:
    pool = database.engine.pool
    assert isinstance(pool, QueuePool) and pool.checkedout() == 0


@pytest.mark.parametrize("handled", [False, True])
def test_production_request_rolls_back_all_writes_and_events(
    store: RoomTestStore, handled: bool
) -> None:
    app = create_app(
        LOGGER,
        database=store.database,
        session_driver=FakeSessionDriver(),
        queue_driver=FakeQueueDriver(),
    )

    @app.post("/test/failure")
    def fail(service: RoomServiceDependency) -> None:
        room = service.create_room(CreateRoom(name="Rollback", project_path="D:/rollback"))
        service.add_topic(room.id, CreateTopic(name="Rollback topic"))
        if handled:
            raise HTTPException(status_code=409, detail="Rejected")
        raise RuntimeError("Injected failure")

    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.post("/test/failure")
        assert response.status_code == (409 if handled else 500)
        assert store.queries.rooms() == []
        with store.database.read() as session:
            assert session.scalar(select(func.count()).select_from(RoomEventRecord)) == 0
        assert_released(store.database)
    finally:
        client.close()


def test_production_commit_failure_returns_error_without_persisting_success(
    store: RoomTestStore,
) -> None:
    app = create_app(
        LOGGER,
        database=store.database,
        session_driver=FakeSessionDriver(),
        queue_driver=FakeQueueDriver(),
    )

    def fail_commit(connection: Connection) -> None:
        raise RuntimeError("Injected commit failure")

    event.listen(store.database.engine, "commit", fail_commit)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.post("/api/room", json={"name": "Fail", "projectPath": "D:/fail"})
        assert response.status_code == 500
        assert response.json()["code"] == "internal_error"
        assert "Injected" not in response.text
        assert store.queries.rooms() == []
        with store.database.read() as session:
            assert session.scalar(select(func.count()).select_from(RoomEventRecord)) == 0
        assert_released(store.database)
    finally:
        event.remove(store.database.engine, "commit", fail_commit)
        client.close()


def test_member_http_rpc_and_websocket_wait_release_sessions(store: RoomTestStore) -> None:
    room = RoomService(store).create_room(CreateRoom(name="Project", project_path="D:/project"))
    driver = FakeSessionDriver([SessionInfo("candidate", "D:/project", "codex", "Agent", "idle")])

    class InspectingDriver(FakeSessionDriver):
        def list_sessions(self) -> list[SessionInfo]:
            assert_released(store.database)
            assert store.queries.rooms() == [room]
            return driver.list_sessions()

        def inspect(self, thread_id: str) -> SessionInfo:
            assert_released(store.database)
            assert store.queries.rooms() == [room]
            return driver.inspect(thread_id)

    app = create_app(
        LOGGER,
        database=store.database,
        session_driver=InspectingDriver(),
        queue_driver=FakeQueueDriver(),
    )
    client = TestClient(app)
    try:
        route = f"/api/room/{room.id}"
        assert client.get(f"{route}/session").status_code == 200
        response = client.post(
            f"{route}/member", json={"sessionId": "candidate", "name": "Agent", "topicIds": []}
        )
        assert response.status_code == 201
        assert driver.listed == 1 and driver.inspected == ["candidate"]
        with client.websocket_connect(f"{route}/event/stream") as stream:
            assert stream.receive_json()["events"]
            assert_released(store.database)
            changed = client.post(f"{route}/topic", json={"name": "While waiting"})
            assert changed.status_code == 201
            stream.send_text("poll")
            assert stream.receive_json()["events"][0]["entityId"] == changed.json()["id"]
            assert_released(store.database)
    finally:
        client.close()


@pytest.mark.parametrize("borrowed", [False, True])
def test_engine_ownership_and_runner_shutdown_order(
    store: RoomTestStore, monkeypatch: pytest.MonkeyPatch, borrowed: bool
) -> None:
    monkeypatch.setenv("AGENT_RELAY_DATABASE__PATH", str(store.path.parent / "." / store.path.name))
    app = create_app(
        LOGGER,
        database=store.database if borrowed else None,
        session_driver=FakeSessionDriver(),
        queue_driver=FakeQueueDriver(),
    )
    database: Database = app.state.database
    disposed: list[bool] = []

    def observe_dispose(engine: object) -> None:
        assert not app.state.presence_runner.thread.is_alive()
        assert not app.state.delivery_runner.thread.is_alive()
        assert app.state.delivery_runner.lock.file is None
        disposed.append(True)

    event.listen(database.engine, "engine_disposed", observe_dispose)
    try:
        with TestClient(app) as client:
            assert client.get("/api/room").json() == []
            assert database.path == store.path.resolve()
            assert app.state.delivery_runner.lock.path == store.path.with_suffix(
                ".sqlite3.dispatch.lock"
            )
        assert disposed == ([] if borrowed else [True])
        assert_released(database)
        if borrowed:
            assert store.queries.rooms() == []
    finally:
        event.remove(database.engine, "engine_disposed", observe_dispose)


@pytest.mark.parametrize("failure", ["construction", "startup"])
def test_owned_engine_closes_when_app_construction_or_startup_fails(
    store: RoomTestStore, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from agent_relay.bootstrap import http

    disposed: list[bool] = []
    event.listen(store.database.engine, "engine_disposed", lambda engine: disposed.append(True))
    monkeypatch.setattr(http, "create_database", lambda *args, **kwargs: store.database)

    def fail() -> None:
        raise RuntimeError("Injected startup failure")

    if failure == "construction":
        monkeypatch.setattr(http, "mount_static_files", lambda *args, **kwargs: fail())
        with pytest.raises(RuntimeError, match="Injected startup failure"):
            create_app(LOGGER, session_driver=FakeSessionDriver(), queue_driver=FakeQueueDriver())
    else:
        app = create_app(LOGGER, session_driver=FakeSessionDriver(), queue_driver=FakeQueueDriver())
        monkeypatch.setattr(app.state.presence_runner, "start", fail)
        with pytest.raises(RuntimeError, match="Injected startup failure"), TestClient(app):
            pass
        assert not app.state.delivery_runner.thread.is_alive()
        assert app.state.delivery_runner.lock.file is None
    assert disposed == [True]
