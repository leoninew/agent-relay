import { ref } from "vue";

import { describeApiError } from "@/services/api";
import { deleteQueueMessage, fetchMessageQueue } from "@/services/roomApi";
import type { MessageQueuePage, MessageQueueScope, RoomMessage } from "@/services/roomApi";

export function useMessageQueue(
  roomId: () => string | undefined,
  scope: () => MessageQueueScope = () => ({}),
) {
  const messages = ref<RoomMessage[]>([]);
  const hasMore = ref(false);
  const loading = ref(false);
  const loadingMore = ref(false);
  const removingId = ref<string | null>(null);
  const error = ref<string | null>(null);
  const removeError = ref<string | null>(null);
  let nextBeforeSeq: number | null = null;
  let version = 0;
  let controller: AbortController | undefined;

  function cancel(): void {
    version++;
    controller?.abort();
    loading.value = false;
    loadingMore.value = false;
  }

  function reset(): void {
    cancel();
    messages.value = [];
    hasMore.value = false;
    nextBeforeSeq = null;
    error.value = null;
    removeError.value = null;
  }

  function apply(page: MessageQueuePage, loaded: RoomMessage[]): void {
    messages.value = [...loaded].sort((left, right) => right.seq - left.seq);
    hasMore.value = page.hasMore;
    nextBeforeSeq = page.nextBeforeSeq;
  }

  async function refresh(): Promise<void> {
    const currentRoom = roomId();
    if (!currentRoom) return;
    cancel();
    const requestVersion = version;
    controller = new AbortController();
    const signal = controller.signal;
    const currentScope = scope();
    const desiredCount = Math.max(50, messages.value.length);
    loading.value = true;
    error.value = null;
    try {
      const loaded: RoomMessage[] = [];
      let cursor: number | undefined;
      let page: MessageQueuePage;
      do {
        page = await fetchMessageQueue(
          currentRoom,
          {
            ...currentScope,
            beforeSeq: cursor,
            limit: Math.min(200, desiredCount - loaded.length),
          },
          signal,
        );
        if (requestVersion !== version || currentRoom !== roomId()) return;
        loaded.push(...page.messages);
        cursor = page.nextBeforeSeq ?? undefined;
      } while (page.hasMore && loaded.length < desiredCount);
      apply(page, loaded);
    } catch (caught) {
      if (requestVersion === version)
        error.value = describeApiError(caught, "消息队列加载失败，请重试。");
    } finally {
      if (requestVersion === version) loading.value = false;
    }
  }

  async function loadMore(): Promise<void> {
    const currentRoom = roomId();
    if (
      !currentRoom ||
      !hasMore.value ||
      nextBeforeSeq === null ||
      loading.value ||
      loadingMore.value
    )
      return;
    const requestVersion = version;
    controller = new AbortController();
    loadingMore.value = true;
    error.value = null;
    try {
      const page = await fetchMessageQueue(
        currentRoom,
        { ...scope(), beforeSeq: nextBeforeSeq, limit: 50 },
        controller.signal,
      );
      if (requestVersion !== version || currentRoom !== roomId()) return;
      const combined = new Map(messages.value.map((message) => [message.id, message]));
      for (const message of page.messages) combined.set(message.id, message);
      apply(page, [...combined.values()]);
    } catch (caught) {
      if (requestVersion === version)
        error.value = describeApiError(caught, "更多队列消息加载失败，请重试。");
    } finally {
      if (requestVersion === version) loadingMore.value = false;
    }
  }

  async function remove(messageId: string): Promise<void> {
    const currentRoom = roomId();
    if (!currentRoom || removingId.value !== null) return;
    const currentScope = { ...scope() };
    removingId.value = messageId;
    removeError.value = null;
    try {
      await deleteQueueMessage(currentRoom, messageId);
      if (currentRoom === roomId()) await refresh();
    } catch (caught) {
      const selectedScope = scope();
      if (
        currentRoom === roomId() &&
        currentScope.topicId === selectedScope.topicId &&
        currentScope.memberId === selectedScope.memberId
      )
        removeError.value = describeApiError(caught, "队列记录删除失败，请重试。");
    } finally {
      removingId.value = null;
    }
  }

  return {
    messages,
    hasMore,
    loading,
    loadingMore,
    removingId,
    error,
    removeError,
    refresh,
    loadMore,
    remove,
    reset,
    cancel,
  };
}
