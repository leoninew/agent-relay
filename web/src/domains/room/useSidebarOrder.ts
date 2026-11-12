import { useStoredOrder } from "@/composables/useStoredOrder";

export function useSidebarOrder<Item extends { id: string }>(
  roomId: () => string,
  section: "topics" | "members",
  items: () => Item[],
) {
  return useStoredOrder(() => `relay-sidebar-order:${roomId()}:${section}`, items);
}
