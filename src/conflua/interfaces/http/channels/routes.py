from typing import Annotated

from fastapi import APIRouter, Query

from conflua.application.dto.channels import (
    ArchiveChannel,
    Channel,
    ChannelId,
    ChannelSnapshot,
    CreateChannel,
    IssuedChannelId,
    UpdateChannel,
)
from conflua.interfaces.http.channels.dependencies import (
    ChannelQueriesDependency,
    ChannelServiceDependency,
)
from conflua.interfaces.http.message_output import MessageOutputDependency
from conflua.interfaces.http.rooms.dependencies import RoomQueriesDependency

router = APIRouter(prefix="/room/{room_id}/channel", tags=["channel"])


@router.get("")
def list_channels(room_id: ChannelId, queries: ChannelQueriesDependency) -> list[Channel]:
    return queries.channels(room_id)


@router.post("/issue-id")
def issue_channel_id(room_id: ChannelId, service: ChannelServiceDependency) -> IssuedChannelId:
    return service.issue_id(room_id)


@router.get("/{channel_id}")
def get_channel(
    room_id: ChannelId, channel_id: ChannelId, queries: ChannelQueriesDependency
) -> Channel:
    return queries.channel(room_id, channel_id)


@router.get("/{channel_id}/snapshot")
def get_channel_snapshot(
    room_id: ChannelId,
    channel_id: ChannelId,
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
    room_id: ChannelId, request: CreateChannel, service: ChannelServiceDependency
) -> Channel:
    return service.create(room_id, request)


@router.patch("/{channel_id}")
def update_channel(
    room_id: ChannelId,
    channel_id: ChannelId,
    request: UpdateChannel,
    service: ChannelServiceDependency,
) -> Channel:
    return service.update(room_id, channel_id, request)


@router.delete("/{channel_id}", status_code=204)
def delete_channel(
    room_id: ChannelId, channel_id: ChannelId, service: ChannelServiceDependency
) -> None:
    service.delete(room_id, channel_id)


@router.post("/{channel_id}/archive")
def archive_channel(
    room_id: ChannelId,
    channel_id: ChannelId,
    service: ChannelServiceDependency,
    request: ArchiveChannel | None = None,
) -> Channel:
    return service.archive(room_id, channel_id, name=request.name if request else None)
