import { DEFAULT_CHANNEL_ID } from "@/domains/channel/channelRoutes";
import { appCacheKey, channelCacheKey, roomCacheKey } from "@/services/cacheKeys";
import { readJSON } from "@/services/storage";

function storageKeys(storage: Storage): string[] {
  return Array.from({ length: storage.length }, (_, index) => storage.key(index)).filter(
    (key): key is string => key !== null,
  );
}

function moveKey(storage: Storage, previous: string, current: string): void {
  const value = storage.getItem(previous);
  if (value === null) return;
  if (storage.getItem(current) === null) storage.setItem(current, value);
  storage.removeItem(previous);
}

export function upgradeCacheStorage(): void {
  try {
    const local = window.localStorage;
    const session = window.sessionStorage;
    for (const key of storageKeys(local)) {
      if (key === "conflua-room-order") {
        moveKey(local, key, appCacheKey("rooms-order"));
      } else if (key === "conflua-panel-preferences") {
        moveKey(local, key, appCacheKey("panels"));
      } else {
        const room = /^conflua-(channel-order|selected-channel):([^:]+)$/.exec(key);
        const channel = /^conflua-sidebar-order:([^:]+):([^:]+):(topics|members)$/.exec(key);
        if (room) {
          moveKey(
            local,
            key,
            roomCacheKey(
              room[2],
              room[1] === "channel-order" ? "channels-order" : "selected-channel",
            ),
          );
        } else if (channel) {
          moveKey(
            local,
            key,
            channelCacheKey(
              channel[1],
              channel[2],
              channel[3] === "topics" ? "topics-order" : "members-order",
            ),
          );
        }
      }
    }
    for (const key of storageKeys(session)) {
      const resource = /^conflua-(draft|publication):([^:]+):([^:]+)$/.exec(key);
      const creation = /^conflua-channel-creation:([^:]+)$/.exec(key);
      if (resource) {
        moveKey(
          session,
          key,
          channelCacheKey(
            resource[2],
            resource[3],
            resource[1] === "draft" ? "draft" : "publication",
          ),
        );
      } else if (creation) {
        const selected = readJSON<unknown>(
          local,
          roomCacheKey(creation[1], "selected-channel"),
          null,
        );
        moveKey(
          session,
          key,
          channelCacheKey(
            creation[1],
            typeof selected === "string" && selected ? selected : DEFAULT_CHANNEL_ID,
            "channel-creation",
          ),
        );
      }
    }
  } catch {
    return;
  }
}
