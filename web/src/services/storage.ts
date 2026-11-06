export type JSONStorage = Pick<Storage, "getItem" | "removeItem" | "setItem">;

export function browserStorage(): JSONStorage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export function readJSON<T>(storage: JSONStorage, key: string, fallback: T): T {
  const raw = storage.getItem(key);
  if (!raw) {
    return fallback;
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    storage.removeItem(key);
    return fallback;
  }
}

export function writeJSON<T>(storage: JSONStorage, key: string, value: T): void {
  storage.setItem(key, JSON.stringify(value));
}
