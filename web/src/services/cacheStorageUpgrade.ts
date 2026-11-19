import { appCacheKey } from "@/services/cacheKeys";

function moveKey(storage: Storage, previous: string, current: string): void {
  const value = storage.getItem(previous);
  if (value === null) {
    return;
  }
  if (storage.getItem(current) === null) {
    storage.setItem(current, value);
  }
  storage.removeItem(previous);
}

export function upgradeCacheStorage(): void {
  try {
    const local = window.localStorage;
    moveKey(local, "conflua-room-order", appCacheKey("rooms-order"));
    moveKey(local, "conflua-panel-preferences", appCacheKey("panels"));
  } catch {
    return;
  }
}
