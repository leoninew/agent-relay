import { computed, ref } from "vue";

import type { MessageQueueScope, RoomMessage } from "@/services/roomApi";

type PanelTarget =
  | { kind: "message"; message: RoomMessage }
  | { kind: "topic"; id: string }
  | { kind: "member"; id: string };

type SidebarKind = "topic" | "member";

export function useRoomPanel(messages: () => RoomMessage[]) {
  const selectedTopicId = ref<string>();
  const selectedMemberId = ref<string>();
  const target = ref<PanelTarget>();
  const drawerOpen = ref(false);
  const queueScope = computed<MessageQueueScope>(() => {
    const selected = target.value;
    if (selected?.kind === "topic") return { topicId: selected.id };
    if (selected?.kind === "member") return { memberId: selected.id };
    return {};
  });
  const message = computed(() => {
    const selected = target.value;
    if (!selected) return messages().at(-1);
    return selected.kind === "message" ? selected.message : undefined;
  });

  function show(next: PanelTarget): void {
    target.value = next;
    drawerOpen.value = true;
  }

  function selectSidebar(kind: SidebarKind, resourceId: string | undefined): boolean {
    const selection = kind === "topic" ? selectedTopicId : selectedMemberId;
    const changed = selection.value !== resourceId;
    selection.value = resourceId;
    if (resourceId !== undefined) show({ kind, id: resourceId });
    else if (selectedTopicId.value === undefined && selectedMemberId.value === undefined) {
      closeDetails();
    } else if (target.value?.kind === kind) closeDetails();
    drawerOpen.value = true;
    return changed;
  }

  function showMessage(selected: RoomMessage): void {
    show({ kind: "message", message: selected });
  }

  function openDrawer(): void {
    drawerOpen.value = true;
  }

  function closeDetails(): void {
    target.value = undefined;
  }

  function syncMessages(messages: RoomMessage[]): void {
    const current = target.value;
    if (current?.kind !== "message") return;
    const updated = messages.find((candidate) => candidate.id === current.message.id);
    if (updated) target.value = { kind: "message", message: updated };
  }

  function reset(): void {
    selectedTopicId.value = undefined;
    selectedMemberId.value = undefined;
    target.value = undefined;
    drawerOpen.value = false;
  }

  return {
    selectedTopicId,
    selectedMemberId,
    target,
    drawerOpen,
    message,
    queueScope,
    selectSidebar,
    showMessage,
    openDrawer,
    closeDetails,
    syncMessages,
    reset,
  };
}
