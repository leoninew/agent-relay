from typing import Annotated

from fastapi import APIRouter, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from agent_relay.application.dto.images import UploadedImage
from agent_relay.application.dto.members import (
    ChangedMember,
    CreatedMember,
    CreateMember,
    SessionCandidate,
    UpdateMember,
)
from agent_relay.application.dto.messages import (
    ClearedMessageQueue,
    CreateMessage,
    MessagePage,
    MessageQueuePage,
)
from agent_relay.application.dto.rooms import (
    ChangedTopic,
    ClearedRoom,
    CreateRoom,
    CreateTopic,
    RoomEventPage,
    RoomMetadata,
    RoomSnapshot,
    UpdateRoom,
)
from agent_relay.application.images.ports import MAX_IMAGE_BYTES
from agent_relay.domain.rooms.models import Member, Message, Room
from agent_relay.interfaces.http.members.dependencies import (
    MemberServiceDependency,
    SessionDriverDependency,
)
from agent_relay.interfaces.http.rooms.dependencies import (
    ImageServiceDependency,
    MessageServiceDependency,
    QueueClearServiceDependency,
    QueueDriverDependency,
    RoomClearServiceDependency,
    RoomQueriesDependency,
    RoomServiceDependency,
)

router = APIRouter(prefix="/room", tags=["room"])


@router.post("/{room_id}/image", status_code=201)
async def upload_image(
    room_id: str, file: UploadFile, service: ImageServiceDependency
) -> UploadedImage:
    try:
        content = await file.read(MAX_IMAGE_BYTES + 1)
        return await run_in_threadpool(service.upload, room_id, content)
    finally:
        await file.close()


@router.get("/{room_id}/image/{image_id}")
def read_image(room_id: str, image_id: str, service: ImageServiceDependency) -> FileResponse:
    image = service.read(room_id, image_id)
    return FileResponse(
        image.path,
        media_type=image.media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=31536000, immutable",
        },
    )


@router.get("")
def list_rooms(queries: RoomQueriesDependency) -> list[Room]:
    return queries.rooms()


@router.post("", status_code=201)
def create_room(request: CreateRoom, service: RoomServiceDependency) -> Room:
    return service.create_room(request)


@router.delete("/{room_id}", status_code=204)
def delete_room(room_id: str, service: RoomServiceDependency) -> None:
    service.delete_room(room_id)


@router.post("/{room_id}/clear")
def clear_room(
    room_id: str, service: RoomClearServiceDependency, driver: SessionDriverDependency
) -> ClearedRoom:
    return service.clear_room(room_id, driver)


@router.patch("/{room_id}")
def update_room(room_id: str, request: UpdateRoom, service: RoomServiceDependency) -> Room:
    return service.update_room(room_id, request)


@router.get("/{room_id}")
def get_room(
    room_id: str,
    queries: RoomQueriesDependency,
    topic_id: Annotated[str | None, Query()] = None,
    member_id: Annotated[str | None, Query()] = None,
    keyword: Annotated[str | None, Query(max_length=200)] = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> RoomSnapshot:
    return queries.snapshot(
        room_id,
        topic_id,
        member_id=member_id,
        keyword=keyword,
        before_seq=before_seq,
        limit=limit,
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
    keyword: Annotated[str | None, Query(max_length=200)] = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MessagePage:
    return queries.page(
        room_id,
        topic_id=topic_id,
        member_id=member_id,
        keyword=keyword,
        before_seq=before_seq,
        limit=limit,
    )


@router.get("/{room_id}/queue")
def get_message_queue(
    room_id: str,
    queries: RoomQueriesDependency,
    topic_id: Annotated[str | None, Query()] = None,
    member_id: Annotated[str | None, Query()] = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MessageQueuePage:
    return queries.queue(
        room_id, topic_id=topic_id, member_id=member_id, before_seq=before_seq, limit=limit
    )


@router.get("/{room_id}/message/{message_id}")
def get_message(room_id: str, message_id: str, queries: RoomQueriesDependency) -> Message:
    return queries.message(room_id, message_id)


@router.delete("/{room_id}/queue", response_model_exclude_none=True)
def clear_message_queue(
    room_id: str,
    service: MessageServiceDependency,
    queue_clear_service: QueueClearServiceDependency,
    driver: QueueDriverDependency,
    topic_id: Annotated[str | None, Query()] = None,
    member_id: Annotated[str | None, Query()] = None,
    clear_codex: Annotated[bool, Query()] = False,
) -> ClearedMessageQueue:
    if clear_codex:
        return queue_clear_service.clear_queue_with_codex(
            room_id, driver, topic_id=topic_id, member_id=member_id
        )
    return service.clear_queue(room_id, topic_id=topic_id, member_id=member_id)


@router.delete("/{room_id}/queue/{message_id}", response_model_exclude_none=True)
def delete_queue_message(
    room_id: str, message_id: str, service: MessageServiceDependency
) -> ClearedMessageQueue:
    return service.delete_queue_message(room_id, message_id)


@router.get("/{room_id}/event")
def get_events(
    room_id: str,
    queries: RoomQueriesDependency,
    after_event_id: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> RoomEventPage:
    return queries.events(room_id, after_event_id, limit)


@router.post("/{room_id}/message", status_code=201)
def create_message(
    room_id: str, request: CreateMessage, service: MessageServiceDependency
) -> Message:
    return service.post_message(room_id, request)


@router.get("/{room_id}/publication/{publication_id}")
def get_publication(
    room_id: str, publication_id: str, service: MessageServiceDependency
) -> Message:
    return service.publication(room_id, publication_id)


@router.get("/{room_id}/session")
def list_sessions(room_id: str, service: MemberServiceDependency) -> list[SessionCandidate]:
    return service.candidates(room_id)


@router.get("/{room_id}/session/{session_id}/member")
def get_session_member(room_id: str, session_id: str, queries: RoomQueriesDependency) -> Member:
    return queries.member_for_session(room_id, session_id)


@router.post("/{room_id}/member", status_code=201)
def add_member(
    room_id: str, request: CreateMember, service: MemberServiceDependency
) -> CreatedMember:
    return service.add(room_id, request)


@router.patch("/{room_id}/member/{member_id}")
def update_member(
    room_id: str, member_id: str, request: UpdateMember, service: MemberServiceDependency
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
def delete_member(room_id: str, member_id: str, service: MemberServiceDependency) -> ChangedMember:
    return service.delete_member(room_id, member_id)
