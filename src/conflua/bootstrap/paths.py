from pathlib import Path

from conflua.bootstrap.config import load_settings
from conflua.bootstrap.settings import Settings
from conflua.resources import resource_root as resource_root


def user_data_root() -> Path:
    return (Path.home() / ".conflua").resolve()


def resolve_path(path: Path, *, root: Path) -> Path:
    expanded = path.expanduser()
    return (expanded if expanded.is_absolute() else root / expanded).resolve()


def load_app_settings(*, user_root: Path | None = None, resources: Path | None = None) -> Settings:
    active_user_root = (user_root or user_data_root()).resolve()
    active_resources = (resources or resource_root()).resolve()
    settings = load_settings(
        active_user_root,
        default_config=active_resources / "config" / "conflua.yaml",
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
