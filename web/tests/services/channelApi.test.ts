import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/services/api";
import { deleteChannel } from "@/services/channelApi";

describe("channel API", () => {
  const originalAdapter = apiClient.defaults.adapter;

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
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
});
