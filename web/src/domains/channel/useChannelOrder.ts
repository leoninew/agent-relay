import { computed } from "vue";

import { useStoredOrder } from "@/composables/useStoredOrder";
import type { Channel } from "@/services/channelApi";
import { roomCacheKey } from "@/services/cacheKeys";

export function useChannelOrder(roomId: () => string | undefined, channels: () => Channel[]) {
  const defaultChannel = computed(() => channels().find((channel) => channel.isDefault));
  const { orderedItems: sortableChannels, moveItem: moveChannel } = useStoredOrder(
    () => roomCacheKey(roomId() ?? "", "channels-order"),
    () => channels().filter((channel) => !channel.isDefault),
  );
  const availableChannels = computed(() => [
    ...(defaultChannel.value ? [defaultChannel.value] : []),
    ...sortableChannels.value,
  ]);

  return { defaultChannel, sortableChannels, availableChannels, moveChannel };
}
