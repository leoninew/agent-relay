import { ref, watch } from "vue";

import type { ComposerDraft } from "@/domains/room/composerMemberMention";
import type { MessageDraft } from "@/services/roomApi";
import { createMessageDraftStorage } from "@/stores/messageDrafts";

export function draftSnapshot(draft: ComposerDraft): string {
  return JSON.stringify([
    draft.content,
    draft.topicIds,
    draft.mentionedMemberIds,
    draft.replyToMessageId ?? null,
    draft.capabilities?.map(({ type, id, name }) => [type, id, name]) ?? [],
    draft.memberMentions?.map(({ id, name, start, end }) => [id, name, start, end]) ?? [],
  ]);
}

export function useRoomDraft(storage = createMessageDraftStorage()) {
  const drafts = ref<Record<string, ComposerDraft>>({});
  const currentScope = ref<string>();

  watch(
    () => (currentScope.value ? drafts.value[currentScope.value] : undefined),
    (draft) => {
      const scope = currentScope.value;
      if (!scope || !draft) {
        return;
      }
      if (
        draft.content ||
        draft.topicIds.length ||
        draft.mentionedMemberIds.length ||
        draft.capabilities?.length ||
        draft.replyToMessageId
      ) {
        storage.save(scope, draft);
      } else {
        storage.remove(scope);
      }
    },
    { deep: true, flush: "sync" },
  );

  function open(scope: string): void {
    currentScope.value = undefined;
    const saved = drafts.value[scope] ?? storage.load(scope);
    drafts.value[scope] = saved
      ? {
          content: saved.content,
          topicIds: [...saved.topicIds],
          mentionedMemberIds: [...saved.mentionedMemberIds],
          ...(saved.capabilities
            ? { capabilities: saved.capabilities.map((reference) => ({ ...reference })) }
            : {}),
          ...(saved.memberMentions?.length
            ? { memberMentions: saved.memberMentions.map((mention) => ({ ...mention })) }
            : {}),
          ...(saved.replyToMessageId ? { replyToMessageId: saved.replyToMessageId } : {}),
        }
      : { content: "", topicIds: [], mentionedMemberIds: [] };
    currentScope.value = scope;
  }

  function finish(scope: string, sent: MessageDraft, snapshot: string): boolean {
    const saved = storage.load(scope);
    const editing = drafts.value[scope];
    if (
      !saved ||
      draftSnapshot(saved) !== snapshot ||
      (editing && draftSnapshot(editing) !== snapshot)
    ) {
      return false;
    }
    const draft: MessageDraft = {
      content: "",
      topicIds: [...sent.topicIds],
      mentionedMemberIds: [...sent.mentionedMemberIds],
    };
    drafts.value[scope] = draft;
    if (draft.topicIds.length || draft.mentionedMemberIds.length) {
      storage.save(scope, draft);
    } else {
      storage.remove(scope);
    }
    return true;
  }

  return { drafts, open, finish };
}
