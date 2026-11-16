from types import SimpleNamespace
from unittest.mock import Mock

from starlette.requests import Request

from conflua.application.rooms.ports import RoomStore
from conflua.interfaces.dto import HttpDependencies, HttpLogging
from conflua.interfaces.http.channels.dependencies import get_channel_service
from conflua.interfaces.http.persistence import get_independent_room_store, get_room_store
from conflua.interfaces.http.transactions import RequestTransaction


def test_providers_separate_request_transactions_from_rpc_scopes() -> None:
    transaction = Mock(spec=RequestTransaction)
    request_store = Mock(spec=RoomStore)
    independent_store = Mock(spec=RoomStore)
    factory = Mock(return_value=request_store)
    channel_factory = Mock()
    dependencies = HttpDependencies(
        request_room_store=factory,
        request_channel_service=channel_factory,
        room_store=independent_store,
        context_for_channel=Mock(),
        session_driver=Mock(),
        queue_driver=Mock(),
        capability_driver=Mock(),
        logging=HttpLogging(0, "begin", "body", "end", "failed", "response"),
    )
    request = Request(
        {
            "type": "http",
            "headers": [],
            "app": SimpleNamespace(state=SimpleNamespace(http_dependencies=dependencies)),
            "state": {"database_transaction": transaction},
        }
    )

    assert get_room_store(request) is request_store
    factory.assert_called_once_with(transaction)
    assert get_channel_service(request) is channel_factory.return_value
    channel_factory.assert_called_once_with(transaction)
    request.scope["path_params"] = {"channel_id": "channel-api"}
    assert get_independent_room_store(request) is independent_store.for_channel.return_value
    independent_store.for_channel.assert_called_once_with("channel-api")
    transaction.finish.assert_not_called()
