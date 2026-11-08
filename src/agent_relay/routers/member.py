from fastapi import APIRouter

from agent_relay.dependencies import (
    MemberContextDependency,
    RoomServiceDependency,
)
from agent_relay.member_context_models import ContextQuery, ContextResult, MemberCatalog
from agent_relay.room_models import CreateMessage, Message, TopicPosition

router = APIRouter(prefix="/room/{room_id}/member/{member_id}", tags=["member"])


@router.get("/catalog")
def get_catalog(room_id: str, member_id: str, context: MemberContextDependency) -> MemberCatalog:
    return context.catalog(room_id, member_id)


@router.get("/position")
def get_positions(
    room_id: str, member_id: str, context: MemberContextDependency
) -> list[TopicPosition]:
    return context.positions(room_id, member_id)


@router.post("/context")
def query_context(
    room_id: str,
    member_id: str,
    request: ContextQuery,
    context: MemberContextDependency,
) -> ContextResult:
    return context.query(room_id, member_id, request)


@router.post("/message", status_code=201)
def publish_message(
    room_id: str,
    member_id: str,
    request: CreateMessage,
    service: RoomServiceDependency,
) -> Message:
    return service.post_message(room_id, request, member_id=member_id)


@router.get("/publication/{publication_id}")
def get_publication(
    room_id: str,
    member_id: str,
    publication_id: str,
    service: RoomServiceDependency,
) -> Message:
    return service.publication(room_id, publication_id, member_id=member_id)
