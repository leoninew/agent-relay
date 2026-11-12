import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from dynaconf import Dynaconf

from agent_relay.bootstrap.settings import Settings


@lru_cache
def load_settings(
    project_root: Path | None = None,
    *,
    default_config: Path | None = None,
) -> Settings:
    root = (project_root or Path.cwd()).resolve()
    profile = os.environ.get("AGENT_RELAY_PROFILE", "prod")
    config_file = root / "config" / "config.yaml"
    if not config_file.is_file() and default_config is not None:
        config_file = default_config.resolve()
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
        **dotenv_values(root / f".env.{profile}", encoding="utf-8", interpolate=False),
        **os.environ,
    }
    for name, value in overrides.items():
        if name.startswith("AGENT_RELAY_") and name != "AGENT_RELAY_PROFILE" and value is not None:
            config.set(name.removeprefix("AGENT_RELAY_"), value, tomlfy=True, merge=False)

    values = {
        name.lower(): value for name, value in config.as_dict().items() if name != "LOAD_DOTENV"
    }
    return Settings.model_validate({**values, "profile": profile})
