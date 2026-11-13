from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

type LanguagePreference = Literal["system", "zh-CN", "en"]
type ResolvedLanguage = Literal["zh-CN", "en"]
type ThemePreference = Literal["system", "light", "dark"]


class Preferences(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    language: LanguagePreference
    resolved_language: ResolvedLanguage = Field(alias="resolvedLanguage")
    theme: ThemePreference


class StoredPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: LanguagePreference | None = None
    theme: ThemePreference | None = None


class UpdatePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: LanguagePreference | None = None
    theme: ThemePreference | None = None

    @model_validator(mode="after")
    def require_update(self) -> "UpdatePreferences":
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Preference values cannot be null")
        if self.language is None and self.theme is None:
            raise ValueError("At least one preference is required")
        return self
