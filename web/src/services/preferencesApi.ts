import type { ResolvedLanguage } from "@/i18n";
import { apiClient } from "@/services/api";

export type LanguagePreference = "system" | ResolvedLanguage;
export type Preferences = { language: LanguagePreference; resolvedLanguage: ResolvedLanguage };

const timeout = 5000;

export async function fetchPreferences(): Promise<Preferences> {
  const { data } = await apiClient.get<Preferences>("/api/preferences", { timeout });
  return data;
}

export async function updatePreferences(language: LanguagePreference): Promise<Preferences> {
  const { data } = await apiClient.patch<Preferences>(
    "/api/preferences",
    { language },
    { timeout },
  );
  return data;
}
