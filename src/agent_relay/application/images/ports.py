from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

MAX_IMAGE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class StoredImage:
    id: str
    path: Path
    media_type: str
    size: int


class ImageStore(Protocol):
    def save(self, room_id: str, content: bytes) -> StoredImage: ...
    def read(self, room_id: str, image_id: str) -> StoredImage: ...
