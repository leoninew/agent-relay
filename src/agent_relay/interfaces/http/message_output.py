from typing import Annotated, Literal

from fastapi import Depends, Header
from starlette.requests import HTTPConnection

from agent_relay.application.images.message_text import ImageMessageText
from agent_relay.interfaces.http.dependencies import get_http_dependencies


def get_message_output(
    connection: HTTPConnection,
    image_paths: Annotated[
        Literal["local", "url"], Header(alias="X-Agent-Relay-Image-Paths")
    ] = "url",
) -> ImageMessageText:
    images = get_http_dependencies(connection).image_store if image_paths == "local" else None
    channel_id = connection.path_params["channel_id"]
    return ImageMessageText(images.for_channel(channel_id) if images else None, channel_id)


MessageOutputDependency = Annotated[ImageMessageText, Depends(get_message_output)]
