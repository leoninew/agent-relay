from fastapi import APIRouter

from agent_relay.application.dto.context import ContextQuery, ContextResult, MemberCatalog
from agent_relay.application.dto.messages import CreateMessage
from agent_relay.application.dto.positions import TopicPosition
from agent_relay.domain.rooms.models import Message
from agent_relay.interfaces.http.message_output import MessageOutputDependency
from agent_relay.interfaces.http.persistence import (
    ContextQueriesDependency,
    ContextServiceDependency,
)
from agent_relay.interfaces.http.rooms.dependencies import MessageServiceDependency

router = APIRouter(prefix="/room/{room_id}/member/{member_id}", tags=["member"])


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
