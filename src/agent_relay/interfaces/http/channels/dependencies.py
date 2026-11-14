from typing import Annotated, cast

from fastapi import Depends, Request

from agent_relay.application.channels.ports import ChannelQueries
from agent_relay.application.channels.service import ChannelService
from agent_relay.interfaces.http.dependencies import get_http_dependencies
from agent_relay.interfaces.http.transactions import RequestTransaction


def get_channel_service(request: Request) -> ChannelService:
    transaction = cast(RequestTransaction, request.state.database_transaction)
    return get_http_dependencies(request).request_channel_service(transaction)


ChannelServiceDependency = Annotated[ChannelService, Depends(get_channel_service)]


def get_channel_queries(service: ChannelServiceDependency) -> ChannelQueries:
    return service


ChannelQueriesDependency = Annotated[ChannelQueries, Depends(get_channel_queries)]
