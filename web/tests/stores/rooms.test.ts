import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { addRoomTopic } from "@/services/roomApi";
import { useRoomsStore } from "@/stores/rooms";

import { roomFixture } from "../fixtures/room";

vi.mock("@/services/roomApi", () => ({
  addRoomTopic: vi.fn(),
  createRoom: vi.fn(),
  fetchRooms: vi.fn(),
}));

describe("room state", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    setActivePinia(createPinia());
  });

  it("applies saved resources in one room while keeping messages and the applied cursor", async () => {
    const store = useRoomsStore();
    const first = roomFixture();
    const second = {
      ...roomFixture(),
      room: { ...first.room, id: "other-project" },
      topics: [],
      members: [],
    };
    store.sync(first);
    store.sync(second);
    const topic = { id: "review", name: "审查", description: "", messageCount: 0, deletedAt: null };
    vi.mocked(addRoomTopic).mockResolvedValue({
      ...topic,
      metadata: {
        ...first,
        topics: [...first.topics, topic],
        positions: [
          { ...first.positions[0], seq: 1, laterCount: 0, updatedAt: "2026-11-06T10:00:00Z" },
        ],
        eventId: 20,
      },
    });

    await store.createTopic(first.room.id, { name: "审查", description: "" });

    expect(store.snapshots[first.room.id].topics).toContainEqual(topic);
    expect(store.snapshots[first.room.id].messages).toEqual(first.messages);
    expect(store.snapshots[first.room.id].eventId).toBe(10);
    expect(store.snapshots[first.room.id].positions[0].seq).toBe(1);
    expect(store.snapshots[second.room.id].topics).toEqual([]);
    store.syncMetadata({ ...first, topics: [], eventId: 15 });
    expect(store.snapshots[first.room.id].topics).toContainEqual(topic);
  });

  it("prepends earlier pages once while retaining live delivery updates and global totals", () => {
    const store = useRoomsStore();
    const initial = roomFixture();
    const earlier = { ...initial.messages[0], id: "older", seq: 0 };
    const previous = structuredClone(initial.messages[0]);
    store.sync(initial);
    const liveMessage = { ...initial.messages[0], content: "已更新投递状态" };
    store.applyMessages(initial.room.id, [liveMessage], {});
    store.prependPage(initial.room.id, {
      messages: [earlier, previous],
      hasMore: true,
      nextBeforeSeq: 0,
      hasNewer: true,
    });

    const snapshot = store.snapshots[initial.room.id];
    expect(snapshot.messages.map((message) => message.id)).toEqual([
      "older",
      "msg-0001",
      "msg-0002",
    ]);
    expect(snapshot.messages[1].content).toBe("已更新投递状态");
    expect(snapshot.hasMore).toBe(true);
    expect(snapshot.hasNewer).toBe(false);
    expect(snapshot.summary.totalMessages).toBe(2);
  });

  it("applies delivery updates and appends new messages matching topic and sender", () => {
    const store = useRoomsStore();
    const initial = roomFixture();
    store.sync(initial);
    const newest = { ...initial.messages[1], id: "msg-0003", seq: 3 };
    const unrelated = { ...newest, id: "msg-0004", seq: 4, senderId: "frontend-worker" };
    store.applyMessages(initial.room.id, [newest, unrelated], {
      topicId: "backend",
      memberId: "backend-worker",
    });
    expect(store.snapshots[initial.room.id].messages.map((message) => message.seq)).toEqual([
      1, 2, 3,
    ]);

    store.snapshots[initial.room.id].hasNewer = true;
    store.applyMessages(
      initial.room.id,
      [
        { ...newest, content: "更新已加载消息" },
        { ...newest, id: "msg-0005", seq: 5 },
      ],
      {},
    );
    expect(store.snapshots[initial.room.id].messages.at(-1)?.content).toBe("更新已加载消息");
    expect(store.snapshots[initial.room.id].messages.map((message) => message.seq)).toEqual([
      1, 2, 3,
    ]);
  });

  it("keeps messages addressed to the user visible during topic filtering", () => {
    const store = useRoomsStore();
    const initial = roomFixture();
    store.sync(initial);
    const message = {
      ...initial.messages[1],
      id: "msg-0003",
      seq: 3,
      topicIds: [],
      mentionedMemberIds: ["user"],
      recipientIds: ["user"],
      deliveries: [],
    };
    store.applyMessages(initial.room.id, [message], { topicId: "frontend" });
    expect(store.snapshots[initial.room.id].messages.at(-1)).toEqual(message);
  });
});
