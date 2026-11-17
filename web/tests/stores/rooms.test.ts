import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { addRoomTopic, clearRoom, deleteRoom, updateRoom } from "@/services/roomApi";
import { useRoomsStore } from "@/stores/rooms";

import { roomFixture } from "../fixtures/room";

const removeDraft = vi.hoisted(() => vi.fn());
vi.mock("@/stores/messageDrafts", () => ({
  createMessageDraftStorage: () => ({ remove: removeDraft }),
}));

vi.mock("@/services/roomApi", () => ({
  addRoomTopic: vi.fn(),
  clearRoom: vi.fn(),
  createRoom: vi.fn(),
  deleteRoom: vi.fn(),
  fetchRooms: vi.fn(),
  updateRoom: vi.fn(),
}));

describe("room state", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    setActivePinia(createPinia());
  });

  it("merges activity and resources with independent versions in the selected channel", () => {
    const store = useRoomsStore();
    const initial = roomFixture();
    store.sync(initial, "channel-default");
    store.sync(roomFixture(), "other");
    const summary = { ...initial.summary, totalMessages: 100 };
    store.syncActivity(initial.room.id, { positions: [], summary, eventId: 30 }, "channel-default");
    store.syncMetadata({ ...initial, topics: [], eventId: 20 }, "channel-default");
    const snapshot = store.snapshots[store.snapshotKey(initial.room.id, "channel-default")];
    expect(snapshot.topics).toEqual([]);
    expect(snapshot.summary.totalMessages).toBe(100);
    expect(snapshot.positions).toEqual([]);
    expect(snapshot.eventId).toBe(10);
    store.syncActivity(initial.room.id, initial, "channel-default");
    expect(snapshot.summary.totalMessages).toBe(100);
    expect(store.snapshots[store.snapshotKey(initial.room.id, "other")].summary).toEqual(
      roomFixture().summary,
    );
  });

  it("removes a deleted room and its snapshot while retaining other rooms", async () => {
    const store = useRoomsStore();
    const snapshot = roomFixture();
    const otherRoom = { ...snapshot.room, id: "other" };
    store.rooms = [snapshot.room, otherRoom];
    store.sync(snapshot, "channel-default");
    store.sync({ ...snapshot, room: otherRoom }, "channel-default");
    vi.mocked(deleteRoom).mockResolvedValue();

    await store.remove(snapshot.room.id);

    expect(deleteRoom).toHaveBeenCalledWith(snapshot.room.id);
    expect(removeDraft).toHaveBeenCalledOnce();
    expect(removeDraft).toHaveBeenCalledWith(
      store.snapshotKey(snapshot.room.id, "channel-default"),
    );
    expect(store.rooms).toEqual([otherRoom]);
    expect(store.snapshots[store.snapshotKey(snapshot.room.id, "channel-default")]).toBeUndefined();
    expect(store.snapshots[store.snapshotKey(otherRoom.id, "channel-default")].room).toEqual(
      otherRoom,
    );
  });

  it("retains a room and its snapshot when deletion fails", async () => {
    const store = useRoomsStore();
    const snapshot = roomFixture();
    store.rooms = [snapshot.room];
    store.sync(snapshot, "channel-default");
    vi.mocked(deleteRoom).mockRejectedValue(new Error("unavailable"));

    await expect(store.remove(snapshot.room.id)).rejects.toThrow("unavailable");
    expect(removeDraft).not.toHaveBeenCalled();
    expect(store.rooms).toEqual([snapshot.room]);
    expect(store.snapshots[store.snapshotKey(snapshot.room.id, "channel-default")]).toEqual(
      snapshot,
    );
  });

  it("clears messages and pagination while applying member changes only to that room", async () => {
    const store = useRoomsStore();
    const snapshot = roomFixture();
    const other = { ...roomFixture(), room: { ...snapshot.room, id: "other" } };
    store.rooms = [snapshot.room, other.room];
    store.sync(
      { ...snapshot, hasMore: true, hasNewer: true, nextBeforeSeq: 10 },
      "channel-default",
    );
    store.sync(other, "channel-default");
    const metadata = {
      ...snapshot,
      members: snapshot.members.map((member, index) =>
        index === 0 ? { ...member, deletedAt: "2026-11-12T10:00:00Z", topicIds: [] } : member,
      ),
      positions: [],
      summary: {
        totalMessages: 0,
        queuedCount: 0,
        receivedCount: 0,
        pendingCount: 0,
        submittingCount: 0,
        rejectedCount: 0,
        unknownCount: 0,
      },
      eventId: 20,
    };
    vi.mocked(clearRoom).mockResolvedValue({ removedMessages: 2, removedMembers: 1, metadata });

    await store.clear(snapshot.room.id, "channel-default");

    expect(removeDraft).not.toHaveBeenCalled();
    expect(store.rooms).toEqual([snapshot.room, other.room]);
    expect(store.snapshots[store.snapshotKey(snapshot.room.id, "channel-default")]).toEqual({
      ...metadata,
      messages: [],
      hasMore: false,
      hasNewer: false,
      nextBeforeSeq: null,
    });
    expect(store.snapshots[store.snapshotKey(other.room.id, "channel-default")]).toEqual(other);
    store.syncMetadata({ ...snapshot, eventId: 15 }, "channel-default");
    expect(
      store.snapshots[store.snapshotKey(snapshot.room.id, "channel-default")].members[0].deletedAt,
    ).toBeTruthy();
  });

  it("retains messages and members when clearing fails", async () => {
    const store = useRoomsStore();
    const snapshot = roomFixture();
    store.sync(snapshot, "channel-default");
    vi.mocked(clearRoom).mockRejectedValue(new Error("unavailable"));

    await expect(store.clear(snapshot.room.id, "channel-default")).rejects.toThrow("unavailable");
    expect(store.snapshots[store.snapshotKey(snapshot.room.id, "channel-default")]).toEqual(
      snapshot,
    );
  });

  it("updates the visible room name without changing its path", async () => {
    const store = useRoomsStore();
    const snapshot = roomFixture();
    store.rooms = [snapshot.room];
    store.sync(snapshot, "channel-default");
    vi.mocked(updateRoom).mockResolvedValue({ ...snapshot.room, name: "Renamed" });

    await store.update(snapshot.room.id, { name: "Renamed" });

    expect(updateRoom).toHaveBeenCalledWith(snapshot.room.id, { name: "Renamed" });
    expect(store.rooms[0]).toEqual({
      ...snapshot.room,
      name: "Renamed",
    });
    expect(store.rooms[0].projectPath).toBe(snapshot.room.projectPath);
  });

  it("preserves the input path and refreshes cached room paths across channels", async () => {
    const store = useRoomsStore();
    const snapshot = roomFixture();
    store.rooms = [snapshot.room];
    store.sync(snapshot, "channel-default");
    store.sync(roomFixture(), "other");
    const request = { name: "Moved", projectPath: " D:\\Other\\Project\\ " };
    const updated = {
      ...snapshot.room,
      name: request.name,
      rawProjectPath: request.projectPath,
      projectPath: "D:/Other/Project",
    };
    vi.mocked(updateRoom).mockResolvedValue(updated);

    await store.update(snapshot.room.id, request);

    expect(updateRoom).toHaveBeenCalledWith(snapshot.room.id, request);
    expect(store.rooms[0]).toEqual(updated);
    expect(store.snapshots[store.snapshotKey(snapshot.room.id, "channel-default")].room).toEqual(
      updated,
    );
    expect(store.snapshots[store.snapshotKey(snapshot.room.id, "other")].room).toEqual(updated);
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
    store.sync(first, "channel-default");
    store.sync(second, "channel-default");
    const topic = {
      id: "review",
      name: "审查",
      description: "",
      createdAt: "2026-11-06T10:00:00Z",
      deletedAt: null,
    };
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

    await store.createTopic(first.room.id, { name: "审查", description: "" }, "channel-default");

    expect(
      store.snapshots[store.snapshotKey(first.room.id, "channel-default")].topics,
    ).toContainEqual(topic);
    expect(store.snapshots[store.snapshotKey(first.room.id, "channel-default")].messages).toEqual(
      first.messages,
    );
    expect(store.snapshots[store.snapshotKey(first.room.id, "channel-default")].eventId).toBe(10);
    expect(
      store.snapshots[store.snapshotKey(first.room.id, "channel-default")].positions[0].seq,
    ).toBe(1);
    expect(store.snapshots[store.snapshotKey(second.room.id, "channel-default")].topics).toEqual(
      [],
    );
    store.syncMetadata({ ...first, topics: [], eventId: 15 }, "channel-default");
    expect(
      store.snapshots[store.snapshotKey(first.room.id, "channel-default")].topics,
    ).toContainEqual(topic);
  });

  it("applies topic creation only to the explicitly selected channel", async () => {
    const store = useRoomsStore();
    const original = roomFixture();
    const channel = { ...original, topics: [], members: [], messages: [] };
    store.sync(original, "channel-default");
    store.sync(channel, "channel-api");
    const topic = {
      id: "review",
      name: "Review",
      description: "",
      createdAt: null,
      deletedAt: null,
    };
    vi.mocked(addRoomTopic).mockResolvedValue({
      ...topic,
      metadata: { ...channel, topics: [topic], eventId: 20 },
    });

    await store.createTopic(original.room.id, { name: "Review", description: "" }, "channel-api");

    expect(addRoomTopic).toHaveBeenCalledWith(
      original.room.id,
      { name: "Review", description: "" },
      "channel-api",
    );
    expect(store.snapshots[store.snapshotKey(original.room.id, "channel-api")].topics).toEqual([
      topic,
    ]);
    expect(store.snapshots[store.snapshotKey(original.room.id, "channel-default")].topics).toEqual(
      original.topics,
    );
  });

  it("prepends earlier pages once while retaining live delivery updates and global totals", () => {
    const store = useRoomsStore();
    const initial = roomFixture();
    const earlier = { ...initial.messages[0], id: "older", seq: 0 };
    const previous = structuredClone(initial.messages[0]);
    store.sync(initial, "channel-default");
    const liveMessage = { ...initial.messages[0], content: "已更新投递状态" };
    store.applyMessages(initial.room.id, [liveMessage], {}, "channel-default");
    store.prependPage(
      initial.room.id,
      {
        messages: [earlier, previous],
        hasMore: true,
        nextBeforeSeq: 0,
        hasNewer: true,
      },
      "channel-default",
    );

    const snapshot = store.snapshots[store.snapshotKey(initial.room.id, "channel-default")];
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

  it("applies delivery updates and appends new messages matching topic and member", () => {
    const store = useRoomsStore();
    const initial = roomFixture();
    store.sync(initial, "channel-default");
    const newest = { ...initial.messages[1], id: "msg-0003", seq: 3 };
    const unrelated = { ...newest, id: "msg-0004", seq: 4, senderId: "frontend-worker" };
    store.applyMessages(
      initial.room.id,
      [newest, unrelated],
      {
        topicId: "backend",
        memberId: "backend-worker",
      },
      "channel-default",
    );
    expect(
      store.snapshots[store.snapshotKey(initial.room.id, "channel-default")].messages.map(
        (message) => message.seq,
      ),
    ).toEqual([1, 2, 3]);

    store.snapshots[store.snapshotKey(initial.room.id, "channel-default")].hasNewer = true;
    store.applyMessages(
      initial.room.id,
      [
        { ...newest, content: "更新已加载消息" },
        { ...newest, id: "msg-0005", seq: 5 },
      ],
      {},
      "channel-default",
    );
    expect(
      store.snapshots[store.snapshotKey(initial.room.id, "channel-default")].messages.at(-1)
        ?.content,
    ).toBe("更新已加载消息");
    expect(
      store.snapshots[store.snapshotKey(initial.room.id, "channel-default")].messages.map(
        (message) => message.seq,
      ),
    ).toEqual([1, 2, 3]);
  });

  it("only appends messages containing the literal search keyword", () => {
    const store = useRoomsStore();
    const initial = roomFixture();
    store.sync({ ...initial, messages: [] }, "channel-default");
    const matching = { ...initial.messages[0], content: "接口%_ 已确认" };
    const unrelated = { ...initial.messages[1], content: "接口变更" };

    store.applyMessages(
      initial.room.id,
      [matching, unrelated],
      { keyword: "接口%_" },
      "channel-default",
    );

    expect(store.snapshots[store.snapshotKey(initial.room.id, "channel-default")].messages).toEqual(
      [matching],
    );
  });

  it.each([
    { query: {}, expected: [3, 4, 5, 6, 7] },
    { query: { topicId: "backend" }, expected: [3, 4] },
    { query: { memberId: "backend-worker" }, expected: [3, 4, 5, 6] },
    { query: { memberId: "user" }, expected: [5, 7] },
    { query: { topicId: "backend", memberId: "backend-worker" }, expected: [3, 4] },
    { query: { topicId: "frontend", memberId: "backend-worker" }, expected: [5] },
    { query: { topicId: "frontend", memberId: "user" }, expected: [5] },
    { query: { topicId: "backend", memberId: "user" }, expected: [] },
  ])("matches topic and member filters: $query", ({ query, expected }) => {
    const store = useRoomsStore();
    const initial = roomFixture();
    const sent = { ...initial.messages[1], id: "sent", seq: 3 };
    const received = {
      ...sent,
      id: "received",
      seq: 4,
      senderId: "frontend-worker",
      mentionedMemberIds: [],
      recipientIds: ["backend-worker", "test-worker"],
    };
    const otherTopic = {
      ...sent,
      id: "other-topic",
      seq: 5,
      topicIds: ["frontend"],
      mentionedMemberIds: ["user"],
      recipientIds: ["user"],
    };
    const direct = { ...received, id: "direct", seq: 6, topicIds: [] };
    const userOnly = {
      ...otherTopic,
      id: "user-only",
      seq: 7,
      senderId: "frontend-worker",
      topicIds: [],
      deliveries: [],
    };
    store.sync({ ...initial, messages: [] }, "channel-default");
    store.applyMessages(
      initial.room.id,
      [sent, received, otherTopic, direct, userOnly],
      query,
      "channel-default",
    );

    expect(
      store.snapshots[store.snapshotKey(initial.room.id, "channel-default")].messages.map(
        (message) => message.seq,
      ),
    ).toEqual(expected);
  });
});
