import { computed, ref } from "vue";

import { ApiClientError, describeApiError } from "@/services/api";
import { issueChannelId } from "@/services/channelApi";
import type { CreateChannel } from "@/services/channelApi";
import type { JSONStorage } from "@/services/storage";
import { readJSON } from "@/services/storage";
import { channelCacheKey } from "@/services/cacheKeys";
import { useChannelsStore } from "@/stores/channels";

export type ChannelCreationStep = "form" | "creating" | "unknown";

type PendingCreation = CreateChannel & { roomId: string };

export function useChannelCreation(
  roomId: () => string | undefined,
  sourceChannelId: () => string | undefined,
  storage: JSONStorage | undefined = typeof window === "undefined"
    ? undefined
    : window.sessionStorage,
) {
  const channels = useChannelsStore();
  const name = ref("");
  const description = ref("");
  const useWorktree = ref(false);
  const step = ref<ChannelCreationStep>("form");
  const channelId = ref<string>();
  const error = ref<string>();
  const checking = ref(false);
  const busy = computed(() => checking.value || step.value === "creating");

  function savePending(room: string, sourceChannel: string, value?: PendingCreation): void {
    if (!storage || !room) {
      return;
    }
    const key = channelCacheKey(room, sourceChannel, "channel-creation");
    if (value) {
      storage.setItem(key, JSON.stringify(value));
    } else {
      storage.removeItem(key);
    }
  }

  function reset(): void {
    name.value = "";
    description.value = "";
    useWorktree.value = false;
    step.value = "form";
    channelId.value = undefined;
    error.value = undefined;
    const room = roomId();
    const sourceChannel = sourceChannelId();
    const saved =
      storage && room && sourceChannel
        ? readJSON<PendingCreation | undefined>(
            storage,
            channelCacheKey(room, sourceChannel, "channel-creation"),
            undefined,
          )
        : undefined;
    if (
      saved?.roomId === room &&
      saved?.channelId &&
      typeof saved.name === "string" &&
      typeof saved.description === "string"
    ) {
      channelId.value = saved.channelId;
      name.value = saved.name;
      description.value = saved.description;
      useWorktree.value = saved.useWorktree;
      step.value = "unknown";
    }
  }

  async function submit(): Promise<boolean> {
    if (busy.value || step.value === "unknown") {
      return false;
    }
    const room = roomId();
    const sourceChannel = sourceChannelId();
    if (!room || !sourceChannel || !name.value.trim()) {
      return false;
    }
    const form = {
      name: name.value.trim(),
      description: description.value.trim(),
      useWorktree: useWorktree.value,
    };
    step.value = "creating";
    error.value = undefined;
    channelId.value = undefined;
    try {
      channelId.value = await issueChannelId(room);
    } catch (caught) {
      error.value = errorKey(caught, "errors.channelCreate");
      step.value = "form";
      return false;
    }
    const request: CreateChannel = { ...form, channelId: channelId.value };
    try {
      savePending(room, sourceChannel, { roomId: room, ...request });
      await channels.create(room, request);
      savePending(room, sourceChannel);
      step.value = "form";
      return true;
    } catch (caught) {
      error.value = errorKey(caught, "errors.channelCreate");
      step.value =
        caught instanceof ApiClientError &&
        caught.kind === "http_error" &&
        caught.status &&
        caught.status >= 400 &&
        caught.status < 500
          ? "form"
          : "unknown";
      if (step.value === "form") {
        savePending(room, sourceChannel);
      }
      return false;
    }
  }

  async function lookup(selectedChannelId: string): Promise<boolean> {
    const room = roomId();
    const sourceChannel = sourceChannelId();
    if (!room || !sourceChannel || busy.value) {
      return false;
    }
    checking.value = true;
    error.value = undefined;
    try {
      const channel = await channels.lookup(room, selectedChannelId);
      if (channel.status === "archived" || channel.archivedAt) {
        error.value = "errors.channel_unavailable";
        return false;
      }
      savePending(room, sourceChannel);
      step.value = "form";
      return true;
    } catch (caught) {
      error.value = errorKey(caught, "errors.channelLoad");
      return false;
    } finally {
      checking.value = false;
    }
  }

  reset();

  return {
    name,
    description,
    useWorktree,
    step,
    channelId,
    error,
    busy,
    reset,
    submit,
    lookup,
  };
}

function errorKey(caught: unknown, fallback: string): string {
  return describeApiError(caught, fallback).key;
}
