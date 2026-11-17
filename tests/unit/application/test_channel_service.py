from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from conflua.application.channels.ports import ChannelData, ChannelStore, WorktreeDriver
from conflua.application.channels.service import ChannelService
from conflua.application.dto.channels import CreateChannel
from conflua.domain.rooms.errors import RoomConflictError, RoomNotFoundError
from conflua.domain.rooms.models import RoomState


@pytest.mark.parametrize("use_worktree", [False, True])
def test_channel_creation_supplies_initial_resources_to_persistence(
    room_state: RoomState, tmp_path: Path, use_worktree: bool
) -> None:
    repository = Mock(spec=ChannelData)
    repository.room.return_value = room_state.room
    repository.channel.side_effect = RoomNotFoundError("频道不存在", code="channel_not_found")
    repository.workspace_exists.return_value = False
    store = MagicMock(spec=ChannelStore)
    store.write.return_value.__enter__.return_value = repository
    driver = Mock(spec=WorktreeDriver)
    driver.inspect.return_value = "current-head"
    service = ChannelService(store, driver, tmp_path)

    channel = service.create(
        room_state.room.id,
        CreateChannel(
            name="API",
            description="Backend work",
            channel_id="channel-api",
            use_worktree=use_worktree,
        ),
    )

    repository.insert.assert_called_once()
    saved_channel, state = repository.insert.call_args.args
    assert saved_channel == channel
    assert state.room == room_state.room
    assert state.channel_id == channel.id
    assert state.working_path == channel.working_path
    assert [member.id for member in state.members] == ["user"]
    assert state.topics
    assert all(topic.created_at == channel.created_at for topic in state.topics)
    if use_worktree:
        assert channel.working_path == (tmp_path / room_state.room.id / channel.id).as_posix()
        driver.inspect.assert_called_once_with(room_state.room.workspace_path)
        driver.create.assert_called_once_with(
            room_state.room.workspace_path, channel.working_path, channel.branch, "current-head"
        )
        driver.verify.assert_called_once_with(
            room_state.room.workspace_path, channel.working_path, channel.branch, "current-head"
        )
    else:
        assert channel.working_path == room_state.room.workspace_path
        assert driver.mock_calls == []


def test_worktree_path_collision_is_rejected_before_git(
    room_state: RoomState, tmp_path: Path
) -> None:
    repository = Mock(spec=ChannelData)
    repository.room.return_value = room_state.room
    repository.channel.side_effect = RoomNotFoundError("频道不存在", code="channel_not_found")
    repository.workspace_exists.return_value = True
    store = MagicMock(spec=ChannelStore)
    store.write.return_value.__enter__.return_value = repository
    driver = Mock(spec=WorktreeDriver)

    with pytest.raises(RoomConflictError) as error:
        ChannelService(store, driver, tmp_path).create(
            room_state.room.id, CreateChannel(name="API", use_worktree=True)
        )
    assert error.value.code == "worktree_path_exists"
    repository.insert.assert_not_called()
    driver.inspect.assert_not_called()


def test_channel_archive_uses_guard_and_status_write_without_git(tmp_path: Path) -> None:
    repository = Mock(spec=ChannelData)
    store = MagicMock(spec=ChannelStore)
    store.write.return_value.__enter__.return_value = repository
    driver = Mock(spec=WorktreeDriver)

    result = ChannelService(store, driver, tmp_path).archive("room", "channel-api")

    assert result is repository.archive.return_value
    store.guard.assert_called_once_with("room")
    repository.archive.assert_called_once_with("room", "channel-api")
    repository.delete.assert_not_called()
    assert driver.mock_calls == []
