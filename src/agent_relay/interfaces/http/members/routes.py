from fastapi import APIRouter

from agent_relay.application.context.contracts import ContextQuery, ContextResult, MemberCatalog
from agent_relay.application.messages.contracts import CreateMessage
from agent_relay.application.rooms.views import TopicPosition
from agent_relay.domain.rooms.models import Message
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
) -> ContextResult:
    return context.provide(room_id, member_id, request)


@router.post("/message", status_code=201)
def publish_message(
    room_id: str,
    member_id: str,
    request: CreateMessage,
    service: MessageServiceDependency,
) -> Message:
    return service.post_message(room_id, request, member_id=member_id)


@router.get("/publication/{publication_id}")
def get_publication(
    room_id: str,
    member_id: str,
    publication_id: str,
    service: MessageServiceDependency,
) -> Message:
    return service.publication(room_id, publication_id, member_id=member_id)
