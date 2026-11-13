import re
import warnings
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from agent_relay.application.images.ports import MAX_IMAGE_BYTES, StoredImage
from agent_relay.domain.rooms.errors import RoomInputError, RoomNotFoundError

_FORMATS = {
    "PNG": ("png", "image/png"),
    "JPEG": ("jpg", "image/jpeg"),
    "WEBP": ("webp", "image/webp"),
}


class FileImageStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def _directory(self, room_id: str) -> Path:
        if not re.fullmatch(r"room-[A-Za-z0-9_-]+", room_id):
            raise RoomNotFoundError("Room not found")
        return self.root / room_id

    def save(self, room_id: str, content: bytes) -> StoredImage:
        if not content:
            raise RoomInputError("Empty image content", code="image_invalid")
        if len(content) > MAX_IMAGE_BYTES:
            raise RoomInputError("Image exceeds the size limit", code="image_too_large")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    image_format = image.format or ""
                    if image_format not in _FORMATS or getattr(image, "is_animated", False):
                        raise RoomInputError("Use a PNG, JPEG or WebP image", code="image_invalid")
                    image.load()
        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise RoomInputError("Invalid image content", code="image_invalid") from exc
        extension, media_type = _FORMATS[image_format]
        image_id = f"img-{uuid4().hex}"
        directory = self._directory(room_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{image_id}.{extension}"
        with path.open("xb") as output:
            output.write(content)
        return StoredImage(image_id, path, media_type, len(content))

    def read(self, room_id: str, image_id: str) -> StoredImage:
        directory = self._directory(room_id)
        if re.fullmatch(r"img-[a-f0-9]{32}", image_id):
            for extension, media_type in _FORMATS.values():
                path = directory / f"{image_id}.{extension}"
                if path.is_file():
                    return StoredImage(image_id, path, media_type, path.stat().st_size)
        raise RoomNotFoundError("Image not found", code="image_not_found")
