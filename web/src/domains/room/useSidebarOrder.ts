import { useStoredOrder } from "@/composables/useStoredOrder";
import { channelCacheKey } from "@/services/cacheKeys";

export function useSidebarOrder<Item extends { id: string }>(
  roomId: () => string,
  channelId: () => string,
  section: "topics" | "members",
  items: () => Item[],
) {
  return useStoredOrder(
    () =>
      channelCacheKey(
        roomId(),
        channelId(),
        section === "topics" ? "topics-order" : "members-order",
      ),
    items,
  );
}
