import { createPinia, setActivePinia } from "pinia";
import { effectScope, ref } from "vue";
import type { EffectScope } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_CHANNEL_ID } from "@/domains/channel/channelRoutes";
import { canArchiveChannel, useChannelArchive } from "@/domains/channel/useChannelArchive";
import { archiveChannel } from "@/services/channelApi";
import type { Channel } from "@/services/channelApi";
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
    id: "channel-api",
    roomId: "room",
    name: "API",
    description: "",
    workingPath: "D:/work/conflua",
    isDefault: false,
    status: "active",
    workspaceKind: "existing",
    createdAt: null,
    ...overrides,
  };
}

describe("channel archive confirmation", () => {
  let scope: EffectScope;

  beforeEach(() => {
    vi.resetAllMocks();
    setActivePinia(createPinia());
    scope = effectScope();
    useChannelsStore().byRoom[roomCacheKey("room", "channels")] = [
      channel({ id: DEFAULT_CHANNEL_ID, isDefault: true }),
      channel(),
    ];
  });
  afterEach(() => scope.stop());

  function controller() {
    const roomId = ref("room");
    const current = ref(DEFAULT_CHANNEL_ID);
    const locked = ref(false);
    const archive = scope.run(() =>
      useChannelArchive(
        () => roomId.value,
        () => current.value,
        () => locked.value,
      ),
    )!;
    return { archive, roomId, current, locked };
  }

  it("offers archiving only for active non-default channels other than the current one", () => {
    expect(canArchiveChannel(channel(), DEFAULT_CHANNEL_ID)).toBe(true);
    expect(canArchiveChannel(channel(), "channel-api")).toBe(false);
    expect(canArchiveChannel(channel({ isDefault: true }), DEFAULT_CHANNEL_ID)).toBe(false);
    expect(canArchiveChannel(channel({ status: "archived" }), DEFAULT_CHANNEL_ID)).toBe(false);
    expect(canArchiveChannel(channel({ archivedAt: "2026-11-17" }), DEFAULT_CHANNEL_ID)).toBe(
      false,
    );
    expect(canArchiveChannel(channel(), undefined)).toBe(false);
  });

  it("opens and cancels confirmation without sending a request", async () => {
    const { archive } = controller();
    archive.open(channel({ id: DEFAULT_CHANNEL_ID, isDefault: true }));
    expect(archive.target.value).toBeUndefined();
    archive.open(channel({ roomId: "other-room" }));
    expect(archive.target.value).toBeUndefined();
    archive.open(channel());
    expect(archive.target.value?.id).toBe("channel-api");
    expect(archiveChannel).not.toHaveBeenCalled();
    archive.close();
    expect(await archive.confirm("API")).toBe(false);
    expect(archiveChannel).not.toHaveBeenCalled();
  });

  it("confirms once, hides the archived channel and closes the dialog", async () => {
    let finish!: (value: Channel) => void;
    vi.mocked(archiveChannel).mockImplementation(
      () =>
        new Promise<Channel>((resolve) => {
          finish = resolve;
        }),
    );
    const { archive } = controller();
    archive.open(channel());
    const result = archive.confirm("Finished API");
    expect(archive.busy.value).toBe(true);
    expect(await archive.confirm("Finished API")).toBe(false);
    archive.close();
    expect(archive.target.value).toBeDefined();
    finish(channel({ name: "Finished API", status: "archived" }));

    expect(await result).toBe(true);
    expect(archiveChannel).toHaveBeenCalledOnce();
    expect(archiveChannel).toHaveBeenCalledWith("room", "channel-api", "Finished API");
    expect(archive.busy.value).toBe(false);
    expect(archive.target.value).toBeUndefined();
    expect(
      useChannelsStore()
        .activeChannels("room")
        .map((item) => item.id),
    ).toEqual([DEFAULT_CHANNEL_ID]);
  });

  it("retains the target after failure and allows retry", async () => {
    vi.mocked(archiveChannel).mockRejectedValueOnce(new Error("offline"));
    const { archive } = controller();
    archive.open(channel());
    expect(await archive.confirm("API")).toBe(false);
    expect(archive.error.value?.key).toBe("errors.channelArchive");
    expect(archive.target.value?.id).toBe("channel-api");
    expect(useChannelsStore().activeChannels("room")).toHaveLength(2);

    vi.mocked(archiveChannel).mockResolvedValue(channel({ status: "archived" }));
    expect(await archive.confirm("API")).toBe(true);
    expect(archive.error.value).toBeNull();
  });

  it("drops stale confirmation when the current channel or room changes", async () => {
    const { archive, current, roomId } = controller();
    archive.open(channel());
    current.value = "channel-api";
    expect(archive.target.value).toBeUndefined();
    expect(await archive.confirm("API")).toBe(false);
    archive.open(channel());
    expect(archive.target.value).toBeUndefined();
    current.value = DEFAULT_CHANNEL_ID;
    archive.open(channel());
    roomId.value = "other-room";
    expect(await archive.confirm("API")).toBe(false);
    expect(archiveChannel).not.toHaveBeenCalled();
  });

  it("rechecks latest status and busy state before sending", async () => {
    const { archive, locked } = controller();
    locked.value = true;
    archive.open(channel());
    expect(archive.target.value).toBeUndefined();
    locked.value = false;
    archive.open(channel());
    locked.value = true;
    expect(await archive.confirm("API")).toBe(false);
    locked.value = false;
    useChannelsStore().byRoom[roomCacheKey("room", "channels")][1].status = "archived";
    expect(await archive.confirm("API")).toBe(false);
    expect(archive.target.value).toBeUndefined();
    expect(archiveChannel).not.toHaveBeenCalled();
  });
});
