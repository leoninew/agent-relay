import type { JSONStorage } from "@/services/storage";
import { browserStorage, readJSON, writeJSON } from "@/services/storage";

const storageKey = (roomId: string) => `relay-selected-channel:${roomId}`;

export function createChannelSelectionStorage(storage: JSONStorage | null = browserStorage()) {
  return {
    load(roomId: string): string | undefined {
      if (!storage) return undefined;
      const selected = readJSON<unknown>(storage, storageKey(roomId), undefined);
      return typeof selected === "string" && selected ? selected : undefined;
    },
    save(roomId: string, channelId: string): void {
      if (storage) writeJSON(storage, storageKey(roomId), channelId);
    },
    remove(roomId: string): void {
      storage?.removeItem(storageKey(roomId));
    },
  };
}
