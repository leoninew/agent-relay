from typing import Annotated

from fastapi import APIRouter, Query

from agent_relay.dependencies import (
    MemberSessionsDependency,
    RoomQueriesDependency,
    RoomServiceDependency,
)
from agent_relay.room_models import (
    ChangedMember,
    ChangedTopic,
    CreatedMember,
    CreateMember,
    CreateMessage,
    CreateRoom,
    CreateTopic,
    Message,
    MessagePage,
    Room,
    RoomEventPage,
    RoomMetadata,
    RoomSnapshot,
    SessionCandidate,
    UpdateMember,
)

router = APIRouter(prefix="/room", tags=["room"])


@router.get("")
def list_rooms(queries: RoomQueriesDependency) -> list[Room]:
    return queries.rooms()


@router.post("", status_code=201)
def create_room(request: CreateRoom, service: RoomServiceDependency) -> Room:
    return service.create_room(request)


@router.get("/{room_id}")
def get_room(
    room_id: str,
    queries: RoomQueriesDependency,
    topic_id: Annotated[str | None, Query()] = None,
    member_id: Annotated[str | None, Query()] = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> RoomSnapshot:
    return queries.snapshot(
        room_id, topic_id, member_id=member_id, before_seq=before_seq, limit=limit
    )


@router.get("/{room_id}/metadata")
def get_metadata(room_id: str, queries: RoomQueriesDependency) -> RoomMetadata:
    return queries.metadata(room_id)


@router.get("/{room_id}/message")
def list_messages(
    room_id: str,
    queries: RoomQueriesDependency,
    topic_id: Annotated[str | None, Query()] = None,
    member_id: Annotated[str | None, Query()] = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MessagePage:
    return queries.page(
        room_id, topic_id=topic_id, member_id=member_id, before_seq=before_seq, limit=limit
    )


@router.get("/{room_id}/message/{message_id}")
def get_message(room_id: str, message_id: str, queries: RoomQueriesDependency) -> Message:
    return queries.message(room_id, message_id)


@router.get("/{room_id}/event")
def get_events(
    room_id: str,
    queries: RoomQueriesDependency,
    after_event_id: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> RoomEventPage:
    return queries.events(room_id, after_event_id, limit)


@router.post("/{room_id}/message", status_code=201)
def create_message(room_id: str, request: CreateMessage, service: RoomServiceDependency) -> Message:
    return service.post_message(room_id, request)


@router.get("/{room_id}/publication/{publication_id}")
def get_publication(room_id: str, publication_id: str, service: RoomServiceDependency) -> Message:
    return service.publication(room_id, publication_id)


@router.get("/{room_id}/session")
def list_sessions(room_id: str, service: MemberSessionsDependency) -> list[SessionCandidate]:
    return service.candidates(room_id)


@router.post("/{room_id}/member", status_code=201)
def add_member(
    room_id: str, request: CreateMember, service: MemberSessionsDependency
) -> CreatedMember:
    return service.add(room_id, request)


@router.patch("/{room_id}/member/{member_id}")
def update_member(
    room_id: str, member_id: str, request: UpdateMember, service: RoomServiceDependency
) -> ChangedMember:
    return service.update_member(room_id, member_id, request)


@router.post("/{room_id}/topic", status_code=201)
def add_topic(room_id: str, request: CreateTopic, service: RoomServiceDependency) -> ChangedTopic:
    return service.add_topic(room_id, request)


@router.patch("/{room_id}/topic/{topic_id}")
def update_topic(
    room_id: str, topic_id: str, request: CreateTopic, service: RoomServiceDependency
) -> ChangedTopic:
    return service.update_topic(room_id, topic_id, request)


@router.delete("/{room_id}/topic/{topic_id}")
def delete_topic(room_id: str, topic_id: str, service: RoomServiceDependency) -> ChangedTopic:
    return service.delete_topic(room_id, topic_id)


@router.delete("/{room_id}/member/{member_id}")
def delete_member(room_id: str, member_id: str, service: RoomServiceDependency) -> ChangedMember:
    return service.delete_member(room_id, member_id)
