import { ref, watch } from "vue";

import type { MessageDraft } from "@/services/roomApi";
import { createMessageDraftStorage } from "@/stores/messageDrafts";

export function useRoomDraft(
  storage = createMessageDraftStorage(),
  locked: () => boolean = () => false,
) {
  const drafts = ref<Record<string, MessageDraft>>({});
  const currentRoomId = ref<string>();

  watch(
    () => (currentRoomId.value ? drafts.value[currentRoomId.value] : undefined),
    (draft) => {
      const roomId = currentRoomId.value;
      if (!roomId || !draft || locked()) return;
      if (
        draft.content ||
        draft.topicIds.length ||
        draft.mentionedMemberIds.length ||
        draft.capabilities?.length ||
        draft.replyToMessageId
      ) {
        storage.save(roomId, draft);
      } else storage.remove(roomId);
    },
    { deep: true, flush: "sync" },
  );

  function open(roomId: string, pending?: MessageDraft): void {
    currentRoomId.value = undefined;
    const saved = pending ?? drafts.value[roomId] ?? storage.load(roomId);
    drafts.value[roomId] = saved
      ? {
          content: saved.content,
          topicIds: [...saved.topicIds],
          mentionedMemberIds: [...saved.mentionedMemberIds],
          ...(saved.capabilities
            ? { capabilities: saved.capabilities.map((reference) => ({ ...reference })) }
            : {}),
          ...(saved.replyToMessageId ? { replyToMessageId: saved.replyToMessageId } : {}),
        }
      : { content: "", topicIds: [], mentionedMemberIds: [] };
    currentRoomId.value = roomId;
  }

  function remove(roomId: string): void {
    delete drafts.value[roomId];
    storage.remove(roomId);
  }

  return { drafts, open, remove };
}
