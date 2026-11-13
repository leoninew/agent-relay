from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_relay.application.dto.preferences import LanguagePreference


class PreferencesSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    language: LanguagePreference = "system"


class RequestLogMessages(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    begin: str
    body: str
    end: str
    failed: str


class ResponseLogMessages(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    body: str


class StaticSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    directory: Path


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: Path
    migrate_on_startup: bool = False


class CodexSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    command: list[str] = Field(min_length=1)
    rpc_timeout: float = Field(gt=0, le=300)
    queue_concurrency: int = Field(default=4, ge=1, le=32)

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
    reload_paths: list[str] = Field(min_length=1)

    @field_validator("reload_paths")
    @classmethod
    def validate_reload_paths(cls, value: list[str]) -> list[str]:
        if any(not path.strip() for path in value):
            raise ValueError("Reload paths cannot be blank")
        return value


class LoggingSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    body: BodyLoggingSettings
    request: RequestLogMessages
    response: ResponseLogMessages


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    profile: str
    server: ServerSettings
    static: StaticSettings
    database: DatabaseSettings
    codex: CodexSettings
    logging: LoggingSettings
    preferences: PreferencesSettings = Field(default_factory=PreferencesSettings)
