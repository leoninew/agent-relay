import type { JSONStorage } from "@/services/storage";
import { browserStorage, readJSON, writeJSON } from "@/services/storage";
import { roomCacheKey } from "@/services/cacheKeys";

export function createChannelSelectionStorage(storage: JSONStorage | null = browserStorage()) {
  return {
    load(roomId: string): string | undefined {
      if (!storage) {
        return undefined;
      }
      const selected = readJSON<unknown>(
        storage,
        roomCacheKey(roomId, "selected-channel"),
        undefined,
      );
      return typeof selected === "string" && selected ? selected : undefined;
    },
    save(roomId: string, channelId: string): void {
      if (storage) {
        writeJSON(storage, roomCacheKey(roomId, "selected-channel"), channelId);
      }
    },
    remove(roomId: string): void {
      storage?.removeItem(roomCacheKey(roomId, "selected-channel"));
    },
  };
}
