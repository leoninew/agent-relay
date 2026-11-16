import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from dynaconf import Dynaconf

from conflua.bootstrap.settings import Settings

_CLIENT_ENVIRONMENT_VARIABLES = {
    "CONFLUA_PROFILE",
    "CONFLUA_SESSION_ID",
    "CONFLUA_CHANNEL_ID",
    "CONFLUA_URL",
    "CONFLUA_HTTP_TIMEOUT",
}


@lru_cache
def load_settings(
    project_root: Path | None = None,
    *,
    default_config: Path | None = None,
    profile: str | None = None,
    override_file: Path | None = None,
) -> Settings:
    root = (project_root or Path.cwd()).resolve()
    selected_profile = profile or os.environ.get("CONFLUA_PROFILE", "prod")
    config_file = (
        default_config.resolve() if default_config is not None else root / "config" / "config.yaml"
    )
    if not config_file.is_file():
        raise FileNotFoundError(f"Required config file not found: {config_file}")

    config = Dynaconf(
        settings_files=[str(config_file)],
        loaders=[],
        load_dotenv=False,
        environments=False,
        merge_enabled=False,
        encoding="utf-8",
    )
    overrides = {
        **dotenv_values(
            override_file or root / f".env.{selected_profile}",
            encoding="utf-8",
            interpolate=False,
        ),
        **os.environ,
    }
    for name, value in overrides.items():
        if (
            name.startswith("CONFLUA_")
            and name not in _CLIENT_ENVIRONMENT_VARIABLES
            and value is not None
        ):
            config.set(name.removeprefix("CONFLUA_"), value, tomlfy=True, merge=False)

    values = {
        name.lower(): value for name, value in config.as_dict().items() if name != "LOAD_DOTENV"
    }
    return Settings.model_validate({**values, "profile": selected_profile})
