import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePanelPreferencesStore } from "@/stores/panelPreferences";
import type * as storage from "@/services/storage";

const saved = vi.hoisted(() => new Map<string, string>());
vi.mock("@/services/storage", async (importOriginal) => ({
  ...(await importOriginal<typeof storage>()),
  browserStorage: () => ({
    getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => saved.set(key, value),
    removeItem: (key: string) => saved.delete(key),
  }),
}));

describe("panel preferences", () => {
  beforeEach(() => {
    saved.clear();
    setActivePinia(createPinia());
  });

  it("restores each panel's last state in a new session", () => {
    const store = usePanelPreferencesStore();
    store.setCollapsed("navigation", true);
    store.setCollapsed("details", true);
    store.setCollapsed("navigation", false);

    setActivePinia(createPinia());
    expect(usePanelPreferencesStore().collapsed).toEqual({ navigation: false, details: true });
  });

  it("ignores invalid stored values", () => {
    saved.set("relay-panel-preferences", '{"navigation":"false","details":true}');
    expect(usePanelPreferencesStore().collapsed).toEqual({ navigation: false, details: true });
  });
});
