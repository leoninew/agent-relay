from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type LanguagePreference = Literal["system", "zh-CN", "en"]
type ResolvedLanguage = Literal["zh-CN", "en"]


class Preferences(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    language: LanguagePreference
    resolved_language: ResolvedLanguage = Field(alias="resolvedLanguage")


class UpdatePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: LanguagePreference
