from typing import Annotated, cast

from fastapi import Depends, Request

from conflua.application.channels.ports import ChannelQueries
from conflua.application.channels.service import ChannelService
from conflua.interfaces.http.dependencies import get_http_dependencies
from conflua.interfaces.http.transactions import RequestTransaction


def get_channel_service(request: Request) -> ChannelService:
    transaction = cast(RequestTransaction, request.state.database_transaction)
    return get_http_dependencies(request).request_channel_service(transaction)


ChannelServiceDependency = Annotated[ChannelService, Depends(get_channel_service)]


def get_channel_queries(service: ChannelServiceDependency) -> ChannelQueries:
    return service


ChannelQueriesDependency = Annotated[ChannelQueries, Depends(get_channel_queries)]
