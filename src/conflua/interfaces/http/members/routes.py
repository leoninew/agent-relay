from fastapi import APIRouter

from conflua.application.dto.context import ContextQuery, ContextResult, MemberCatalog
from conflua.application.dto.messages import CreateMessage
from conflua.application.dto.positions import TopicPosition
from conflua.domain.rooms.models import Message
from conflua.interfaces.http.message_output import MessageOutputDependency
from conflua.interfaces.http.persistence import (
    ContextQueriesDependency,
    ContextServiceDependency,
)
from conflua.interfaces.http.rooms.dependencies import MessageServiceDependency

router = APIRouter(
    prefix="/room/{room_id}/channel/{channel_id}/member/{member_id}", tags=["member"]
)


@router.get("/catalog")
def get_catalog(room_id: str, member_id: str, context: ContextQueriesDependency) -> MemberCatalog:
    return context.catalog(room_id, member_id)


@router.get("/position")
def get_positions(
    room_id: str, member_id: str, context: ContextQueriesDependency
) -> list[TopicPosition]:
    return context.positions(room_id, member_id)


@router.post("/context")
def query_context(
    room_id: str,
    member_id: str,
    request: ContextQuery,
    context: ContextServiceDependency,
    output: MessageOutputDependency,
) -> ContextResult:
    return output.page(room_id, context.provide(room_id, member_id, request))


@router.post("/message", status_code=201)
def publish_message(
    room_id: str,
    member_id: str,
    request: CreateMessage,
    service: MessageServiceDependency,
    output: MessageOutputDependency,
) -> Message:
    return output.message(room_id, service.post_message(room_id, request, member_id=member_id))


@router.get("/publication/{publication_id}")
def get_publication(
    room_id: str,
    member_id: str,
    publication_id: str,
    service: MessageServiceDependency,
    output: MessageOutputDependency,
) -> Message:
    return output.message(
        room_id, service.publication(room_id, publication_id, member_id=member_id)
    )
