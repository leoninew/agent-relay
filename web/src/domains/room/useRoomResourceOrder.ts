import { computed } from "vue";

import { useSidebarOrder } from "@/domains/room/useSidebarOrder";
import type { RoomSnapshot } from "@/services/roomApi";

export function useRoomResourceOrder(
  snapshot: () => RoomSnapshot | undefined,
  channelId: () => string | undefined,
) {
  const roomId = () => snapshot()?.room.id ?? "";
  const channel = () => channelId() ?? "";
  const { orderedItems: activeTopics, moveItem: moveTopic } = useSidebarOrder(
    roomId,
    channel,
    "topics",
    () => snapshot()?.topics.filter((topic) => !topic.deletedAt) ?? [],
  );
  const { orderedItems: activeAgents, moveItem: moveMember } = useSidebarOrder(
    roomId,
    channel,
    "members",
    () =>
      snapshot()?.members.filter((member) => member.kind === "agent" && !member.deletedAt) ?? [],
  );
  const topics = computed(() => [
    ...activeTopics.value,
    ...(snapshot()?.topics.filter((topic) => topic.deletedAt) ?? []),
  ]);
  const members = computed(() => [
    ...(snapshot()?.members.filter((member) => member.kind === "human") ?? []),
    ...activeAgents.value,
    ...(snapshot()?.members.filter((member) => member.kind === "agent" && member.deletedAt) ?? []),
  ]);

  return { topics, members, activeTopics, activeAgents, moveTopic, moveMember };
}
