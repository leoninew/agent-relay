import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientError } from "@/services/api";
import { fetchPreferences, updatePreferences } from "@/services/preferencesApi";
import { usePreferencesStore } from "@/stores/preferences";

vi.mock("@/services/preferencesApi", () => ({
  fetchPreferences: vi.fn(),
  updatePreferences: vi.fn(),
}));

describe("preferences", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    setActivePinia(createPinia());
  });

  it("loads the backend's resolved language", async () => {
    vi.mocked(fetchPreferences).mockResolvedValue({
      language: "system",
      resolvedLanguage: "zh-CN",
      theme: "system",
    });
    const store = usePreferencesStore();
    expect(await store.load()).toBe(true);
    expect(store.resolvedLanguage).toBe("zh-CN");
    expect(store.theme).toBe("system");
  });

  it("keeps the current language on a definite failure", async () => {
    const store = usePreferencesStore();
    vi.mocked(updatePreferences).mockRejectedValue(new ApiClientError("failed", "http_error"));
    expect(await store.save("zh-CN")).toBe(false);
    expect(store.resolvedLanguage).toBe("en");
    expect(store.error?.key).toBe("settings.saveFailed");
  });

  it("checks an unknown write result without repeating the patch", async () => {
    const store = usePreferencesStore();
    vi.mocked(updatePreferences).mockRejectedValue(new ApiClientError("timeout", "timeout"));
    vi.mocked(fetchPreferences).mockResolvedValue({
      language: "zh-CN",
      resolvedLanguage: "zh-CN",
      theme: "system",
    });
    expect(await store.save("zh-CN")).toBe(true);
    expect(store.resolvedLanguage).toBe("zh-CN");
    expect(updatePreferences).toHaveBeenCalledTimes(1);
    expect(fetchPreferences).toHaveBeenCalledTimes(1);
  });

  it("reports an unknown result if the confirmation also fails", async () => {
    const store = usePreferencesStore();
    vi.mocked(updatePreferences).mockRejectedValue(new ApiClientError("timeout", "timeout"));
    vi.mocked(fetchPreferences).mockRejectedValue(new Error("offline"));
    expect(await store.save("zh-CN")).toBe(false);
    expect(store.error?.key).toBe("settings.saveUnknown");
    expect(store.resolvedLanguage).toBe("en");
  });

  it("saves theme without changing the confirmed language", async () => {
    vi.mocked(fetchPreferences).mockResolvedValue({
      language: "en",
      resolvedLanguage: "en",
      theme: "system",
    });
    const store = usePreferencesStore();
    await store.load();
    vi.mocked(updatePreferences).mockResolvedValue({
      language: "en",
      resolvedLanguage: "en",
      theme: "dark",
    });
    expect(await store.saveTheme("dark")).toBe(true);
    expect(updatePreferences).toHaveBeenCalledWith({ theme: "dark" });
    expect(store.theme).toBe("dark");
    expect(store.language).toBe("en");
  });

  it("confirms only the requested theme after an unknown write", async () => {
    vi.mocked(updatePreferences).mockRejectedValue(new ApiClientError("timeout", "timeout"));
    vi.mocked(fetchPreferences).mockResolvedValue({
      language: "zh-CN",
      resolvedLanguage: "zh-CN",
      theme: "light",
    });
    const store = usePreferencesStore();
    expect(await store.saveTheme("light")).toBe(true);
    expect(store.theme).toBe("light");
    expect(store.language).toBe("zh-CN");
    expect(updatePreferences).toHaveBeenCalledTimes(1);
  });
});
