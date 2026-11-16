from typing import cast

from conflua.application.dto.context import ContextMessage, ContextResult
from conflua.application.dto.messages import MessagePage, MessageQueuePage
from conflua.application.dto.rooms import RoomSnapshot
from conflua.application.images.ports import ImageStore
from conflua.domain.rooms.errors import RoomNotFoundError
from conflua.domain.rooms.inline_images import inline_images
from conflua.domain.rooms.models import Message


class ImageMessageText:
    """Project image URLs to existing local files for messages read by agents."""

    def __init__(self, images: ImageStore | None, channel_id: str) -> None:
        self.images = images
        self.channel_id = channel_id

    def text(self, room_id: str, content: str) -> str:
        if self.images is None:
            return content
        start = 0
        parts: list[str] = []
        for reference in inline_images(content, room_id, self.channel_id):
            parts.append(content[start : reference.start])
            try:
                image = self.images.read(room_id, reference.id)
                parts.append(image.path.as_posix())
            except RoomNotFoundError:
                parts.append(content[reference.start : reference.end])
            start = reference.end
        parts.append(content[start:])
        return "".join(parts)

    def message[T: Message | ContextMessage](self, room_id: str, message: T) -> T:
        content = self.text(room_id, message.content)
        if content == message.content:
            return message
        return cast(T, message.model_copy(update={"content": content}))

    def page[T: MessagePage | MessageQueuePage | RoomSnapshot | ContextResult](
        self, room_id: str, page: T
    ) -> T:
        return cast(
            T,
            page.model_copy(
                update={"messages": [self.message(room_id, message) for message in page.messages]}
            ),
        )
