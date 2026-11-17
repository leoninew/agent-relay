import { computed } from "vue";

import { useStoredOrder } from "@/composables/useStoredOrder";
import type { Channel } from "@/services/channelApi";

export function useChannelOrder(roomId: () => string | undefined, channels: () => Channel[]) {
  const defaultChannel = computed(() => channels().find((channel) => channel.isDefault));
  const { orderedItems: sortableChannels, moveItem: moveChannel } = useStoredOrder(
    () => `conflua-channel-order:${roomId() ?? ""}`,
    () => channels().filter((channel) => !channel.isDefault),
  );
  const availableChannels = computed(() => [
    ...(defaultChannel.value ? [defaultChannel.value] : []),
    ...sortableChannels.value,
  ]);

  return { defaultChannel, sortableChannels, availableChannels, moveChannel };
}
