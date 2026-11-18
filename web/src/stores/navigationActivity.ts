import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { appCacheKey, channelCacheKey, roomCacheKey } from "@/services/cacheKeys";
import { fetchChannelMessageHeads, type ChannelMessageHead } from "@/services/channelApi";
import { browserStorage } from "@/services/storage";
import { useChannelsStore } from "@/stores/channels";
import { useRoomsStore } from "@/stores/rooms";

function sameIds(entries: { id: string }[], expected: ReadonlySet<string>): boolean {
  return entries.length === expected.size && entries.every(({ id }) => expected.has(id));
}

export const useNavigationActivity = defineStore("navigationActivity", () => {
  const storage = browserStorage();
  const initializedKey = appCacheKey("message-dots-initialized");
  let initialized = storage?.getItem(initializedKey) === "1";
  const heads = ref<ChannelMessageHead[]>([]);
  const seen = ref<Record<string, number>>({});
  const visible = ref(false);

  function advance(key: string, seq: number) {
    const stored = Number(storage?.getItem(key)) || 0;
    const next = Math.max(stored, seen.value[key] ?? 0, seq);
    if (next !== seen.value[key]) {
      seen.value[key] = next;
    }
    if (next > stored) {
      storage?.setItem(key, String(next));
    }
  }

  function apply(rows: ChannelMessageHead[]) {
    initialized ||= storage?.getItem(initializedKey) === "1";
    for (const row of rows) {
      advance(
        channelCacheKey(row.roomId, row.channelId, "seen-seq"),
        initialized ? 0 : row.latestSeq,
      );
    }
    if (!initialized) {
      initialized = true;
      storage?.setItem(initializedKey, "1");
    }
    heads.value = rows;
  }

  const unread = computed(() => {
    const rooms = new Map<string, Set<string>>();
    for (const { roomId, channelId, latestSeq } of heads.value) {
      if (latestSeq <= (seen.value[channelCacheKey(roomId, channelId, "seen-seq")] ?? 0)) {
        continue;
      }
      const channels = rooms.get(roomId) ?? new Set<string>();
      channels.add(channelId);
      rooms.set(roomId, channels);
    }
    return rooms;
  });

  function presented(roomId: string, channelId: string, seq: number) {
    if (visible.value) {
      advance(channelCacheKey(roomId, channelId, "seen-seq"), seq);
    }
  }

  function subscribe() {
    const rooms = useRoomsStore();
    const channels = useChannelsStore();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let request: AbortController | undefined;
    function reconcileDirectory(rows: ChannelMessageHead[]) {
      const byRoom = new Map<string, Set<string>>();
      for (const { roomId, channelId } of rows) {
        const ids = byRoom.get(roomId) ?? new Set<string>();
        ids.add(channelId);
        byRoom.set(roomId, ids);
      }
      const loads: Promise<unknown>[] = [];
      if (!sameIds(rooms.rooms, new Set(byRoom.keys()))) {
        loads.push(rooms.load());
      }
      for (const [roomId, ids] of byRoom) {
        if (
          channels.loadedRooms[roomCacheKey(roomId, "channels")] &&
          !sameIds(channels.activeChannels(roomId), ids)
        ) {
          loads.push(channels.load(roomId, true));
        }
      }
      return Promise.allSettled(loads);
    }
    async function refresh() {
      const controller = new AbortController();
      request = controller;
      try {
        const rows = await fetchChannelMessageHeads(controller.signal);
        if (!controller.signal.aborted) {
          apply(rows);
          void reconcileDirectory(rows);
        }
      } catch {
        // Keep the last successful summary until the next poll.
      } finally {
        if (!controller.signal.aborted) {
          timer = setTimeout(refresh, 5000);
        }
      }
    }
    function stop() {
      clearTimeout(timer);
      request?.abort();
      visible.value = false;
    }
    function visibilityChanged() {
      stop();
      visible.value = document.visibilityState === "visible";
      if (visible.value) {
        void refresh();
      }
    }
    document.addEventListener("visibilitychange", visibilityChanged);
    visibilityChanged();
    return () => {
      stop();
      document.removeEventListener("visibilitychange", visibilityChanged);
    };
  }
  return { unread, visible, presented, subscribe, apply };
});
