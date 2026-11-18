import { ref, watch } from "vue";

import type { ComposerDraft } from "@/domains/room/composerMemberMention";
import type { MessageDraft } from "@/services/roomApi";
import { createMessageDraftStorage } from "@/stores/messageDrafts";

export function useRoomDraft(
  storage = createMessageDraftStorage(),
  locked: () => boolean = () => false,
) {
  const drafts = ref<Record<string, ComposerDraft>>({});
  const currentScope = ref<string>();

  watch(
    () => (currentScope.value ? drafts.value[currentScope.value] : undefined),
    (draft) => {
      const scope = currentScope.value;
      if (!scope || !draft || locked()) return;
      if (
        draft.content ||
        draft.topicIds.length ||
        draft.mentionedMemberIds.length ||
        draft.capabilities?.length ||
        draft.replyToMessageId
      ) {
        storage.save(scope, draft);
      } else storage.remove(scope);
    },
    { deep: true, flush: "sync" },
  );

  function open(scope: string, pending?: MessageDraft): void {
    currentScope.value = undefined;
    const saved: ComposerDraft | undefined = drafts.value[scope] ?? storage.load(scope) ?? pending;
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

  function finish(scope: string, sent: MessageDraft): void {
    const draft: MessageDraft = {
      content: "",
      topicIds: [...sent.topicIds],
      mentionedMemberIds: [...sent.mentionedMemberIds],
    };
    drafts.value[scope] = draft;
    if (draft.topicIds.length || draft.mentionedMemberIds.length) storage.save(scope, draft);
    else storage.remove(scope);
  }

  return { drafts, open, finish };
}
