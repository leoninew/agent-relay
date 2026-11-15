from datetime import UTC, datetime

from sqlalchemy import select, update

from agent_relay.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from agent_relay.domain.rooms.models import Channel, RoomState
from agent_relay.infrastructure.persistence.models import (
    ChannelRecord,
    DeliveryRecord,
    MemberRecord,
)
from agent_relay.infrastructure.persistence.repositories.rooms import SQLAlchemyRoomRepository


def channel_from_record(record: ChannelRecord) -> Channel:
    return Channel.model_validate({name: getattr(record, name) for name in Channel.model_fields})


class SQLAlchemyChannelRepository(SQLAlchemyRoomRepository):
    def channels(self, room_id: str) -> list[Channel]:
        self.room(room_id)
        return [
            channel_from_record(record)
            for record in self.session.scalars(
                select(ChannelRecord)
                .where(ChannelRecord.room_id == room_id, ChannelRecord.archived_at.is_(None))
                .order_by(
                    ChannelRecord.is_default.desc(), ChannelRecord.created_at, ChannelRecord.id
                )
            )
        ]

    def channel(self, room_id: str, channel_id: str) -> Channel:
        self.room(room_id)
        record = self.session.get(ChannelRecord, (room_id, channel_id))
        if record is None:
            raise RoomNotFoundError("频道不存在", code="channel_not_found")
        return channel_from_record(record)

    def insert(self, channel: Channel, state: RoomState) -> None:
        room = self.room(channel.room_id)
        if (
            self.session.scalar(
                select(ChannelRecord.id).where(
                    ChannelRecord.room_id == channel.room_id,
                    ChannelRecord.name == channel.name,
                    ChannelRecord.archived_at.is_(None),
                )
            )
            is not None
        ):
            raise RoomConflictError("频道名称已存在", code="channel_name_conflict")
        self.session.add(ChannelRecord(**channel.model_dump()))
        self.session.flush()
        user = state.members[0]
        self.session.add(
            MemberRecord(
                room_id=room.id,
                channel_id=channel.id,
                **user.model_dump(exclude={"topic_ids"}),
            )
        )
        self.session.flush()
        scoped = SQLAlchemyRoomRepository(self.session, channel.id)
        scoped.save_resources(
            state,
            RoomState(
                room=room, channel_id=channel.id, working_path=channel.working_path, members=[user]
            ),
        )
        scoped._event(room.id, "room", channel.id)

    def delete(self, room_id: str, channel_id: str) -> None:
        self.room(room_id)
        record = self.session.get(ChannelRecord, (room_id, channel_id))
        if record is None:
            raise RoomNotFoundError("频道不存在", code="channel_not_found")
        if record.is_default:
            raise RoomConflictError("默认频道不能单独删除", code="default_channel_required")
        if record.archived_at is not None:
            return
        if (
            self.session.scalar(
                select(DeliveryRecord.id)
                .where(
                    DeliveryRecord.room_id == room_id,
                    DeliveryRecord.channel_id == channel_id,
                    DeliveryRecord.status == "submitting",
                    DeliveryRecord.deleted_at.is_(None),
                )
                .limit(1)
            )
            is not None
        ):
            raise RoomConflictError("频道操作正在进行", code="channel_operation_busy")
        now = datetime.now(UTC)
        record.archived_at = now
        self.session.execute(
            update(MemberRecord)
            .where(
                MemberRecord.room_id == room_id,
                MemberRecord.channel_id == channel_id,
                MemberRecord.kind == "agent",
                MemberRecord.deleted_at.is_(None),
            )
            .values(deleted_at=now)
        )
        self.session.execute(
            update(DeliveryRecord)
            .where(
                DeliveryRecord.room_id == room_id,
                DeliveryRecord.channel_id == channel_id,
                DeliveryRecord.status == "pending",
                DeliveryRecord.deleted_at.is_(None),
            )
            .values(deleted_at=now, updated_at=now)
        )
