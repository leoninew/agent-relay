import { beforeEach, describe, expect, it, vi } from "vitest";

import { loadRoomEventUpdates } from "@/domains/room/roomEventUpdates";
import { fetchRoomActivity, fetchRoomMessageUpdates, fetchRoomMetadata } from "@/services/roomApi";
import type { RoomEvent } from "@/services/roomApi";
import { roomFixture } from "../../fixtures/room";

vi.mock("@/services/roomApi", () => ({
  fetchRoomActivity: vi.fn(),
  fetchRoomMessageUpdates: vi.fn(),
  fetchRoomMetadata: vi.fn(),
}));

describe("event update queries", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(fetchRoomActivity).mockResolvedValue(roomFixture());
    vi.mocked(fetchRoomMetadata).mockResolvedValue(roomFixture());
    vi.mocked(fetchRoomMessageUpdates).mockResolvedValue([]);
  });

  it("batches changed IDs with current filters and retains only changed visible or detail messages", async () => {
    const events: RoomEvent[] = [
      { eventId: 11, kind: "message", entityId: "new", messageId: "new" },
      { eventId: 12, kind: "delivery", entityId: "delivery", messageId: "new" },
      { eventId: 13, kind: "delivery", entityId: "delivery2", messageId: "detail" },
    ];
    const query = { topicId: "frontend", memberId: "worker", keyword: "needle", beforeSeq: 5 };
    const signal = new AbortController().signal;
    await loadRoomEventUpdates(
      "room",
      "channel",
      events,
      query,
      new Set(["detail", "old"]),
      signal,
    );
    expect(fetchRoomMessageUpdates).toHaveBeenCalledOnce();
    expect(fetchRoomMessageUpdates).toHaveBeenCalledWith(
      "room",
      {
        messageIds: ["new", "detail"],
        retainedIds: ["detail"],
        topicId: "frontend",
        memberId: "worker",
        keyword: "needle",
      },
      signal,
      "channel",
    );
    expect(fetchRoomActivity).toHaveBeenCalledOnce();
    expect(fetchRoomActivity).toHaveBeenCalledWith("room", signal, "channel");
    expect(fetchRoomMetadata).not.toHaveBeenCalled();
  });

  it("loads resources for member changes without issuing an empty message query", async () => {
    await loadRoomEventUpdates(
      "room",
      "channel",
      [{ eventId: 11, kind: "member", entityId: "worker", messageId: null }],
      {},
      new Set(),
    );
    expect(fetchRoomMetadata).toHaveBeenCalledOnce();
    expect(fetchRoomMetadata).toHaveBeenCalledWith("room", undefined, "channel");
    expect(fetchRoomActivity).not.toHaveBeenCalled();
    expect(fetchRoomMessageUpdates).not.toHaveBeenCalled();
  });

  it("propagates a failed batch so the caller does not advance its event cursor", async () => {
    vi.mocked(fetchRoomMessageUpdates).mockRejectedValue(new Error("unavailable"));
    await expect(
      loadRoomEventUpdates(
        "room",
        "channel",
        [{ eventId: 11, kind: "message", entityId: "new", messageId: "new" }],
        {},
        new Set(),
      ),
    ).rejects.toThrow("unavailable");
  });
});
