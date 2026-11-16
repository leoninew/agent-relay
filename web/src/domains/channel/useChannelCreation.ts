import { computed, ref } from "vue";

import { ApiClientError, describeApiError } from "@/services/api";
import type { CreateChannel } from "@/services/channelApi";
import type { JSONStorage } from "@/services/storage";
import { readJSON } from "@/services/storage";
import { useChannelsStore } from "@/stores/channels";

export type ChannelCreationStep = "form" | "creating" | "unknown";

type PendingCreation = CreateChannel & { roomId: string };

export function useChannelCreation(
  roomId: () => string | undefined,
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

  function savePending(room: string, value?: PendingCreation): void {
    if (!storage || !room) return;
    const key = `conflua-channel-creation:${room}`;
    if (value) storage.setItem(key, JSON.stringify(value));
    else storage.removeItem(key);
  }

  function reset(): void {
    name.value = "";
    description.value = "";
    useWorktree.value = false;
    step.value = "form";
    channelId.value = undefined;
    error.value = undefined;
    const room = roomId();
    const saved =
      storage && room
        ? readJSON<PendingCreation | undefined>(
            storage,
            `conflua-channel-creation:${room}`,
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
    if (busy.value || step.value === "unknown") return false;
    const room = roomId();
    if (!room || !name.value.trim()) return false;
    channelId.value = `channel-${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
    const request: CreateChannel = {
      name: name.value.trim(),
      description: description.value.trim(),
      channelId: channelId.value,
      useWorktree: useWorktree.value,
    };
    step.value = "creating";
    error.value = undefined;
    savePending(room, { roomId: room, ...request });
    try {
      await channels.create(room, request);
      savePending(room);
      step.value = "form";
      return true;
    } catch (caught) {
      error.value = errorKey(caught, "errors.channelCreate");
      step.value =
        caught instanceof ApiClientError && caught.status && caught.status < 500
          ? "form"
          : "unknown";
      if (step.value === "form") savePending(room);
      return false;
    }
  }

  async function lookup(selectedChannelId: string): Promise<boolean> {
    const room = roomId();
    if (!room || busy.value) return false;
    checking.value = true;
    error.value = undefined;
    try {
      const channel = await channels.lookup(room, selectedChannelId);
      if (channel.archivedAt) {
        error.value = "errors.channel_unavailable";
        return false;
      }
      savePending(room);
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
