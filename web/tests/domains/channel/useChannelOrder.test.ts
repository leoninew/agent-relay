import { effectScope, ref } from "vue";
import type { EffectScope } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useChannelOrder } from "@/domains/channel/useChannelOrder";
import type { Channel } from "@/services/channelApi";
import type * as storage from "@/services/storage";
import { roomCacheKey } from "@/services/cacheKeys";

const DEFAULT_CHANNEL_ID = "0000000000123";
const saved = vi.hoisted(() => new Map<string, string>());
vi.mock("@/services/storage", async (importOriginal) => ({
  ...(await importOriginal<typeof storage>()),
  browserStorage: () => ({
    getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => saved.set(key, value),
    removeItem: (key: string) => saved.delete(key),
  }),
}));

function channel(id: string): Channel {
  return {
    id,
    roomId: "room",
    name: id,
    description: "",
    workingPath: "D:/work/conflua",
    isDefault: id === DEFAULT_CHANNEL_ID,
    status: "active",
    workspaceKind: "existing",
    createdAt: null,
  };
}

describe("channel order", () => {
  let scope: EffectScope;

  beforeEach(() => {
    saved.clear();
    scope = effectScope();
  });
  afterEach(() => scope.stop());

  it("pins the default channel even when the previously saved order moved it", () => {
    saved.set(roomCacheKey("room", "channels-order"), '["second","channel-default","first"]');
    const channels = [channel("first"), channel(DEFAULT_CHANNEL_ID), channel("second")];
    const order = scope.run(() =>
      useChannelOrder(
        () => "room",
        () => channels,
      ),
    )!;

    expect(order.defaultChannel.value?.id).toBe(DEFAULT_CHANNEL_ID);
    expect(order.sortableChannels.value.map((item) => item.id)).toEqual(["second", "first"]);
    expect(order.availableChannels.value.map((item) => item.id)).toEqual([
      DEFAULT_CHANNEL_ID,
      "second",
      "first",
    ]);

    order.sortableChannels.value = order.sortableChannels.value.toReversed();
    expect(saved.get(roomCacheKey("room", "channels-order"))).toBe('["first","second"]');
    expect(order.availableChannels.value[0].id).toBe(DEFAULT_CHANNEL_ID);
    expect(channels.map((item) => item.id)).toEqual(["first", DEFAULT_CHANNEL_ID, "second"]);
  });

  it("prevents keyboard moves from moving the default channel or crossing its position", () => {
    const channels = [channel(DEFAULT_CHANNEL_ID), channel("first"), channel("second")];
    const order = scope.run(() =>
      useChannelOrder(
        () => "room",
        () => channels,
      ),
    )!;

    order.moveChannel(DEFAULT_CHANNEL_ID, 1);
    order.moveChannel("first", -1);
    expect(order.availableChannels.value).toEqual(channels);

    order.moveChannel("second", -1);
    expect(order.availableChannels.value.map((item) => item.id)).toEqual([
      DEFAULT_CHANNEL_ID,
      "second",
      "first",
    ]);
  });

  it("restores each room's order while keeping the default channel first", () => {
    const roomId = ref("room-a");
    const channels = [channel(DEFAULT_CHANNEL_ID), channel("first"), channel("second")];
    const order = scope.run(() =>
      useChannelOrder(
        () => roomId.value,
        () => channels,
      ),
    )!;

    order.moveChannel("second", -1);
    roomId.value = "room-b";
    expect(order.availableChannels.value).toEqual(channels);
    roomId.value = "room-a";
    expect(order.availableChannels.value.map((item) => item.id)).toEqual([
      DEFAULT_CHANNEL_ID,
      "second",
      "first",
    ]);
  });
});
