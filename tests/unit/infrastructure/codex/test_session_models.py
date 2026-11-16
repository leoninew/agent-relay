from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from pytest import MonkeyPatch

from conflua.application.dto.session_models import SessionModelCatalog, UpdateSessionModel
from conflua.application.members.sessions import SessionModelRejected, SessionUnavailableError
from conflua.infrastructure.codex.driver import CodexDriver, ProxyRpc, RpcRejected


def metadata(**changes: Any) -> dict[str, Any]:
    return {
        "thread": {
            "id": "thread",
            "cwd": "D:/project",
            "modelProvider": "provider",
            "model": "old",
            "reasoningEffort": "high",
            "status": {"type": "active"},
            **changes,
        }
    }


def model(name: str = "new", **changes: Any) -> dict[str, Any]:
    return {
        "id": "catalog-entry-" + name,
        "model": name,
        "displayName": name.title(),
        "description": "Model description",
        "hidden": False,
        "defaultReasoningEffort": "none",
        "supportedReasoningEfforts": [{"reasoningEffort": "none"}],
        **changes,
    }


@pytest.fixture
def model_rpc(monkeypatch: MonkeyPatch) -> MagicMock:
    rpc = MagicMock(spec=ProxyRpc)
    rpc.__enter__.return_value = rpc
    monkeypatch.setattr("conflua.infrastructure.codex.driver.ProxyRpc", lambda *_: rpc)
    return rpc


def update(driver: CodexDriver) -> SessionModelCatalog:
    return driver.update_model(
        "thread", "d:/project/", UpdateSessionModel(session_id="thread", model="new")
    )


def test_provider_catalog_paginates_filters_hidden_and_keeps_real_current_model(
    model_rpc: Mock,
) -> None:
    model_rpc.call.side_effect = [
        metadata(model="unlisted"),
        {"data": [model(), model("hidden", hidden=True)], "nextCursor": "next"},
        {"data": [model("second")]},
    ]
    result = CodexDriver(["unused"], 1).model_catalog("thread", "D:/project")
    assert result.current_model == "unlisted"
    assert [option.model for option in result.models] == ["new", "second"]
    assert result.models[0].id == "catalog-entry-new"
    assert model_rpc.call.call_args_list[1].args == (
        "model/list",
        {"modelProvider": "provider", "includeHidden": False, "limit": 100, "cursor": None},
    )
    assert model_rpc.call.call_args_list[2].args[1]["cursor"] == "next"


def test_empty_catalog_and_unknown_current_model_are_preserved(model_rpc: Mock) -> None:
    model_rpc.call.side_effect = [metadata(model=None), {"data": []}]
    result = CodexDriver(["unused"], 1).model_catalog("thread", "D:/project")
    assert result.current_model is None and result.models == []


def test_models_without_reasoning_options_remain_selectable(model_rpc: Mock) -> None:
    model_rpc.call.side_effect = [
        metadata(),
        {"data": [model(supportedReasoningEfforts=[])]},
        {},
        metadata(model="new", reasoningEffort="none"),
    ]
    result = update(CodexDriver(["unused"], 1))
    assert result.current_model == "new"
    assert model_rpc.call.call_args_list[2].args[1]["effort"] == "none"


@pytest.mark.parametrize("bad", ["cursor", "duplicate", "duplicate-id", "effort", "malformed"])
def test_invalid_catalog_fails_safely(model_rpc: Mock, bad: str) -> None:
    cases: dict[str, list[object]] = {
        "cursor": [{"data": [], "nextCursor": "same"}, {"data": [], "nextCursor": "same"}],
        "duplicate": [{"data": [model(), model()]}],
        "duplicate-id": [{"data": [model(), model("second", id="catalog-entry-new")]}],
        "effort": [{"data": [model(defaultReasoningEffort="unsupported")]}],
        "malformed": [{"data": [{}]}],
    }
    model_rpc.call.side_effect = [metadata(), *cases[bad]]
    with pytest.raises(SessionUnavailableError) as caught:
        CodexDriver(["unused"], 1).model_catalog("thread", "D:/project")
    assert caught.value.code == "session_model_unavailable"


@pytest.mark.parametrize(
    "changes", [{"id": "wrong"}, {"cwd": "D:/wrong"}, {"status": {"type": "notLoaded"}}]
)
def test_invalid_session_never_reads_catalog_or_writes(
    model_rpc: Mock, changes: dict[str, Any]
) -> None:
    model_rpc.call.return_value = metadata(**changes)
    with pytest.raises(SessionModelRejected):
        update(CodexDriver(["unused"], 1))
    assert model_rpc.call.call_count == 1


@pytest.mark.parametrize("compatible", [True, False])
def test_switch_preserves_supported_effort_or_uses_default_and_confirms(
    model_rpc: Mock, compatible: bool
) -> None:
    effort = "high" if compatible else "none"
    selected = model(
        supportedReasoningEfforts=[{"reasoningEffort": effort}, {"reasoningEffort": "none"}]
    )
    model_rpc.call.side_effect = [
        metadata(),
        {"data": [selected]},
        {},
        metadata(model="new", reasoningEffort=effort),
    ]
    result = update(CodexDriver(["unused"], 1))
    assert result.current_model == "new"
    assert model_rpc.call.call_args_list[2].args == (
        "thread/settings/update",
        {"threadId": "thread", "model": "new", "effort": effort},
    )
    assert [entry.args[0] for entry in model_rpc.call.call_args_list] == [
        "thread/read",
        "model/list",
        "thread/settings/update",
        "thread/read",
    ]


def test_unavailable_model_never_submits(model_rpc: Mock) -> None:
    model_rpc.call.side_effect = [metadata(), {"data": []}]
    with pytest.raises(SessionModelRejected) as caught:
        update(CodexDriver(["unused"], 1))
    assert caught.value.code == "session_model_not_available"
    assert model_rpc.call.call_count == 2


def test_rebound_request_never_reaches_rpc(model_rpc: Mock) -> None:
    with pytest.raises(SessionModelRejected):
        CodexDriver(["unused"], 1).update_model(
            "other", "D:/project", UpdateSessionModel(session_id="thread", model="new")
        )
    model_rpc.call.assert_not_called()


def test_same_current_model_does_not_write(model_rpc: Mock) -> None:
    model_rpc.call.side_effect = [metadata(model="new"), {"data": [model()]}]
    update(CodexDriver(["unused"], 1))
    assert model_rpc.call.call_count == 2


def test_explicit_rejection_is_safe_and_not_retried(model_rpc: Mock) -> None:
    model_rpc.call.side_effect = [metadata(), {"data": [model()]}, RpcRejected("private", -32600)]
    with pytest.raises(SessionModelRejected) as caught:
        update(CodexDriver(["unused"], 1))
    assert caught.value.code == "session_model_update_rejected"
    assert "private" not in str(caught.value)
    assert model_rpc.call.call_count == 3


@pytest.mark.parametrize("failure", ["before", "write", "read", "mismatch", "provider", "effort"])
def test_failures_distinguish_preflight_from_unknown_update(model_rpc: Mock, failure: str) -> None:
    responses: list[object] = [metadata(), {"data": [model()]}]
    if failure == "before":
        responses = [TimeoutError("private")]
    elif failure == "write":
        responses.append(TimeoutError("private"))
    else:
        responses.extend(
            [
                {},
                {
                    "read": TimeoutError("private"),
                    "mismatch": metadata(),
                    "provider": metadata(
                        model="new", reasoningEffort="none", modelProvider="other"
                    ),
                    "effort": metadata(model="new", reasoningEffort="high"),
                }[failure],
            ]
        )
    model_rpc.call.side_effect = responses
    with pytest.raises(SessionUnavailableError) as caught:
        update(CodexDriver(["unused"], 1))
    assert caught.value.code == (
        "session_model_unavailable" if failure == "before" else "session_model_update_unknown"
    )
    assert "private" not in str(caught.value)
    assert (
        sum(entry.args[0] == "thread/settings/update" for entry in model_rpc.call.call_args_list)
        <= 1
    )
