import logging
from pathlib import Path

from fastapi.testclient import TestClient
from room_fixtures import create_room_store
from session_fixtures import FakeQueueDriver, FakeSessionDriver
from starlette.types import Message, Receive, Scope, Send

from agent_relay.api import create_app
from agent_relay.dependencies import RoomQueriesDependency, RoomServiceDependency
from agent_relay.room_models import CreateRoom, CreateTopic, RoomMetadata
from agent_relay.room_queries import RoomQueries
from agent_relay.room_service import RoomService


def test_request_shares_writes_and_commits_before_the_response_starts(tmp_path: Path) -> None:
    store = create_room_store(tmp_path / "request.sqlite3")
    app = create_app(
        logging.getLogger("tests.request-transaction"),
        room_service=RoomService(store),
        session_driver=FakeSessionDriver(),
        queue_driver=FakeQueueDriver(),
    )

    @app.post("/test/collaboration", status_code=201)
    def create_collaboration(
        service: RoomServiceDependency, queries: RoomQueriesDependency
    ) -> RoomMetadata:
        room = service.create_room(CreateRoom(name="Project", project_path="D:/project"))
        service.add_topic(room.id, CreateTopic(name="Implementation"))
        # Other connections cannot see either write until the request is committed.
        assert RoomQueries(store).rooms() == []
        return queries.metadata(room.id)

    committed: list[RoomMetadata] = []

    async def observe_response(scope: Scope, receive: Receive, send: Send) -> None:
        async def observe_start(message: Message) -> None:
            if message["type"] == "http.response.start":
                rooms = RoomQueries(store).rooms()
                assert len(rooms) == 1
                committed.append(RoomQueries(store).metadata(rooms[0].id))
            await send(message)

        await app(scope, receive, observe_start)

    with TestClient(observe_response) as client:
        response = client.post("/test/collaboration")

    assert response.status_code == 201
    metadata = RoomMetadata.model_validate(response.json())
    assert committed == [metadata]
    assert [topic.name for topic in metadata.topics] == ["Implementation"]
    assert metadata.event_id > 0
