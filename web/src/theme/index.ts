import type { ThemePreference } from "@/services/preferencesApi";

export type ResolvedTheme = "light" | "dark";

export type ThemeMediaQuery = {
  matches: boolean;
  addEventListener(type: "change", listener: (event: MediaQueryListEvent) => void): void;
  removeEventListener(type: "change", listener: (event: MediaQueryListEvent) => void): void;
};

export type ThemeRoot = {
  classList: Pick<DOMTokenList, "add" | "remove" | "toggle">;
  dataset: DOMStringMap;
  style: Pick<CSSStyleDeclaration, "colorScheme">;
};

export type ThemeRuntime = {
  setPreference(preference: ThemePreference): void;
  stop(): void;
};

const systemThemeQuery = "(prefers-color-scheme: dark)";

export type MatchMediaFactory = (query: string) => ThemeMediaQuery;

export function inertThemeMediaQuery(): ThemeMediaQuery {
  return {
    matches: false,
    addEventListener() {},
    removeEventListener() {},
  };
}

export function createSystemThemeMediaQuery(
  getMatchMedia?: () => MatchMediaFactory | undefined,
): ThemeMediaQuery {
  let matchMedia: MatchMediaFactory | undefined;
  try {
    matchMedia = getMatchMedia ? getMatchMedia() : window.matchMedia;
  } catch {
    matchMedia = undefined;
  }

  if (typeof matchMedia !== "function") return inertThemeMediaQuery();

  try {
    const query = matchMedia(systemThemeQuery);
    if (
      query &&
      typeof query.matches === "boolean" &&
      typeof query.addEventListener === "function" &&
      typeof query.removeEventListener === "function"
    ) {
      return query;
    }
  } catch {
    // Fall through to the inert query below.
  }

  return inertThemeMediaQuery();
}

export function resolveTheme(preference: ThemePreference, prefersDark: boolean): ResolvedTheme {
  if (preference !== "system") return preference;
  return prefersDark ? "dark" : "light";
}

export function createThemeRuntime(root: ThemeRoot, mediaQuery: ThemeMediaQuery): ThemeRuntime {
  let preference: ThemePreference = "system";

  function apply(): void {
    const resolved = resolveTheme(preference, mediaQuery.matches);
    root.classList.toggle("dark", resolved === "dark");
    root.dataset.theme = resolved;
    root.style.colorScheme = resolved;
  }

  function onSystemChange(): void {
    if (preference === "system") apply();
  }

  mediaQuery.addEventListener("change", onSystemChange);
  apply();

  return {
    setPreference(next) {
      preference = next;
      apply();
    },
    stop() {
      mediaQuery.removeEventListener("change", onSystemChange);
    },
  };
}
