from conflua.application.dto.images import UploadedImage
from conflua.application.images.ports import ImageStore, StoredImage
from conflua.application.rooms.ports import RoomQueries


class ImageService:
    def __init__(self, queries: RoomQueries, images: ImageStore, channel_id: str) -> None:
        self.queries = queries
        self.images = images
        self.channel_id = channel_id

    def upload(self, room_id: str, content: bytes) -> UploadedImage:
        self.queries.metadata(room_id)
        image = self.images.save(room_id, content)
        prefix = f"/api/room/{room_id}/channel/{self.channel_id}"
        url = f"{prefix}/image/{image.id}"
        return UploadedImage(
            id=image.id,
            url=url,
            markdown=f"![image]({url})",
            media_type=image.media_type,
            size=image.size,
        )

    def read(self, room_id: str, image_id: str) -> StoredImage:
        self.queries.metadata(room_id)
        return self.images.read(room_id, image_id)
