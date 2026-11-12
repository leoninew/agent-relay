from pathlib import Path

from agent_relay.bootstrap.config import load_settings
from agent_relay.bootstrap.settings import Settings
from agent_relay.resources import resource_root as resource_root


def user_data_root() -> Path:
    return (Path.home() / ".agent-relay").resolve()


def resolve_path(path: Path, *, root: Path) -> Path:
    expanded = path.expanduser()
    return (expanded if expanded.is_absolute() else root / expanded).resolve()


def load_app_settings(*, user_root: Path | None = None, resources: Path | None = None) -> Settings:
    active_user_root = (user_root or user_data_root()).resolve()
    active_resources = (resources or resource_root()).resolve()
    settings = load_settings(
        active_user_root,
        default_config=active_resources / "config" / "app.yaml",
        profile="app",
        override_file=active_user_root / ".env",
    )
    return settings.model_copy(
        update={
            "static": settings.static.model_copy(
                update={"directory": resolve_path(settings.static.directory, root=active_resources)}
            ),
            "database": settings.database.model_copy(
                update={"path": resolve_path(settings.database.path, root=active_user_root)}
            ),
        }
    )
