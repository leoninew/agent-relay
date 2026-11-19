import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useChannelCreation } from "@/domains/channel/useChannelCreation";
import { ApiClientError } from "@/services/api";
import type { Channel } from "@/services/channelApi";
import { createChannel, fetchChannel, issueChannelId } from "@/services/channelApi";

const SOURCE_CHANNEL_ID = "0000000000123";
const ISSUED_CHANNEL_ID = "0000000000124";

vi.mock("@/services/channelApi", () => ({
  archiveChannel: vi.fn(),
  createChannel: vi.fn(),
  deleteChannel: vi.fn(),
  fetchChannel: vi.fn(),
  fetchChannels: vi.fn(),
  issueChannelId: vi.fn(),
}));

function channel(id: string, worktree = false): Channel {
  return {
    id,
    roomId: "room-1",
    name: "API",
    description: "Backend work",
    workingPath: "D:/work/conflua",
    isDefault: false,
    status: "active",
    workspaceKind: worktree ? "worktree" : "existing",
    createdAt: null,
  };
}

describe("channel creation", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    setActivePinia(createPinia());
    vi.mocked(issueChannelId).mockResolvedValue(ISSUED_CHANNEL_ID);
    vi.mocked(createChannel).mockImplementation(async (_room, request) =>
      channel(request.channelId, request.useWorktree),
    );
  });

  it("issues the ID before creating once with that exact ID and no worktree by default", async () => {
    const creation = useChannelCreation(
      () => "room-1",
      () => SOURCE_CHANNEL_ID,
    );
    creation.name.value = " API ";
    creation.description.value = " Backend work ";

    expect(creation.useWorktree.value).toBe(false);
    expect(await creation.submit()).toBe(true);
    expect(issueChannelId).toHaveBeenCalledOnce();
    expect(issueChannelId).toHaveBeenCalledWith("room-1");
    expect(vi.mocked(issueChannelId).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(createChannel).mock.invocationCallOrder[0],
    );
    expect(createChannel).toHaveBeenCalledOnce();
    expect(createChannel).toHaveBeenCalledWith("room-1", {
      name: "API",
      description: "Backend work",
      channelId: ISSUED_CHANNEL_ID,
      useWorktree: false,
    });
  });

  it("creates a worktree channel without a base override", async () => {
    const creation = useChannelCreation(
      () => "room-1",
      () => SOURCE_CHANNEL_ID,
    );
    creation.name.value = "API";
    creation.useWorktree.value = true;

    expect(await creation.submit()).toBe(true);
    expect(createChannel).toHaveBeenCalledOnce();
    expect(createChannel).toHaveBeenCalledWith("room-1", {
      name: "API",
      description: "",
      channelId: creation.channelId.value,
      useWorktree: true,
    });
  });

  it("returns a rejected request to the form", async () => {
    vi.mocked(createChannel).mockRejectedValue(
      new ApiClientError("Name conflict", "http_error", {
        code: "channel_name_conflict",
        status: 409,
      }),
    );
    const creation = useChannelCreation(
      () => "room-1",
      () => SOURCE_CHANNEL_ID,
    );
    creation.name.value = "API";

    expect(await creation.submit()).toBe(false);
    expect(creation.step.value).toBe("form");
    expect(creation.busy.value).toBe(false);
    expect(creation.error.value).toBe("errors.channel_name_conflict");
  });

  it("restores an unknown request and looks up the same ID without sending another create", async () => {
    const saved = new Map<string, string>();
    const storage = {
      getItem: (key: string) => saved.get(key) ?? null,
      setItem: (key: string, value: string) => saved.set(key, value),
      removeItem: (key: string) => saved.delete(key),
    };
    vi.mocked(createChannel).mockRejectedValue(new Error("timeout"));
    const first = useChannelCreation(
      () => "room-1",
      () => SOURCE_CHANNEL_ID,
      storage,
    );
    first.name.value = "API";
    first.description.value = "Backend work";
    expect(await first.submit()).toBe(false);
    expect(first.error.value).toBe("errors.channelCreate");
    const channelId = first.channelId.value!;

    setActivePinia(createPinia());
    const restored = useChannelCreation(
      () => "room-1",
      () => SOURCE_CHANNEL_ID,
      storage,
    );
    expect(restored.step.value).toBe("unknown");
    expect(restored.description.value).toBe("Backend work");
    expect(restored.channelId.value).toBe(channelId);
    expect(await restored.submit()).toBe(false);
    expect(createChannel).toHaveBeenCalledOnce();
    expect(
      useChannelCreation(
        () => "room-2",
        () => SOURCE_CHANNEL_ID,
        storage,
      ).step.value,
    ).toBe("form");
    expect(
      useChannelCreation(
        () => "room-1",
        () => "channel-other",
        storage,
      ).step.value,
    ).toBe("form");

    vi.mocked(fetchChannel).mockResolvedValue(channel(channelId));
    expect(await restored.lookup(channelId)).toBe(true);
    expect(fetchChannel).toHaveBeenCalledWith("room-1", channelId);
    expect(issueChannelId).toHaveBeenCalledOnce();
    expect(createChannel).toHaveBeenCalledOnce();
    expect(saved.size).toBe(0);
  });
});
