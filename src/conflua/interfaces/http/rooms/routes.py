from typing import Annotated

from fastapi import APIRouter, Query, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from conflua.application.dto.images import UploadedImage
from conflua.application.dto.members import (
    ChangedMember,
    CreatedMember,
    CreateMember,
    MemberInterruptResult,
    SessionCandidate,
    UpdateMember,
)
from conflua.application.dto.messages import (
    ClearedMessageQueue,
    CreateMessage,
    MessagePage,
    MessageQueuePage,
    MessageUpdatesQuery,
)
from conflua.application.dto.rooms import (
    ChangedTopic,
    ClearedRoom,
    CreateRoom,
    CreateTopic,
    RoomActivity,
    RoomEventPage,
    RoomMetadata,
    UpdateRoom,
)
from conflua.application.dto.session_models import SessionModelCatalog, UpdateSessionModel
from conflua.application.images.ports import MAX_IMAGE_BYTES
from conflua.domain.rooms.models import Member, Message, Room
from conflua.interfaces.http.members.dependencies import (
    MemberServiceDependency,
    SessionDriverDependency,
)
from conflua.interfaces.http.message_output import MessageOutputDependency
from conflua.interfaces.http.rooms.dependencies import (
    ImageServiceDependency,
    MessageServiceDependency,
    QueueClearServiceDependency,
    QueueDriverDependency,
    RoomClearServiceDependency,
    RoomQueriesDependency,
    RoomServiceDependency,
)

router = APIRouter(prefix="/room", tags=["room"])
channel_router = APIRouter(prefix="/room/{room_id}/channel/{channel_id}", tags=["channel"])


@channel_router.post("/image", status_code=201)
async def upload_image(
    room_id: str, file: UploadFile, service: ImageServiceDependency
) -> UploadedImage:
    try:
        content = await file.read(MAX_IMAGE_BYTES + 1)
        return await run_in_threadpool(service.upload, room_id, content)
    finally:
        await file.close()


@channel_router.get("/image/{image_id}")
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


@channel_router.post("/clear")
def clear_room(
    room_id: str, service: RoomClearServiceDependency, driver: SessionDriverDependency
) -> ClearedRoom:
    return service.clear_room(room_id, driver)


@router.patch("/{room_id}")
def update_room(room_id: str, request: UpdateRoom, service: RoomServiceDependency) -> Room:
    return service.update_room(room_id, request)


@channel_router.get("/metadata")
def get_metadata(room_id: str, queries: RoomQueriesDependency) -> RoomMetadata:
    return queries.metadata(room_id)


@channel_router.get("/message")
def list_messages(
    room_id: str,
    queries: RoomQueriesDependency,
    output: MessageOutputDependency,
    topic_id: Annotated[str | None, Query()] = None,
    member_id: Annotated[str | None, Query()] = None,
    keyword: Annotated[str | None, Query(max_length=200)] = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MessagePage:
    page = queries.page(
        room_id,
        topic_id=topic_id,
        member_id=member_id,
        keyword=keyword,
        before_seq=before_seq,
        limit=limit,
    )
    return output.page(room_id, page)


@channel_router.get("/activity")
def get_activity(room_id: str, queries: RoomQueriesDependency) -> RoomActivity:
    return queries.activity(room_id)


@channel_router.post("/message/updates")
def get_message_updates(
    room_id: str,
    request: MessageUpdatesQuery,
    queries: RoomQueriesDependency,
    output: MessageOutputDependency,
) -> list[Message]:
    return [
        output.message(room_id, message) for message in queries.message_updates(room_id, request)
    ]


@channel_router.get("/queue")
def get_message_queue(
    room_id: str,
    queries: RoomQueriesDependency,
    output: MessageOutputDependency,
    topic_id: Annotated[str | None, Query()] = None,
    member_id: Annotated[str | None, Query()] = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MessageQueuePage:
    page = queries.queue(
        room_id, topic_id=topic_id, member_id=member_id, before_seq=before_seq, limit=limit
    )
    return output.page(room_id, page)


@channel_router.get("/message/{message_id}")
def get_message(
    room_id: str,
    message_id: str,
    queries: RoomQueriesDependency,
    output: MessageOutputDependency,
) -> Message:
    return output.message(room_id, queries.message(room_id, message_id))


@channel_router.delete("/queue", response_model_exclude_none=True)
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


@channel_router.delete("/queue/{message_id}", response_model_exclude_none=True)
def delete_queue_message(
    room_id: str, message_id: str, service: MessageServiceDependency
) -> ClearedMessageQueue:
    return service.delete_queue_message(room_id, message_id)


@channel_router.get("/event")
def get_events(
    room_id: str,
    queries: RoomQueriesDependency,
    after_event_id: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> RoomEventPage:
    return queries.events(room_id, after_event_id, limit)


@channel_router.post("/message", status_code=201)
def create_message(
    room_id: str,
    request: CreateMessage,
    service: MessageServiceDependency,
    output: MessageOutputDependency,
) -> Message:
    return output.message(room_id, service.post_message(room_id, request))


@channel_router.get("/publication/{publication_id}")
def get_publication(
    room_id: str,
    publication_id: str,
    service: MessageServiceDependency,
    output: MessageOutputDependency,
) -> Message:
    return output.message(room_id, service.publication(room_id, publication_id))


@channel_router.get("/session")
def list_sessions(room_id: str, service: MemberServiceDependency) -> list[SessionCandidate]:
    return service.candidates(room_id)


@channel_router.get("/session/{session_id}/member")
def get_session_member(room_id: str, session_id: str, queries: RoomQueriesDependency) -> Member:
    return queries.member_for_session(room_id, session_id)


@channel_router.post("/member", status_code=201)
def add_member(
    room_id: str, request: CreateMember, service: MemberServiceDependency
) -> CreatedMember:
    return service.add(room_id, request)


@channel_router.patch("/member/{member_id}")
def update_member(
    room_id: str, member_id: str, request: UpdateMember, service: MemberServiceDependency
) -> ChangedMember:
    return service.update_member(room_id, member_id, request)


@channel_router.post("/member/{member_id}/interrupt")
def interrupt_member(
    room_id: str, member_id: str, service: MemberServiceDependency
) -> MemberInterruptResult:
    return service.interrupt(room_id, member_id)


@channel_router.get("/member/{member_id}/model")
def get_member_models(
    room_id: str, member_id: str, service: MemberServiceDependency
) -> SessionModelCatalog:
    return service.model_catalog(room_id, member_id)


@channel_router.patch("/member/{member_id}/model")
def update_member_model(
    room_id: str, member_id: str, request: UpdateSessionModel, service: MemberServiceDependency
) -> SessionModelCatalog:
    return service.update_model(room_id, member_id, request)


@channel_router.post("/topic", status_code=201)
def add_topic(room_id: str, request: CreateTopic, service: RoomServiceDependency) -> ChangedTopic:
    return service.add_topic(room_id, request)


@channel_router.patch("/topic/{topic_id}")
def update_topic(
    room_id: str, topic_id: str, request: CreateTopic, service: RoomServiceDependency
) -> ChangedTopic:
    return service.update_topic(room_id, topic_id, request)


@channel_router.delete("/topic/{topic_id}")
def delete_topic(room_id: str, topic_id: str, service: RoomServiceDependency) -> ChangedTopic:
    return service.delete_topic(room_id, topic_id)


@channel_router.delete("/member/{member_id}")
def delete_member(room_id: str, member_id: str, service: MemberServiceDependency) -> ChangedMember:
    return service.delete_member(room_id, member_id)
