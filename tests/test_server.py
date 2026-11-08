from unittest.mock import Mock

import pytest
import uvicorn

from agent_relay import development_reload, server
from agent_relay.config import load_settings


@pytest.mark.parametrize("reload_enabled", [True, False])
def test_server_uses_configured_startup(
    monkeypatch: pytest.MonkeyPatch, reload_enabled: bool
) -> None:
    base = load_settings()
    settings = base.model_copy(
        update={
            "profile": "qa",
            "server": base.server.model_copy(update={"reload": reload_enabled}),
        }
    )
    run = Mock()
    run_development = Mock()
    monkeypatch.setattr(server, "load_settings", lambda: settings)
    monkeypatch.setattr(server, "configure_logging", Mock())
    monkeypatch.setattr(server, "run_development", run_development)
    monkeypatch.setattr("uvicorn.run", run)
    monkeypatch.setattr("sys.argv", ["agent-relay-server"])

    server.main()

    if reload_enabled:
        run_development.assert_called_once_with(settings.server, "qa")
    else:
        run.assert_called_once_with(
            "agent_relay.server:create_server_app",
            host=settings.server.host,
            port=settings.server.port,
            reload=False,
            factory=True,
            access_log=False,
            log_config=None,
        )


def test_development_startup_resolves_active_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings().server
    config = Mock()
    config_factory = Mock(return_value=config)
    reload_factory = Mock()
    monkeypatch.setattr(uvicorn, "Config", config_factory)
    monkeypatch.setattr(uvicorn, "Server", Mock())
    monkeypatch.setattr(development_reload, "DevelopmentReload", reload_factory)

    development_reload.run_development(settings, "qa")

    assert config.reload is True
    assert reload_factory.call_args.kwargs["paths"] == [
        "src/agent_relay/**/*.py",
        "src/agent_relay/logging.yaml",
        "config/*.yaml",
        ".env.qa",
    ]
    reload_factory.return_value.run.assert_called_once_with()
