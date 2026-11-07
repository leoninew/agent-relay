from typing import Annotated

from fastapi import APIRouter, Query

from agent_relay.dependencies import MemberSessionsDependency, RoomServiceDependency
from agent_relay.room_models import (
    CreatedMember,
    CreateMember,
    CreateMessage,
    CreateRoom,
    CreateTopic,
    Member,
    Message,
    Room,
    RoomSnapshot,
    SessionCandidate,
    Topic,
    UpdateMember,
)

router = APIRouter(prefix="/room", tags=["room"])


@router.get("")
def list_rooms(service: RoomServiceDependency) -> list[Room]:
    return service.list_rooms()


@router.post("", status_code=201)
def create_room(request: CreateRoom, service: RoomServiceDependency) -> Room:
    return service.create_room(request)


@router.get("/{room_id}")
def get_room(
    room_id: str,
    service: RoomServiceDependency,
    topic_id: Annotated[str | None, Query()] = None,
) -> RoomSnapshot:
    return service.snapshot(room_id, topic_id)


@router.post("/{room_id}/message", status_code=201)
def create_message(room_id: str, request: CreateMessage, service: RoomServiceDependency) -> Message:
    return service.post_message(room_id, request)


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
) -> Member:
    return service.update_member(room_id, member_id, request)


@router.post("/{room_id}/topic", status_code=201)
def add_topic(room_id: str, request: CreateTopic, service: RoomServiceDependency) -> Topic:
    return service.add_topic(room_id, request)


@router.patch("/{room_id}/topic/{topic_id}")
def update_topic(
    room_id: str, topic_id: str, request: CreateTopic, service: RoomServiceDependency
) -> Topic:
    return service.update_topic(room_id, topic_id, request)


@router.delete("/{room_id}/topic/{topic_id}")
def delete_topic(room_id: str, topic_id: str, service: RoomServiceDependency) -> Topic:
    return service.delete_topic(room_id, topic_id)


@router.delete("/{room_id}/member/{member_id}")
def delete_member(room_id: str, member_id: str, service: RoomServiceDependency) -> Member:
    return service.delete_member(room_id, member_id)
