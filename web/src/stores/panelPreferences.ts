import { defineStore } from "pinia";
import { ref } from "vue";

import { browserStorage, readJSON, writeJSON } from "@/services/storage";

const storageKey = "relay-panel-preferences";
type Panel = "navigation" | "details";
type PanelPreferences = Record<Panel, boolean>;

function loadPreferences(): PanelPreferences {
  const defaults = { navigation: false, details: false };
  try {
    const storage = browserStorage();
    const saved = storage ? readJSON<unknown>(storage, storageKey, null) : null;
    if (!saved || typeof saved !== "object") return defaults;
    const value = saved as Partial<Record<Panel, unknown>>;
    return {
      navigation: typeof value.navigation === "boolean" ? value.navigation : false,
      details: typeof value.details === "boolean" ? value.details : false,
    };
  } catch {
    return defaults;
  }
}

export const usePanelPreferencesStore = defineStore("panelPreferences", () => {
  const collapsed = ref<PanelPreferences>(loadPreferences());

  function setCollapsed(panel: Panel, value: boolean): void {
    if (collapsed.value[panel] === value) return;
    collapsed.value[panel] = value;
    try {
      const storage = browserStorage();
      if (storage) writeJSON(storage, storageKey, collapsed.value);
    } catch {
      // Keep the current session usable when browser storage is unavailable.
    }
  }

  return { collapsed, setCollapsed };
});
