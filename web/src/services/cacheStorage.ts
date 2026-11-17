import { roomCacheKey } from "@/services/cacheKeys";

export function removeRoomCacheStorage(roomId: string): void {
  if (typeof window === "undefined") return;
  const prefix = `${roomCacheKey(roomId)}:`;
  for (const kind of ["localStorage", "sessionStorage"] as const) {
    try {
      const storage = window[kind];
      const keys = Array.from({ length: storage.length }, (_, index) => storage.key(index));
      for (const key of keys) {
        if (key?.startsWith(prefix)) storage.removeItem(key);
      }
    } catch {
      continue;
    }
  }
}
