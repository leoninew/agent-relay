from datetime import UTC, datetime
from pathlib import Path

from conflua.application.channels.ports import ChannelQueries, ChannelStore, WorktreeDriver
from conflua.application.dto.channels import CreateChannel, IssuedChannelId, UpdateChannel
from conflua.domain.identifiers import new_tsid
from conflua.domain.rooms.errors import RoomConflictError
from conflua.domain.rooms.models import Channel
from conflua.domain.rooms.resources import new_room_state
from conflua.domain.rooms.rules import normalize_workspace_path


class ChannelService(ChannelQueries):
    def __init__(self, store: ChannelStore, git: WorktreeDriver, root: Path) -> None:
        self.store = store
        self.git = git
        self.root = root.resolve()

    def channels(self, room_id: str) -> list[Channel]:
        with self.store.read() as channels:
            return channels.channels(room_id)

    def channel(self, room_id: str, channel_id: str) -> Channel:
        with self.store.read() as channels:
            return channels.channel(room_id, channel_id)

    def issue_id(self, room_id: str) -> IssuedChannelId:
        with self.store.read() as channels:
            channels.room(room_id)
        return IssuedChannelId(channel_id=new_tsid())

    def create(self, room_id: str, request: CreateChannel) -> Channel:
        channel_id = request.channel_id
        with self.store.guard(room_id), self.store.write() as channels:
            room = channels.room(room_id)
            if channels.channel_id_exists(room_id, channel_id):
                raise RoomConflictError("频道编号已被使用", code="channel_id_conflict")
            source = room.workspace_path
            path = normalize_workspace_path(
                str(self.root / room_id / channel_id) if request.use_worktree else source
            )
            branch = f"conflua/{room_id}/{channel_id}" if request.use_worktree else None
            if branch and channels.workspace_exists(path):
                raise RoomConflictError("该目录已被使用", code="worktree_path_exists")
            commit = self.git.inspect(source) if request.use_worktree else None
            if branch:
                self.git.available(source, path, branch)
            created_at = datetime.now(UTC)
            channel = Channel(
                id=channel_id,
                room_id=room_id,
                name=request.name,
                description=request.description,
                working_path=path,
                is_default=False,
                workspace_kind="worktree" if request.use_worktree else "existing",
                branch=branch,
                base_commit=commit,
                created_at=created_at,
            )
            state = new_room_state(
                room,
                created_at,
                channel_id=channel.id,
                working_path=channel.working_path,
            )
            channels.insert(channel, state)
            if branch and commit:
                self.git.create(source, path, branch, commit)
                self.git.verify(source, path, branch, commit)
            return channel

    def update(self, room_id: str, channel_id: str, request: UpdateChannel) -> Channel:
        with self.store.guard(room_id), self.store.write() as channels:
            return channels.update(room_id, channel_id, request.name, request.description)

    def delete(self, room_id: str, channel_id: str) -> None:
        with self.store.guard(room_id), self.store.write() as channels:
            channels.delete(room_id, channel_id)

    def archive(self, room_id: str, channel_id: str, *, name: str | None = None) -> Channel:
        with self.store.guard(room_id), self.store.write() as channels:
            return channels.archive(room_id, channel_id, name=name)
