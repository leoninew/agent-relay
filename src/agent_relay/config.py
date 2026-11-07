import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from dynaconf import Dynaconf
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RequestLogMessages(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    begin: str
    body: str
    end: str
    failed: str


class ResponseLogMessages(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    body: str


class GreetingSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    prefix: str


class StaticSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    directory: Path


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: Path


class CodexSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command: list[str] = Field(min_length=1)
    rpc_timeout: float = Field(gt=0, le=300)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("Codex command arguments cannot be blank")
        return value


class BodyLoggingSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    limit: int = Field(ge=0)


class ServerSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    host: str = Field(min_length=1)
    port: int = Field(ge=0, le=65535)
    reload: bool


class LoggingSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    body: BodyLoggingSettings
    request: RequestLogMessages
    response: ResponseLogMessages


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    profile: str
    server: ServerSettings
    greeting: GreetingSettings
    static: StaticSettings
    database: DatabaseSettings
    codex: CodexSettings
    logging: LoggingSettings


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
