import re
from dataclasses import dataclass

from conflua.domain.rooms.markdown import inline_matches

_IMAGE_LINK = re.compile(
    r"!\[(?:\\[^\r\n]|[^\]\\\r\n])*\]"
    r"\((/api/room/(room-[A-Za-z0-9_-]+)/channel/([A-Za-z0-9][A-Za-z0-9_-]*)/image/(img-[a-f0-9]{32}))\)"
)


@dataclass(frozen=True)
class InlineImage:
    start: int
    end: int
    id: str


def inline_images(content: str, room_id: str, channel_id: str) -> list[InlineImage]:
    """Locate destinations in the same managed Markdown format used by the editor."""
    return [
        InlineImage(match.start(1), match.end(1), match[4])
        for match in inline_matches(content, _IMAGE_LINK)
        if match[2] == room_id and match[3] == channel_id
    ]
