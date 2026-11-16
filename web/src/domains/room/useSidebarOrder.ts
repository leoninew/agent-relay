import { useStoredOrder } from "@/composables/useStoredOrder";

export function useSidebarOrder<Item extends { id: string }>(
  roomId: () => string,
  channelId: () => string,
  section: "topics" | "members",
  items: () => Item[],
) {
  return useStoredOrder(() => `conflua-sidebar-order:${roomId()}:${channelId()}:${section}`, items);
}
