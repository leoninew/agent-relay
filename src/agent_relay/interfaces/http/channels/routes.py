from typing import Annotated

from fastapi import APIRouter, Query

from agent_relay.application.dto.channels import (
    Channel,
    ChannelSnapshot,
    CreateChannel,
)
from agent_relay.interfaces.http.channels.dependencies import (
    ChannelQueriesDependency,
    ChannelServiceDependency,
)
from agent_relay.interfaces.http.message_output import MessageOutputDependency
from agent_relay.interfaces.http.rooms.dependencies import RoomQueriesDependency

router = APIRouter(prefix="/room/{room_id}/channel", tags=["channel"])


@router.get("")
def list_channels(room_id: str, queries: ChannelQueriesDependency) -> list[Channel]:
    return queries.channels(room_id)


@router.get("/{channel_id}")
def get_channel(room_id: str, channel_id: str, queries: ChannelQueriesDependency) -> Channel:
    return queries.channel(room_id, channel_id)


@router.get("/{channel_id}/snapshot")
def get_channel_snapshot(
    room_id: str,
    channel_id: str,
    queries: ChannelQueriesDependency,
    rooms: RoomQueriesDependency,
    output: MessageOutputDependency,
    topic_id: Annotated[str | None, Query()] = None,
    member_id: Annotated[str | None, Query()] = None,
    keyword: Annotated[str | None, Query(max_length=200)] = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ChannelSnapshot:
    channel = queries.channel(room_id, channel_id)
    snapshot = rooms.snapshot(
        room_id,
        topic_id,
        member_id=member_id,
        keyword=keyword,
        before_seq=before_seq,
        limit=limit,
    )
    return output.page(
        room_id,
        ChannelSnapshot(
            **snapshot.model_dump(),
            channel_id=channel.id,
            working_path=channel.working_path,
        ),
    )


@router.post("", status_code=201)
def create_channel(
    room_id: str, request: CreateChannel, service: ChannelServiceDependency
) -> Channel:
    return service.create(room_id, request)


@router.delete("/{channel_id}", status_code=204)
def delete_channel(room_id: str, channel_id: str, service: ChannelServiceDependency) -> None:
    service.delete(room_id, channel_id)
