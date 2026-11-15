import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_CHANNEL_ID } from "@/domains/channel/channelRoutes";
import type { Channel } from "@/services/channelApi";
import { createChannel, deleteChannel, fetchChannel, fetchChannels } from "@/services/channelApi";
import { useChannelsStore } from "@/stores/channels";

vi.mock("@/services/channelApi", () => ({
  createChannel: vi.fn(),
  deleteChannel: vi.fn(),
  fetchChannel: vi.fn(),
  fetchChannels: vi.fn(),
}));

function channel(overrides: Partial<Channel> = {}): Channel {
  return {
    id: DEFAULT_CHANNEL_ID,
    roomId: "room-1",
    name: "默认",
    description: "",
    workingPath: "D:/work/agent-relay",
    isDefault: true,
    workspaceKind: "existing",
    createdAt: null,
    ...overrides,
  };
}

describe("channel state", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    setActivePinia(createPinia());
  });

  it("loads channels once and excludes archived channels from selection", async () => {
    vi.mocked(fetchChannels).mockResolvedValue([
      channel(),
      channel({ id: "archived", isDefault: false, archivedAt: "2026-01-01T00:00:00Z" }),
    ]);
    const store = useChannelsStore();

    await store.load("room-1");
    await store.load("room-1");

    expect(fetchChannels).toHaveBeenCalledOnce();
    expect(store.activeChannels("room-1").map((item) => item.id)).toEqual([DEFAULT_CHANNEL_ID]);
    expect(store.resolveChannelId("room-1", DEFAULT_CHANNEL_ID)).toBe(DEFAULT_CHANNEL_ID);
    expect(store.resolveChannelId("room-1", "archived")).toBeUndefined();
    expect(store.resolveChannelId("room-1", "missing")).toBeUndefined();
  });

  it("stores the created channel and its description", async () => {
    vi.mocked(createChannel).mockResolvedValue(
      channel({ id: "channel-new", name: "API", description: "Backend work", isDefault: false }),
    );
    const store = useChannelsStore();
    const request = {
      name: "API",
      description: "Backend work",
      channelId: "channel-new",
      useWorktree: false,
    };

    await store.create("room-1", request);

    expect(createChannel).toHaveBeenCalledWith("room-1", request);
    expect(store.channel("room-1", "channel-new")?.description).toBe("Backend work");
    expect(store.recent["room-1"]).toBe("channel-new");
  });

  it("looks up an unconfirmed channel without creating another one", async () => {
    vi.mocked(fetchChannel).mockResolvedValue(
      channel({ id: "channel-new", name: "API", isDefault: false }),
    );
    const store = useChannelsStore();

    await store.lookup("room-1", "channel-new");

    expect(fetchChannel).toHaveBeenCalledWith("room-1", "channel-new");
    expect(store.channel("room-1", "channel-new")?.name).toBe("API");
    expect(createChannel).not.toHaveBeenCalled();
  });

  it("removes the deleted channel from selection while preserving other channels and rooms", async () => {
    const store = useChannelsStore();
    store.byRoom["room-1"] = [channel(), channel({ id: "channel-api", isDefault: false })];
    store.byRoom["room-2"] = [channel({ roomId: "room-2" })];
    store.remember("room-1", "channel-api");
    store.remember("room-2", DEFAULT_CHANNEL_ID);
    vi.mocked(deleteChannel).mockResolvedValue();

    await store.remove("room-1", "channel-api");

    expect(deleteChannel).toHaveBeenCalledWith("room-1", "channel-api");
    expect(store.activeChannels("room-1").map((item) => item.id)).toEqual([DEFAULT_CHANNEL_ID]);
    expect(store.resolveChannelId("room-1", "channel-api")).toBeUndefined();
    expect(store.recent["room-1"]).toBeUndefined();
    expect(store.channel("room-2", DEFAULT_CHANNEL_ID)?.roomId).toBe("room-2");
    expect(store.recent["room-2"]).toBe(DEFAULT_CHANNEL_ID);
  });

  it("retains the channel and selection when deletion is rejected", async () => {
    const store = useChannelsStore();
    const target = channel({ id: "channel-api", isDefault: false });
    store.byRoom["room-1"] = [channel(), target];
    store.remember("room-1", target.id);
    vi.mocked(deleteChannel).mockRejectedValue(new Error("Channel is busy"));

    await expect(store.remove("room-1", target.id)).rejects.toThrow("Channel is busy");

    expect(store.channel("room-1", target.id)).toEqual(target);
    expect(store.recent["room-1"]).toBe(target.id);
  });
});
