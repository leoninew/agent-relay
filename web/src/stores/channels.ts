import { defineStore } from "pinia";
import { ref } from "vue";

import { createChannelSelectionStorage } from "@/domains/channel/channelSelection";
import { roomCacheKey } from "@/services/cacheKeys";
import { describeApiError } from "@/services/api";
import type { MessageDescriptor } from "@/i18n";
import {
  archiveChannel,
  createChannel as createChannelRequest,
  deleteChannel,
  fetchChannel,
  fetchChannels,
  updateChannel,
} from "@/services/channelApi";
import type { Channel, CreateChannel, UpdateChannel } from "@/services/channelApi";

export const useChannelsStore = defineStore("channels", () => {
  const selectionStorage = createChannelSelectionStorage();
  const byRoom = ref<Record<string, Channel[]>>({});
  const loadedRooms = ref<Record<string, boolean>>({});
  const loading = ref<Record<string, boolean>>({});
  const errors = ref<Record<string, MessageDescriptor | null>>({});
  const recent = ref<Record<string, string>>({});
  const pending = new Map<string, Promise<Channel[]>>();
  const controllers = new Map<string, AbortController>();

  function channels(roomId: string): Channel[] {
    return byRoom.value[roomCacheKey(roomId, "channels")] ?? [];
  }

  function activeChannels(roomId: string): Channel[] {
    return channels(roomId).filter((channel) => channel.status === "active" && !channel.archivedAt);
  }

  function channel(roomId: string, channelId: string): Channel | undefined {
    return channels(roomId).find((candidate) => candidate.id === channelId);
  }

  function resolveChannelId(roomId: string, requested: string): string | undefined {
    const available = activeChannels(roomId);
    if (!available.length) return undefined;
    return available.some((candidate) => candidate.id === requested) ? requested : undefined;
  }

  async function load(roomId: string, force = false): Promise<Channel[]> {
    const key = roomCacheKey(roomId, "channels");
    const selectionKey = roomCacheKey(roomId, "selected-channel");
    if (!force && loadedRooms.value[key]) return channels(roomId);
    const inFlight = pending.get(key);
    if (inFlight) return inFlight;
    const controller = new AbortController();
    controllers.set(key, controller);
    loading.value[key] = true;
    errors.value[key] = null;
    const request = fetchChannels(roomId, controller.signal)
      .then((result) => {
        if (controllers.get(key) !== controller) return result;
        byRoom.value[key] = result;
        loadedRooms.value[key] = true;
        const stored = recent.value[selectionKey] ?? selectionStorage.load(roomId);
        const selected = stored ? resolveChannelId(roomId, stored) : undefined;
        if (selected) recent.value[selectionKey] = selected;
        else {
          delete recent.value[selectionKey];
          if (stored) selectionStorage.remove(roomId);
        }
        return result;
      })
      .catch((caught: unknown) => {
        if (controllers.get(key) === controller)
          errors.value[key] = describeApiError(caught, "errors.channelLoad");
        throw caught;
      })
      .finally(() => {
        if (controllers.get(key) === controller) {
          pending.delete(key);
          controllers.delete(key);
          loading.value[key] = false;
        }
      });
    pending.set(key, request);
    return request;
  }

  function remember(roomId: string, channelId: string): void {
    recent.value[roomCacheKey(roomId, "selected-channel")] = channelId;
    selectionStorage.save(roomId, channelId);
  }

  function preferredChannel(roomId: string): string | undefined {
    return recent.value[roomCacheKey(roomId, "selected-channel")] ?? selectionStorage.load(roomId);
  }

  async function create(roomId: string, request: CreateChannel): Promise<Channel> {
    const channel = await createChannelRequest(roomId, request);
    byRoom.value[roomCacheKey(roomId, "channels")] = [
      ...channels(roomId).filter((candidate) => candidate.id !== channel.id),
      channel,
    ];
    remember(roomId, channel.id);
    return channel;
  }

  async function lookup(roomId: string, channelId: string): Promise<Channel> {
    const channel = await fetchChannel(roomId, channelId);
    byRoom.value[roomCacheKey(roomId, "channels")] = [
      ...channels(roomId).filter((candidate) => candidate.id !== channel.id),
      channel,
    ];
    return channel;
  }

  async function update(roomId: string, channelId: string, request: UpdateChannel): Promise<void> {
    const updated = await updateChannel(roomId, channelId, request);
    byRoom.value[roomCacheKey(roomId, "channels")] = channels(roomId).map((candidate) =>
      candidate.id === channelId ? updated : candidate,
    );
  }

  async function remove(roomId: string, channelId: string): Promise<void> {
    const wasSelected = preferredChannel(roomId) === channelId;
    await deleteChannel(roomId, channelId);
    byRoom.value[roomCacheKey(roomId, "channels")] = channels(roomId).filter(
      (candidate) => candidate.id !== channelId,
    );
    if (wasSelected) {
      delete recent.value[roomCacheKey(roomId, "selected-channel")];
      selectionStorage.remove(roomId);
    }
  }

  async function archive(roomId: string, channelId: string, name: string): Promise<void> {
    const updated = await archiveChannel(roomId, channelId, name);
    byRoom.value[roomCacheKey(roomId, "channels")] = channels(roomId).map((candidate) =>
      candidate.id === channelId ? updated : candidate,
    );
    if (preferredChannel(roomId) === channelId) {
      delete recent.value[roomCacheKey(roomId, "selected-channel")];
      selectionStorage.remove(roomId);
    }
  }

  function reset(roomId?: string): void {
    if (roomId) {
      const key = roomCacheKey(roomId, "channels");
      controllers.get(key)?.abort();
      controllers.delete(key);
      pending.delete(key);
      delete byRoom.value[key];
      delete loadedRooms.value[key];
      delete loading.value[key];
      delete errors.value[key];
      delete recent.value[roomCacheKey(roomId, "selected-channel")];
      return;
    }
    controllers.forEach((controller) => controller.abort());
    controllers.clear();
    pending.clear();
    byRoom.value = {};
    loadedRooms.value = {};
    loading.value = {};
    errors.value = {};
    recent.value = {};
  }

  return {
    byRoom,
    loadedRooms,
    loading,
    errors,
    recent,
    channels,
    activeChannels,
    channel,
    resolveChannelId,
    preferredChannel,
    load,
    remember,
    create,
    lookup,
    update,
    remove,
    archive,
    reset,
  };
});
