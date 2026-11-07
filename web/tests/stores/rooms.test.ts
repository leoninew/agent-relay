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

describe("room catalogs", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    setActivePinia(createPinia());
  });

  it("reuses created topics only within their project room", async () => {
    const store = useRoomsStore();
    const first = roomFixture();
    const second = {
      ...roomFixture(),
      room: { ...first.room, id: "other-project" },
      topics: [],
      members: [],
    };
    store.syncCatalog(first);
    store.syncCatalog(second);
    const topic = { id: "review", name: "审查", description: "", messageCount: 0, deletedAt: null };
    vi.mocked(addRoomTopic).mockResolvedValue(topic);

    await store.createTopic(first.room.id, { name: "审查", description: "" });

    expect(store.catalogs[first.room.id].topics).toContainEqual(topic);
    expect(store.catalogs[second.room.id]).toEqual({ topics: [] });
  });
});
