import { beforeEach, describe, expect, it, vi } from "vitest";

import { useMessageQueue } from "@/domains/room/useMessageQueue";
import { deleteQueueMessage, fetchMessageQueue } from "@/services/roomApi";
import type { MessageQueuePage, MessageQueueScope } from "@/services/roomApi";

import { roomFixture } from "../../fixtures/room";

vi.mock("@/services/roomApi", () => ({
  deleteQueueMessage: vi.fn(),
  fetchMessageQueue: vi.fn(),
}));
const fetchQueue = vi.mocked(fetchMessageQueue);
const deleteMessage = vi.mocked(deleteQueueMessage);

function page(overrides: Partial<MessageQueuePage> = {}): MessageQueuePage {
  return {
    messages: [...roomFixture().messages].reverse(),
    totalMessages: 2,
    hasMore: false,
    nextBeforeSeq: null,
    ...overrides,
  };
}

describe("message queue", () => {
  beforeEach(() => vi.resetAllMocks());

  it("loads the newest room queue messages and appends an older page", async () => {
    const sample = roomFixture().messages[0];
    const first = Array.from({ length: 50 }, (_, index) => ({
      ...sample,
      id: `msg-${51 - index}`,
      seq: 51 - index,
    }));
    const second = { ...sample, id: "msg-1", seq: 1 };
    fetchQueue.mockResolvedValueOnce(
      page({ messages: first, totalMessages: 51, hasMore: true, nextBeforeSeq: 2 }),
    );
    const queue = useMessageQueue(() => "room/one");
    await queue.refresh();
    expect(queue.messages.value).toEqual(first);
    fetchQueue.mockResolvedValueOnce(page({ messages: [second], totalMessages: 51 }));
    await queue.loadMore();
    expect(fetchQueue).toHaveBeenLastCalledWith(
      "room/one",
      { beforeSeq: 2, limit: 50 },
      expect.any(AbortSignal),
    );
    expect(queue.messages.value).toEqual([...first, second]);
    expect(queue.hasMore.value).toBe(false);
  });

  it("refreshes completed messages out of the list and keeps previous content on failure", async () => {
    fetchQueue.mockResolvedValueOnce(page());
    const queue = useMessageQueue(() => "room");
    await queue.refresh();
    fetchQueue.mockRejectedValueOnce(new Error("offline"));
    await queue.refresh();
    expect(queue.messages.value).toEqual([...roomFixture().messages].reverse());
    expect(queue.error.value).toBeTruthy();
    fetchQueue.mockResolvedValueOnce(page({ messages: [], totalMessages: 0 }));
    await queue.refresh();
    expect(queue.messages.value).toEqual([]);
    expect(queue.error.value).toBeNull();
  });

  it("retains the expanded list capacity when refreshing", async () => {
    const sample = roomFixture().messages[0];
    const messages = Array.from({ length: 70 }, (_, index) => ({
      ...sample,
      id: `msg-${70 - index}`,
      seq: 70 - index,
    }));
    fetchQueue.mockResolvedValueOnce(
      page({
        messages: messages.slice(0, 50),
        totalMessages: 70,
        hasMore: true,
        nextBeforeSeq: 21,
      }),
    );
    const queue = useMessageQueue(() => "room");
    await queue.refresh();
    fetchQueue.mockResolvedValueOnce(page({ messages: messages.slice(50), totalMessages: 70 }));
    await queue.loadMore();
    fetchQueue.mockResolvedValueOnce(page({ messages, totalMessages: 70 }));
    await queue.refresh();
    expect(fetchQueue).toHaveBeenLastCalledWith(
      "room",
      { beforeSeq: undefined, limit: 70 },
      expect.any(AbortSignal),
    );
    expect(queue.messages.value).toHaveLength(70);
  });

  it("keeps the detail scope while paging and resets it when the detail changes", async () => {
    let scope: MessageQueueScope = { topicId: "frontend" };
    const sample = roomFixture().messages[0];
    const first = Array.from({ length: 50 }, (_, index) => ({
      ...sample,
      id: `msg-${51 - index}`,
      seq: 51 - index,
    }));
    const queue = useMessageQueue(
      () => "room",
      () => scope,
    );
    fetchQueue.mockResolvedValueOnce(
      page({ messages: first, totalMessages: 51, hasMore: true, nextBeforeSeq: 2 }),
    );
    await queue.refresh();
    fetchQueue.mockResolvedValueOnce(page({ messages: [sample] }));
    await queue.loadMore();
    expect(fetchQueue).toHaveBeenLastCalledWith(
      "room",
      { topicId: "frontend", beforeSeq: 2, limit: 50 },
      expect.any(AbortSignal),
    );
    scope = { memberId: "test-worker" };
    queue.reset();
    expect(queue.messages.value).toEqual([]);
    fetchQueue.mockResolvedValueOnce(page());
    await queue.refresh();
    expect(fetchQueue).toHaveBeenLastCalledWith(
      "room",
      { memberId: "test-worker", beforeSeq: undefined, limit: 50 },
      expect.any(AbortSignal),
    );
    scope = {};
    queue.reset();
    fetchQueue.mockResolvedValueOnce(page());
    await queue.refresh();
    expect(fetchQueue).toHaveBeenLastCalledWith(
      "room",
      { beforeSeq: undefined, limit: 50 },
      expect.any(AbortSignal),
    );
  });

  it("removes one message and reloads the current scope without clearing other pages", async () => {
    const sample = roomFixture().messages[0];
    const first = Array.from({ length: 50 }, (_, index) => ({
      ...sample,
      id: `msg-${125 - index}`,
      seq: 125 - index,
    }));
    fetchQueue.mockResolvedValueOnce(
      page({ messages: first, totalMessages: 125, hasMore: true, nextBeforeSeq: 76 }),
    );
    const queue = useMessageQueue(
      () => "room",
      () => ({ topicId: "frontend" }),
    );
    await queue.refresh();
    deleteMessage.mockResolvedValueOnce({ removedMessages: 1 });
    const remaining = [...first.slice(1), { ...sample, id: "msg-75", seq: 75 }];
    fetchQueue.mockResolvedValueOnce(
      page({ messages: remaining, totalMessages: 124, hasMore: true, nextBeforeSeq: 75 }),
    );
    const removing = queue.remove(first[0].id);
    expect(queue.removingId.value).toBe(first[0].id);
    await removing;
    expect(deleteMessage).toHaveBeenCalledOnce();
    expect(deleteMessage).toHaveBeenLastCalledWith("room", first[0].id);
    expect(fetchQueue).toHaveBeenLastCalledWith(
      "room",
      { topicId: "frontend", beforeSeq: undefined, limit: 50 },
      expect.any(AbortSignal),
    );
    expect(queue.messages.value).toEqual(remaining);
    expect(queue.hasMore.value).toBe(true);
    expect(queue.removingId.value).toBeNull();
    expect(queue.removeError.value).toBeNull();
  });

  it("keeps the list and reports a deletion failure without retrying the mutation", async () => {
    fetchQueue.mockResolvedValueOnce(page());
    const queue = useMessageQueue(() => "room");
    await queue.refresh();
    deleteMessage.mockRejectedValueOnce(new Error("offline"));
    const messageId = queue.messages.value[0].id;
    await queue.remove(messageId);
    expect(queue.messages.value).toEqual(page().messages);
    expect(queue.removeError.value).toBe("队列记录删除失败，请重试。");
    expect(queue.removingId.value).toBeNull();
    expect(deleteMessage).toHaveBeenCalledOnce();
    expect(deleteMessage).toHaveBeenLastCalledWith("room", messageId);
    expect(fetchQueue).toHaveBeenCalledOnce();
  });
});
