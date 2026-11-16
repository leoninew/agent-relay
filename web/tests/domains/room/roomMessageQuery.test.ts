import { describe, expect, it } from "vitest";

import { messageQueryKey, mergeRefreshedSnapshot } from "@/domains/room/roomMessageQuery";
import type { MessageQuery, RoomSnapshot } from "@/services/roomApi";

import { roomFixture } from "../../fixtures/room";

function snapshotWithMessages(sequences: number[]): RoomSnapshot {
  const snapshot = roomFixture();
  return {
    ...snapshot,
    messages: sequences.map((seq) => ({ ...snapshot.messages[0], id: `message-${seq}`, seq })),
  };
}

describe("message query ownership", () => {
  it("normalizes empty filters and ignores pagination within the same query", () => {
    expect(messageQueryKey("room", "channel", {})).toBe(
      messageQueryKey("room", "channel", { keyword: "  ", beforeSeq: 20, limit: 100 }),
    );
    expect(messageQueryKey("room", "channel", { topicId: "topic", keyword: " word " })).toBe(
      messageQueryKey("room", "channel", { keyword: "word", topicId: "topic" }),
    );
  });

  it.each<[string, string, MessageQuery]>([
    ["other-room", "channel", {}],
    ["room", "other-channel", {}],
    ["room", "channel", { topicId: "topic" }],
    ["room", "channel", { memberId: "member" }],
    ["room", "channel", { keyword: "word" }],
  ])("separates a changed query: %s / %s / %j", (roomId, channelId, query) => {
    expect(messageQueryKey(roomId, channelId, query)).not.toBe(
      messageQueryKey("room", "channel", {}),
    );
  });
});

describe("refreshing a loaded message window", () => {
  it("keeps loaded history and its cursor while applying refreshed messages and metadata", () => {
    const previous = {
      ...snapshotWithMessages([10, 11, 12]),
      hasMore: true,
      nextBeforeSeq: 10,
    };
    const incoming = { ...snapshotWithMessages([11, 12, 13]), eventId: 20, hasNewer: true };
    incoming.messages[0].content = "updated";

    const result = mergeRefreshedSnapshot(previous, incoming);

    expect(result.messages.map((message) => message.seq)).toEqual([10, 11, 12, 13]);
    expect(result.messages[1].content).toBe("updated");
    expect(result).toMatchObject({
      eventId: 20,
      hasMore: true,
      nextBeforeSeq: 10,
      hasNewer: true,
    });
    expect(previous.messages.map((message) => message.seq)).toEqual([10, 11, 12]);
  });

  it.each([{ sequences: [] }, { sequences: [100] }])(
    "replaces history when the server window has no overlap: $sequences",
    ({ sequences }) => {
      const incoming = snapshotWithMessages(sequences);
      const result = mergeRefreshedSnapshot(snapshotWithMessages([10, 11]), incoming);

      expect(result.messages).toEqual(incoming.messages);
      expect(result.hasMore).toBe(incoming.hasMore);
      expect(result.nextBeforeSeq).toBe(incoming.nextBeforeSeq);
    },
  );
});
