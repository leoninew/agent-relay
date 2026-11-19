import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/services/api";
import {
  archiveChannel,
  deleteChannel,
  issueChannelId,
  updateChannel,
} from "@/services/channelApi";

describe("channel API", () => {
  const originalAdapter = apiClient.defaults.adapter;

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
  });

  it("issues a channel ID with a bodyless POST at the room's issue-id endpoint", async () => {
    const channelId = "0000000000124";
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: { channelId },
      headers: { "content-type": "application/json" },
      status: 200,
      statusText: "OK",
    }));
    apiClient.defaults.adapter = adapter as AxiosAdapter;

    await expect(issueChannelId("0000000000122")).resolves.toBe(channelId);

    expect(adapter).toHaveBeenCalledOnce();
    expect(adapter).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "post",
        url: "/api/room/0000000000122/channel/issue-id",
        data: undefined,
      }),
    );
  });

  it("updates only metadata at an escaped channel URL", async () => {
    const request = { name: "API", description: "Backend" };
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: { id: "channel/api", ...request },
      headers: { "content-type": "application/json" },
      status: 200,
      statusText: "OK",
    }));
    apiClient.defaults.adapter = adapter as AxiosAdapter;
    await expect(updateChannel("room/one", "channel/api", request)).resolves.toMatchObject(request);
    expect(adapter).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "patch",
        url: "/api/room/room%2Fone/channel/channel%2Fapi",
        data: JSON.stringify(request),
      }),
    );
  });

  it("deletes an escaped channel identity and accepts an empty 204 response", async () => {
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: "",
      headers: {},
      status: 204,
      statusText: "No Content",
    }));
    apiClient.defaults.adapter = adapter as AxiosAdapter;

    await expect(deleteChannel("room/one", "channel/api")).resolves.toBeUndefined();

    expect(adapter).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "delete",
        url: "/api/room/room%2Fone/channel/channel%2Fapi",
      }),
    );
  });

  it("sends the final name in the archive POST", async () => {
    const name = "Finished API";
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: { id: "channel/api", name, status: "archived" },
      headers: { "content-type": "application/json" },
      status: 200,
      statusText: "OK",
    }));
    apiClient.defaults.adapter = adapter as AxiosAdapter;

    await expect(archiveChannel("room/one", "channel/api", name)).resolves.toMatchObject({
      id: "channel/api",
      name,
      status: "archived",
    });
    expect(adapter).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "post",
        url: "/api/room/room%2Fone/channel/channel%2Fapi/archive",
        data: JSON.stringify({ name }),
      }),
    );
  });
});
