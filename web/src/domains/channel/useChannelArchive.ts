import { ref, watch } from "vue";

import type { MessageDescriptor } from "@/i18n";
import { describeApiError } from "@/services/api";
import type { Channel } from "@/services/channelApi";
import { useChannelsStore } from "@/stores/channels";

export function canArchiveChannel(channel: Channel, currentChannelId: string | undefined) {
  return (
    Boolean(currentChannelId) &&
    !channel.isDefault &&
    channel.id !== currentChannelId &&
    channel.status === "active" &&
    !channel.archivedAt
  );
}

export function useChannelArchive(
  roomId: () => string | undefined,
  currentChannelId: () => string | undefined,
  locked: () => boolean,
) {
  const channels = useChannelsStore();
  const target = ref<Channel>();
  const busy = ref(false);
  const error = ref<MessageDescriptor | null>(null);

  watch(
    [roomId, currentChannelId],
    () => {
      target.value = undefined;
      error.value = null;
    },
    { flush: "sync" },
  );

  function open(channel: Channel): void {
    if (
      busy.value ||
      locked() ||
      !currentChannelId() ||
      roomId() !== channel.roomId ||
      !canArchiveChannel(channel, currentChannelId())
    )
      return;
    target.value = channel;
    error.value = null;
  }

  function close(): void {
    if (busy.value) return;
    target.value = undefined;
    error.value = null;
  }

  async function confirm(name: string): Promise<boolean> {
    const room = roomId();
    const channel = target.value;
    if (!room || !channel || busy.value || locked() || !currentChannelId()) return false;
    const latest = channels.channel(room, channel.id);
    if (room !== channel.roomId || !latest || !canArchiveChannel(latest, currentChannelId())) {
      close();
      return false;
    }
    busy.value = true;
    error.value = null;
    try {
      await channels.archive(room, channel.id, name);
      if (target.value?.roomId === room && target.value.id === channel.id) target.value = undefined;
      return true;
    } catch (caught) {
      if (target.value?.roomId === room && target.value.id === channel.id)
        error.value = describeApiError(caught, "errors.channelArchive");
      return false;
    } finally {
      busy.value = false;
    }
  }

  return { target, busy, error, open, close, confirm };
}
