import { defineStore } from "pinia";
import { ref } from "vue";

import type { MessageDescriptor, ResolvedLanguage } from "@/i18n";
import { ApiClientError } from "@/services/api";
import { fetchPreferences, updatePreferences } from "@/services/preferencesApi";
import type {
  LanguagePreference,
  Preferences,
  PreferencesUpdate,
  ThemePreference,
} from "@/services/preferencesApi";

export const usePreferencesStore = defineStore("preferences", () => {
  const language = ref<LanguagePreference>("system");
  const resolvedLanguage = ref<ResolvedLanguage>("en");
  const theme = ref<ThemePreference>("system");
  const loading = ref(false);
  const saving = ref(false);
  const error = ref<MessageDescriptor | null>(null);
  let generation = 0;

  function apply(preferences: Preferences): void {
    language.value = preferences.language;
    resolvedLanguage.value = preferences.resolvedLanguage;
    theme.value = preferences.theme;
  }

  async function load(): Promise<boolean> {
    const version = ++generation;
    loading.value = true;
    try {
      const preferences = await fetchPreferences();
      if (version !== generation) return false;
      apply(preferences);
      error.value = null;
      return true;
    } catch (caught) {
      if (version === generation) {
        error.value = {
          key: "settings.loadFailed",
          requestId: caught instanceof ApiClientError ? caught.requestId : undefined,
        };
      }
      return false;
    } finally {
      if (version === generation) loading.value = false;
    }
  }

  async function saveUpdate(update: PreferencesUpdate): Promise<boolean> {
    if (saving.value) return false;
    const version = ++generation;
    loading.value = false;
    saving.value = true;
    error.value = null;
    try {
      const preferences = await updatePreferences(update);
      if (version !== generation) return false;
      apply(preferences);
      return true;
    } catch (caught) {
      if (version !== generation) return false;
      if (caught instanceof ApiClientError && ["timeout", "network_error"].includes(caught.kind)) {
        try {
          const confirmed = await fetchPreferences();
          if (version !== generation) return false;
          apply(confirmed);
          if (
            (update.language === undefined || confirmed.language === update.language) &&
            (update.theme === undefined || confirmed.theme === update.theme)
          ) {
            return true;
          }
        } catch {
          if (version !== generation) return false;
          error.value = { key: "settings.saveUnknown", requestId: caught.requestId };
          return false;
        }
      }
      error.value = {
        key: "settings.saveFailed",
        requestId: caught instanceof ApiClientError ? caught.requestId : undefined,
      };
      return false;
    } finally {
      saving.value = false;
    }
  }

  function save(language: LanguagePreference): Promise<boolean> {
    return saveUpdate({ language });
  }

  function saveTheme(next: ThemePreference): Promise<boolean> {
    return saveUpdate({ theme: next });
  }

  return {
    language,
    resolvedLanguage,
    theme,
    loading,
    saving,
    error,
    load,
    save,
    saveTheme,
  };
});
