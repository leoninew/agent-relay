from types import SimpleNamespace
from unittest.mock import Mock

from starlette.requests import Request

from agent_relay.application.rooms.ports import RoomStore
from agent_relay.interfaces.dto import HttpDependencies, HttpLogging
from agent_relay.interfaces.http.persistence import get_independent_room_store, get_room_store
from agent_relay.interfaces.http.transactions import RequestTransaction


def test_providers_separate_request_transactions_from_rpc_scopes() -> None:
    transaction = Mock(spec=RequestTransaction)
    request_store = Mock(spec=RoomStore)
    independent_store = Mock(spec=RoomStore)
    factory = Mock(return_value=request_store)
    dependencies = HttpDependencies(
        request_room_store=factory,
        room_store=independent_store,
        context_scope=Mock(),
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
    assert get_independent_room_store(request) is independent_store
    transaction.finish.assert_not_called()
