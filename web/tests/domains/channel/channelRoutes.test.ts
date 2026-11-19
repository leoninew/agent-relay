import { describe, expect, it } from "vitest";

import { draftScope, roomResourcePath, snapshotScope } from "@/domains/channel/channelRoutes";

const DEFAULT_CHANNEL_ID = "0000000000123";

describe("channel scoping", () => {
  it("uses explicit channel paths for the default channel", () => {
    expect(roomResourcePath("room/one", DEFAULT_CHANNEL_ID)).toBe(
      `/api/room/room%2Fone/channel/${DEFAULT_CHANNEL_ID}/snapshot`,
    );
    expect(roomResourcePath("room/one", DEFAULT_CHANNEL_ID, "/message")).toBe(
      `/api/room/room%2Fone/channel/${DEFAULT_CHANNEL_ID}/message`,
    );
    expect(roomResourcePath("room/one", DEFAULT_CHANNEL_ID, "/event/stream")).toBe(
      `/api/room/room%2Fone/channel/${DEFAULT_CHANNEL_ID}/event/stream`,
    );
  });

  it("uses explicit channel paths for non-default channels", () => {
    expect(roomResourcePath("room/one", "channel-a")).toBe(
      "/api/room/room%2Fone/channel/channel-a/snapshot",
    );
    expect(roomResourcePath("room/one", "channel/a", "/queue")).toBe(
      "/api/room/room%2Fone/channel/channel%2Fa/queue",
    );
  });

  it("separates non-default snapshot and draft scopes", () => {
    expect(snapshotScope("room", DEFAULT_CHANNEL_ID)).toBe(
      `conflua:room:room:channel:${DEFAULT_CHANNEL_ID}`,
    );
    expect(snapshotScope("room", "channel-a")).toBe("conflua:room:room:channel:channel-a");
    expect(draftScope("room", "channel-a")).toBe("conflua:room:room:channel:channel-a");
    expect(draftScope("room", "channel-b")).not.toBe(draftScope("room", "channel-a"));
    expect(snapshotScope("room:other", "channel-a")).not.toBe(
      snapshotScope("room", "other:channel-a"),
    );
  });
});
