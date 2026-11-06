import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/services/api";
import { fetchGreeting } from "@/services/greetingApi";

const adapterMock = vi.fn();
let originalAdapter: AxiosAdapter | AxiosAdapter[] | undefined;

function mockResponse<T>(data: T): AxiosResponse<T> {
  return {
    config: {} as InternalAxiosRequestConfig,
    data,
    headers: { "content-type": "application/json" },
    status: 200,
    statusText: "",
  };
}

describe("fetchGreeting", () => {
  beforeEach(() => {
    adapterMock.mockReset();
    originalAdapter = apiClient.defaults.adapter;
    apiClient.defaults.adapter = adapterMock as AxiosAdapter;
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
  });

  it("requests the FastAPI greeting endpoint with Axios query parameters", async () => {
    adapterMock.mockResolvedValue(mockResponse({ text: "Hello, Ada Lovelace!" }));

    await expect(fetchGreeting("Ada Lovelace")).resolves.toEqual({
      text: "Hello, Ada Lovelace!",
    });
    expect(adapterMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "get",
        params: { name: "Ada Lovelace" },
        url: "/api/greet",
      }),
    );
  });
});
