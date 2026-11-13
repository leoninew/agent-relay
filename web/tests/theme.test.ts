import { describe, expect, it, vi } from "vitest";

import { createSystemThemeMediaQuery, createThemeRuntime, resolveTheme } from "@/theme";
import type { ThemeMediaQuery, ThemeRoot } from "@/theme";

function createRoot(): ThemeRoot & { classes: Set<string> } {
  const classes = new Set<string>();
  return {
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
      toggle: (name, force) => {
        if (force ?? !classes.has(name)) classes.add(name);
        else classes.delete(name);
        return classes.has(name);
      },
    },
    dataset: {},
    style: { colorScheme: "" },
    classes,
  };
}

function createMedia(initial: boolean): ThemeMediaQuery & {
  listener: ((event: MediaQueryListEvent) => void) | null;
  set(matches: boolean): void;
} {
  return {
    matches: initial,
    listener: null,
    addEventListener(_type, listener) {
      this.listener = listener;
    },
    removeEventListener(_type, listener) {
      if (this.listener === listener) this.listener = null;
    },
    set(matches) {
      this.matches = matches;
      this.listener?.({ matches } as MediaQueryListEvent);
    },
  };
}

describe("theme", () => {
  it("falls back to light when system theme detection is unavailable", () => {
    expect(createSystemThemeMediaQuery(() => undefined).matches).toBe(false);
    expect(
      createSystemThemeMediaQuery(() => {
        throw new Error("matchMedia unavailable");
      }).matches,
    ).toBe(false);
  });

  it("applies the light fallback while preserving fixed dark", () => {
    const root = createRoot();
    const runtime = createThemeRuntime(
      root,
      createSystemThemeMediaQuery(() => undefined),
    );
    expect(root.dataset.theme).toBe("light");

    runtime.setPreference("dark");
    expect(root.dataset.theme).toBe("dark");
  });

  it("falls back to light when the theme query is malformed", () => {
    const media = createSystemThemeMediaQuery(() => () => ({ matches: false }) as ThemeMediaQuery);
    expect(media.matches).toBe(false);
    expect(() => media.removeEventListener("change", () => {})).not.toThrow();
  });

  it("resolves system preference against the current client", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("applies the root class, dataset, and color scheme", () => {
    const root = createRoot();
    const media = createMedia(true);
    const runtime = createThemeRuntime(root, media);
    expect(root.classes.has("dark")).toBe(true);
    expect(root.dataset.theme).toBe("dark");
    expect(root.style.colorScheme).toBe("dark");

    runtime.setPreference("light");
    expect(root.classes.has("dark")).toBe(false);
    expect(root.dataset.theme).toBe("light");
    expect(root.style.colorScheme).toBe("light");
  });

  it("follows system changes only for the system preference", () => {
    const root = createRoot();
    const media = createMedia(false);
    const runtime = createThemeRuntime(root, media);
    media.set(true);
    expect(root.dataset.theme).toBe("dark");

    runtime.setPreference("light");
    media.set(false);
    media.set(true);
    expect(root.dataset.theme).toBe("light");
  });

  it("removes its listener when stopped", () => {
    const root = createRoot();
    const media = createMedia(false);
    const remove = vi.spyOn(media, "removeEventListener");
    const runtime = createThemeRuntime(root, media);
    runtime.stop();
    expect(remove).toHaveBeenCalledWith("change", expect.any(Function));
    expect(media.listener).toBeNull();
  });
});
