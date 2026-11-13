import type { ResolvedLanguage } from "@/i18n";
import { apiClient } from "@/services/api";

export type LanguagePreference = "system" | ResolvedLanguage;
export type ThemePreference = "system" | "light" | "dark";
export type Preferences = {
  language: LanguagePreference;
  resolvedLanguage: ResolvedLanguage;
  theme: ThemePreference;
};
export type PreferencesUpdate = {
  language?: LanguagePreference;
  theme?: ThemePreference;
};

const timeout = 5000;

export async function fetchPreferences(): Promise<Preferences> {
  const { data } = await apiClient.get<Preferences>("/api/preferences", { timeout });
  return data;
}

export async function updatePreferences(update: PreferencesUpdate): Promise<Preferences> {
  const { data } = await apiClient.patch<Preferences>("/api/preferences", update, { timeout });
  return data;
}
