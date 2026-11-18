import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_CHANNEL_ID } from "@/domains/channel/channelRoutes";
import type { Channel } from "@/services/channelApi";
import {
  archiveChannel,
  createChannel,
  deleteChannel,
  fetchChannel,
  fetchChannels,
  updateChannel,
} from "@/services/channelApi";
import { useChannelsStore } from "@/stores/channels";
import { roomCacheKey } from "@/services/cacheKeys";

vi.mock("@/services/channelApi", () => ({
  archiveChannel: vi.fn(),
  createChannel: vi.fn(),
  deleteChannel: vi.fn(),
  fetchChannel: vi.fn(),
  fetchChannels: vi.fn(),
  updateChannel: vi.fn(),
}));

function channel(overrides: Partial<Channel> = {}): Channel {
  return {
    id: DEFAULT_CHANNEL_ID,
    roomId: "room-1",
    name: "默认",
    description: "",
    workingPath: "D:/work/conflua",
    isDefault: true,
    status: "active",
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

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads channels once and excludes archived channels from selection", async () => {
    vi.mocked(fetchChannels).mockResolvedValue([
      channel(),
      channel({ id: "archived", isDefault: false, status: "archived" }),
      channel({ id: "deleted", isDefault: false, archivedAt: "2026-01-01T00:00:00Z" }),
    ]);
    const store = useChannelsStore();

    await store.load("room-1");
    await store.load("room-1");

    expect(fetchChannels).toHaveBeenCalledOnce();
    expect(store.activeChannels("room-1").map((item) => item.id)).toEqual([DEFAULT_CHANNEL_ID]);
    expect(store.resolveChannelId("room-1", DEFAULT_CHANNEL_ID)).toBe(DEFAULT_CHANNEL_ID);
    expect(store.resolveChannelId("room-1", "archived")).toBeUndefined();
    expect(store.resolveChannelId("room-1", "deleted")).toBeUndefined();
    expect(store.resolveChannelId("room-1", "missing")).toBeUndefined();
  });

  it("restores the selected channel per room after the store is recreated", () => {
    const values = new Map<string, string>();
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => void values.delete(key),
      },
    });
    const firstStore = useChannelsStore();
    firstStore.remember("room-1", "channel-api");
    firstStore.remember("room-2", "channel-design");

    setActivePinia(createPinia());
    const restoredStore = useChannelsStore();

    expect(restoredStore.preferredChannel("room-1")).toBe("channel-api");
    expect(restoredStore.preferredChannel("room-2")).toBe("channel-design");
  });

  it("refreshes a revisited room and drops a selection archived elsewhere", async () => {
    const previous = channel({ id: "channel-api", isDefault: false });
    const added = channel({ id: "channel-new", isDefault: false });
    const other = channel({ roomId: "room-2" });
    vi.mocked(fetchChannels)
      .mockResolvedValueOnce([channel(), previous])
      .mockResolvedValueOnce([other])
      .mockResolvedValueOnce([channel(), added]);
    const store = useChannelsStore();
    await store.load("room-1");
    store.remember("room-1", previous.id);
    await store.load("room-2");

    await store.load("room-1", true);

    expect(fetchChannels).toHaveBeenCalledTimes(3);
    expect(store.activeChannels("room-1").map((item) => item.id)).toEqual([
      DEFAULT_CHANNEL_ID,
      added.id,
    ]);
    expect(store.preferredChannel("room-1")).toBeUndefined();
    expect(store.activeChannels("room-2")).toEqual([other]);
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
    expect(store.preferredChannel("room-1")).toBe("channel-new");
  });

  it("updates channel details without changing channel order or current selection", async () => {
    const store = useChannelsStore();
    const target = channel({ id: "channel-api", isDefault: false });
    store.byRoom[roomCacheKey("room-1", "channels")] = [channel(), target];
    store.remember("room-1", target.id);
    const request = { name: "Backend", description: "API changes" };
    vi.mocked(updateChannel).mockResolvedValue({ ...target, ...request });

    await store.update("room-1", target.id, request);

    expect(updateChannel).toHaveBeenCalledWith("room-1", target.id, request);
    expect(store.channels("room-1").map((item) => item.id)).toEqual([
      DEFAULT_CHANNEL_ID,
      target.id,
    ]);
    expect(store.channel("room-1", target.id)).toEqual({ ...target, ...request });
    expect(store.preferredChannel("room-1")).toBe(target.id);
    vi.mocked(updateChannel).mockRejectedValue(new Error("Name conflict"));
    await expect(
      store.update("room-1", target.id, { name: "Duplicate", description: "" }),
    ).rejects.toThrow("Name conflict");
    expect(store.channel("room-1", target.id)?.name).toBe("Backend");
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
    store.byRoom[roomCacheKey("room-1", "channels")] = [
      channel(),
      channel({ id: "channel-api", isDefault: false }),
    ];
    store.byRoom[roomCacheKey("room-2", "channels")] = [channel({ roomId: "room-2" })];
    store.remember("room-1", "channel-api");
    store.remember("room-2", DEFAULT_CHANNEL_ID);
    vi.mocked(deleteChannel).mockResolvedValue();

    await store.remove("room-1", "channel-api");

    expect(deleteChannel).toHaveBeenCalledWith("room-1", "channel-api");
    expect(store.activeChannels("room-1").map((item) => item.id)).toEqual([DEFAULT_CHANNEL_ID]);
    expect(store.resolveChannelId("room-1", "channel-api")).toBeUndefined();
    expect(store.preferredChannel("room-1")).toBeUndefined();
    expect(store.channel("room-2", DEFAULT_CHANNEL_ID)?.roomId).toBe("room-2");
    expect(store.preferredChannel("room-2")).toBe(DEFAULT_CHANNEL_ID);
  });

  it("retains the channel and selection when deletion is rejected", async () => {
    const store = useChannelsStore();
    const target = channel({ id: "channel-api", isDefault: false });
    store.byRoom[roomCacheKey("room-1", "channels")] = [channel(), target];
    store.remember("room-1", target.id);
    vi.mocked(deleteChannel).mockRejectedValue(new Error("Channel is busy"));

    await expect(store.remove("room-1", target.id)).rejects.toThrow("Channel is busy");

    expect(store.channel("room-1", target.id)).toEqual(target);
    expect(store.preferredChannel("room-1")).toBe(target.id);
  });

  it("archives by status without removing cached data or changing the current channel", async () => {
    const store = useChannelsStore();
    const target = channel({ id: "channel-api", isDefault: false });
    store.byRoom[roomCacheKey("room-1", "channels")] = [channel(), target];
    store.byRoom[roomCacheKey("room-2", "channels")] = [channel({ roomId: "room-2" })];
    store.remember("room-1", DEFAULT_CHANNEL_ID);
    const archived = { ...target, name: "Finished API", status: "archived" } as const;
    vi.mocked(archiveChannel).mockResolvedValue(archived);

    await store.archive("room-1", target.id, archived.name);

    expect(archiveChannel).toHaveBeenCalledWith("room-1", target.id, archived.name);
    expect(store.channel("room-1", target.id)).toEqual(archived);
    expect(store.resolveChannelId("room-1", target.id)).toBeUndefined();
    expect(store.preferredChannel("room-1")).toBe(DEFAULT_CHANNEL_ID);
    expect(store.activeChannels("room-2")).toHaveLength(1);
    expect(deleteChannel).not.toHaveBeenCalled();
  });

  it("keeps the channel available when archiving fails", async () => {
    const store = useChannelsStore();
    const target = channel({ id: "channel-api", isDefault: false });
    store.byRoom[roomCacheKey("room-1", "channels")] = [channel(), target];
    vi.mocked(archiveChannel).mockRejectedValue(new Error("Archive failed"));

    await expect(store.archive("room-1", target.id, "Finished API")).rejects.toThrow(
      "Archive failed",
    );

    expect(store.resolveChannelId("room-1", target.id)).toBe(target.id);
    expect(store.channel("room-1", target.id)).toEqual(target);
  });
});
