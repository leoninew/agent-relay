import { defineStore } from "pinia";
import { ref } from "vue";

import { describeApiError } from "@/services/api";
import type { MessageDescriptor } from "@/i18n";
import {
  createChannel as createChannelRequest,
  deleteChannel,
  fetchChannel,
  fetchChannels,
} from "@/services/channelApi";
import type { Channel, CreateChannel } from "@/services/channelApi";

export const useChannelsStore = defineStore("channels", () => {
  const byRoom = ref<Record<string, Channel[]>>({});
  const loadedRooms = ref<Record<string, boolean>>({});
  const loading = ref<Record<string, boolean>>({});
  const errors = ref<Record<string, MessageDescriptor | null>>({});
  const recent = ref<Record<string, string>>({});
  const pending = new Map<string, Promise<Channel[]>>();
  const controllers = new Map<string, AbortController>();

  function channels(roomId: string): Channel[] {
    return byRoom.value[roomId] ?? [];
  }

  function activeChannels(roomId: string): Channel[] {
    return channels(roomId).filter((channel) => !channel.archivedAt);
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
    if (!force && loadedRooms.value[roomId]) return channels(roomId);
    const inFlight = pending.get(roomId);
    if (inFlight) return inFlight;
    const controller = new AbortController();
    controllers.set(roomId, controller);
    loading.value[roomId] = true;
    errors.value[roomId] = null;
    const request = fetchChannels(roomId, controller.signal)
      .then((result) => {
        byRoom.value[roomId] = result;
        loadedRooms.value[roomId] = true;
        const stored = recent.value[roomId];
        const selected = stored ? resolveChannelId(roomId, stored) : undefined;
        if (selected) recent.value[roomId] = selected;
        else delete recent.value[roomId];
        return result;
      })
      .catch((caught: unknown) => {
        errors.value[roomId] = describeApiError(caught, "errors.channelLoad");
        throw caught;
      })
      .finally(() => {
        pending.delete(roomId);
        controllers.delete(roomId);
        loading.value[roomId] = false;
      });
    pending.set(roomId, request);
    return request;
  }

  function remember(roomId: string, channelId: string): void {
    recent.value[roomId] = channelId;
  }

  async function create(roomId: string, request: CreateChannel): Promise<Channel> {
    const channel = await createChannelRequest(roomId, request);
    byRoom.value[roomId] = [
      ...channels(roomId).filter((candidate) => candidate.id !== channel.id),
      channel,
    ];
    recent.value[roomId] = channel.id;
    return channel;
  }

  async function lookup(roomId: string, channelId: string): Promise<Channel> {
    const channel = await fetchChannel(roomId, channelId);
    byRoom.value[roomId] = [
      ...channels(roomId).filter((candidate) => candidate.id !== channel.id),
      channel,
    ];
    return channel;
  }

  async function remove(roomId: string, channelId: string): Promise<void> {
    await deleteChannel(roomId, channelId);
    byRoom.value[roomId] = channels(roomId).filter((candidate) => candidate.id !== channelId);
    if (recent.value[roomId] === channelId) delete recent.value[roomId];
  }

  function reset(roomId?: string): void {
    if (roomId) {
      controllers.get(roomId)?.abort();
      controllers.delete(roomId);
      pending.delete(roomId);
      delete byRoom.value[roomId];
      delete loadedRooms.value[roomId];
      delete loading.value[roomId];
      delete errors.value[roomId];
      delete recent.value[roomId];
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
    load,
    remember,
    create,
    lookup,
    remove,
    reset,
  };
});
