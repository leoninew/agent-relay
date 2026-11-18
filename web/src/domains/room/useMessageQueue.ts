import { ref, watch } from "vue";
import { queueChangedSince } from "@/domains/room/roomEventUpdates";
import type { MessageDescriptor } from "@/i18n";

import { describeApiError } from "@/services/api";
import { deleteQueueMessage, fetchMessageQueue } from "@/services/roomApi";
import type {
  MessageQueuePage,
  MessageQueueScope,
  RoomEventPage,
  RoomMessage,
} from "@/services/roomApi";

export function useMessageQueue(
  roomId: () => string | undefined,
  scope: () => MessageQueueScope,
  channelId: () => string | undefined,
) {
  const messages = ref<RoomMessage[]>([]);
  const hasMore = ref(false);
  const loading = ref(false);
  const loadingMore = ref(false);
  const removingId = ref<string | null>(null);
  const error = ref<MessageDescriptor | null>(null);
  const removeError = ref<MessageDescriptor | null>(null);
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

  function followEvents() {
    const revision = ref(0);
    let eventCursor: number | undefined;
    watch(
      [() => scope().topicId, () => scope().memberId, revision],
      ([topic, member], [previousTopic, previousMember]) => {
        if (topic !== previousTopic || member !== previousMember) {
          reset();
        }
        if (eventCursor !== undefined && roomId() && channelId()) {
          void refresh();
        }
      },
    );
    return {
      reset() {
        eventCursor = undefined;
      },
      resume(snapshotEventId: number) {
        if (eventCursor === undefined) {
          eventCursor = snapshotEventId;
          revision.value++;
        }
        return Math.min(eventCursor, snapshotEventId);
      },
      advance(page: RoomEventPage) {
        if (eventCursor === undefined) {
          return;
        }
        if (queueChangedSince(page.events, eventCursor)) {
          revision.value++;
        }
        eventCursor = Math.max(eventCursor, page.nextEventId);
      },
    };
  }

  function apply(page: MessageQueuePage, loaded: RoomMessage[]): void {
    messages.value = [...loaded].sort((left, right) => right.seq - left.seq);
    hasMore.value = page.hasMore;
    nextBeforeSeq = page.nextBeforeSeq;
  }

  async function refresh(): Promise<void> {
    const currentRoom = roomId();
    if (!currentRoom) {
      return;
    }
    const currentChannel = channelId();
    if (!currentChannel) {
      return;
    }
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
        const query = {
          ...currentScope,
          beforeSeq: cursor,
          limit: Math.min(200, desiredCount - loaded.length),
        };
        page = await fetchMessageQueue(currentRoom, query, signal, currentChannel);
        if (
          requestVersion !== version ||
          currentRoom !== roomId() ||
          currentChannel !== channelId()
        ) {
          return;
        }
        loaded.push(...page.messages);
        cursor = page.nextBeforeSeq ?? undefined;
      } while (page.hasMore && loaded.length < desiredCount);
      apply(page, loaded);
    } catch (caught) {
      if (requestVersion === version) {
        error.value = describeApiError(caught, "errors.queueLoad");
      }
    } finally {
      if (requestVersion === version) {
        loading.value = false;
      }
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
    ) {
      return;
    }
    const currentChannel = channelId();
    if (!currentChannel) {
      return;
    }
    const requestVersion = version;
    controller = new AbortController();
    loadingMore.value = true;
    error.value = null;
    try {
      const query = { ...scope(), beforeSeq: nextBeforeSeq, limit: 50 };
      const page = await fetchMessageQueue(currentRoom, query, controller.signal, currentChannel);
      if (
        requestVersion !== version ||
        currentRoom !== roomId() ||
        currentChannel !== channelId()
      ) {
        return;
      }
      const combined = new Map(messages.value.map((message) => [message.id, message]));
      for (const message of page.messages) {
        combined.set(message.id, message);
      }
      apply(page, [...combined.values()]);
    } catch (caught) {
      if (requestVersion === version) {
        error.value = describeApiError(caught, "errors.queueMore");
      }
    } finally {
      if (requestVersion === version) {
        loadingMore.value = false;
      }
    }
  }

  async function remove(messageId: string): Promise<void> {
    const currentRoom = roomId();
    if (!currentRoom || removingId.value !== null) {
      return;
    }
    const currentChannel = channelId();
    if (!currentChannel) {
      return;
    }
    const currentScope = { ...scope() };
    removingId.value = messageId;
    removeError.value = null;
    try {
      await deleteQueueMessage(currentRoom, messageId, currentChannel);
      if (currentRoom === roomId() && currentChannel === channelId()) {
        await refresh();
      }
    } catch (caught) {
      const selectedScope = scope();
      if (
        currentRoom === roomId() &&
        currentChannel === channelId() &&
        currentScope.topicId === selectedScope.topicId &&
        currentScope.memberId === selectedScope.memberId
      ) {
        removeError.value = describeApiError(caught, "errors.queueRemove");
      }
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
    followEvents,
    loadMore,
    remove,
    reset,
    cancel,
  };
}
