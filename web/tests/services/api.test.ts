import axios from "axios";
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientError, apiClient, describeApiError } from "@/services/api";

const adapterMock = vi.fn();
let originalAdapter: AxiosAdapter | AxiosAdapter[] | undefined;

function mockResponse<T>(
  data: T,
  status = 200,
  headers: Record<string, string> = { "content-type": "application/json" },
): AxiosResponse<T> {
  return {
    config: {} as InternalAxiosRequestConfig,
    data,
    headers,
    status,
    statusText: "",
  };
}

describe("apiClient", () => {
  it("maps known codes and hides untrusted unknown messages", () => {
    expect(
      describeApiError(
        new ApiClientError("private", "http_error", {
          code: "room_not_found",
          requestId: "req1",
          status: 404,
        }),
        "errors.roomLoad",
      ),
    ).toEqual({ key: "errors.room_not_found", requestId: "req1" });
    expect(
      describeApiError(
        new ApiClientError("private", "http_error", {
          code: "unexpected",
          requestId: "req2",
          status: 400,
        }),
        "errors.roomLoad",
      ),
    ).toEqual({ key: "errors.roomLoad", requestId: "req2" });
  });
  beforeEach(() => {
    adapterMock.mockReset();
    originalAdapter = apiClient.defaults.adapter;
    apiClient.defaults.adapter = adapterMock as AxiosAdapter;
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
  });

  it("returns Axios-parsed JSON response data", async () => {
    adapterMock.mockResolvedValue(mockResponse([{ id: "room-1", name: "Room" }]));

    await expect(apiClient.get<{ id: string; name: string }[]>("/api/room")).resolves.toMatchObject(
      {
        data: [{ id: "room-1", name: "Room" }],
      },
    );

    expect(adapterMock).toHaveBeenCalledWith(expect.objectContaining({ url: "/api/room" }));
  });

  it("rejects malformed JSON success responses with their request context", async () => {
    adapterMock.mockResolvedValue(
      mockResponse('[{"id":', 200, {
        "content-type": "application/json",
        "X-Request-Id": "req_parse",
      }),
    );

    await expect(apiClient.get("/api/room")).rejects.toMatchObject({
      kind: "contract_mismatch",
      requestId: "req_parse",
      status: 200,
    });
  });

  it("accepts a no-content response without a JSON content type", async () => {
    adapterMock.mockResolvedValue(mockResponse("", 204, {}));

    await expect(apiClient.delete("/api/resource")).resolves.toMatchObject({ status: 204 });
  });

  it("normalizes structured application errors in the response interceptor", async () => {
    const response = mockResponse(
      {
        code: "validation_error",
        error: "Validation error",
        requestId: "req_blank",
      },
      422,
      {
        "content-type": "application/json",
        "X-Request-Id": "req_blank",
      },
    );
    adapterMock.mockRejectedValue(
      new axios.AxiosError(
        "Request failed",
        axios.AxiosError.ERR_BAD_REQUEST,
        response.config,
        undefined,
        response,
      ),
    );

    await expect(
      apiClient.post("/api/room", { name: "", projectPath: "D:/project" }),
    ).rejects.toMatchObject({
      code: "validation_error",
      kind: "http_error",
      requestId: "req_blank",
      status: 422,
    } satisfies Partial<ApiClientError>);
  });

  it("normalizes network failures in the response interceptor", async () => {
    adapterMock.mockRejectedValue(
      new axios.AxiosError("Network unavailable", axios.AxiosError.ERR_NETWORK),
    );

    await expect(apiClient.get("/api/room")).rejects.toMatchObject({
      kind: "network_error",
      message: "Network request failed.",
    } satisfies Partial<ApiClientError>);
  });

  it.each([axios.AxiosError.ECONNABORTED, axios.AxiosError.ETIMEDOUT])(
    "distinguishes timeout %s from network failures without retrying",
    async (code) => {
      adapterMock.mockRejectedValue(new axios.AxiosError("internal transport detail", code));

      await expect(apiClient.get("/api/room")).rejects.toMatchObject({
        kind: "timeout",
        message: "Request timed out.",
      } satisfies Partial<ApiClientError>);
      expect(adapterMock).toHaveBeenCalledTimes(1);
    },
  );

  it("distinguishes cancellation from network failures", async () => {
    adapterMock.mockRejectedValue(new axios.CanceledError("internal cancellation detail"));

    await expect(apiClient.get("/api/room")).rejects.toMatchObject({
      kind: "canceled",
      message: "Request canceled.",
    } satisfies Partial<ApiClientError>);
  });

  it.each([
    [401, "unauthorized", undefined],
    [503, "service_unavailable", "30"],
  ] as const)(
    "keeps status %s and retry metadata for caller policy",
    async (status, code, retryAfter) => {
      const response = mockResponse(
        { code, error: "Request unavailable", requestId: "req_policy" },
        status,
        {
          "content-type": "application/json",
          "X-Request-Id": "req_policy",
          ...(retryAfter ? { "Retry-After": retryAfter } : {}),
        },
      );
      adapterMock.mockRejectedValue(
        new axios.AxiosError("Request failed", undefined, response.config, undefined, response),
      );

      await expect(apiClient.get("/api/room")).rejects.toMatchObject({
        kind: "http_error",
        code,
        requestId: "req_policy",
        retryAfter,
        status,
      } satisfies Partial<ApiClientError>);
      expect(adapterMock).toHaveBeenCalledTimes(1);
    },
  );

  it.each([
    ["text/plain", { code: "internal_error", error: "private diagnostic", requestId: "req_body" }],
    ["text/html", "<h1>private diagnostic</h1>"],
    ["application/json", { detail: "private diagnostic" }],
    ["application/json", { code: "internal_error", error: "private diagnostic", requestId: 12 }],
  ])("rejects invalid error contract with content type %s", async (contentType, data) => {
    const response = mockResponse(data, 502, {
      "content-type": contentType as string,
      "X-Request-Id": "req_gateway",
    });
    adapterMock.mockRejectedValue(
      new axios.AxiosError("private diagnostic", undefined, response.config, undefined, response),
    );

    await expect(apiClient.get("/api/room")).rejects.toMatchObject({
      kind: "contract_mismatch",
      message: "Unexpected API error response.",
      requestId: "req_gateway",
      status: 502,
    } satisfies Partial<ApiClientError>);
  });

  it("preserves errors already normalized by the API boundary", async () => {
    const error = new ApiClientError("Request unavailable", "http_error", { status: 503 });
    adapterMock.mockRejectedValue(error);

    await expect(apiClient.get("/api/room")).rejects.toBe(error);
  });

  it("rejects non-contract responses without exposing their body", async () => {
    adapterMock.mockResolvedValue(
      mockResponse("<h1>Bad Gateway</h1>", 200, { "content-type": "text/html" }),
    );

    await expect(apiClient.get("/api/room")).rejects.toMatchObject({
      kind: "contract_mismatch",
      message: "Unexpected API success response.",
      status: 200,
    } satisfies Partial<ApiClientError>);
  });
});
