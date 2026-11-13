import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/services/api";
import { fetchAppInfo } from "@/services/appInfoApi";

describe("application information", () => {
  const originalAdapter = apiClient.defaults.adapter;

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
  });

  it("requests the backend version with a bounded timeout", async () => {
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: { version: "1.2.3" },
      headers: { "content-type": "application/json" },
      status: 200,
      statusText: "OK",
    }));
    apiClient.defaults.adapter = adapter as AxiosAdapter;
    await expect(fetchAppInfo()).resolves.toEqual({ version: "1.2.3" });
    expect(adapter).toHaveBeenCalledWith(
      expect.objectContaining({ method: "get", url: "/api/app", timeout: 5000 }),
    );
  });
});
