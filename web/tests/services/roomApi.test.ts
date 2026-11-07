import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/services/api";
import { fetchRoom, fetchRooms, postRoomMessage } from "@/services/roomApi";

import { roomFixture } from "../fixtures/room";

const adapterMock = vi.fn();
let originalAdapter: AxiosAdapter | AxiosAdapter[] | undefined;

describe("room API", () => {
  beforeEach(() => {
    originalAdapter = apiClient.defaults.adapter;
    apiClient.defaults.adapter = adapterMock as AxiosAdapter;
    adapterMock.mockImplementation(async (config: InternalAxiosRequestConfig) => ({
      config,
      data:
        config.method === "post"
          ? roomFixture().messages[0]
          : config.url === "/api/room"
            ? [roomFixture().room]
            : roomFixture(),
      headers: { "content-type": "application/json" },
      status: config.method === "post" ? 201 : 200,
      statusText: "",
    }));
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
    vi.clearAllMocks();
  });

  it("loads a room with an optional topic filter", async () => {
    await expect(fetchRooms()).resolves.toEqual([roomFixture().room]);
    await expect(fetchRoom("agent-relay")).resolves.toEqual(roomFixture());
    await fetchRoom("agent-relay", "frontend");
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "get",
        url: "/api/room/agent-relay",
        params: { topic_id: "frontend" },
      }),
    );
  });

  it("posts structured routing fields to the message endpoint", async () => {
    const request = {
      content: "核对契约",
      topicIds: ["frontend", "backend"],
      mentionedMemberIds: ["test-worker"],
      replyToMessageId: "msg-0001",
    };
    await expect(postRoomMessage("agent-relay", request)).resolves.toEqual(
      roomFixture().messages[0],
    );
    expect(adapterMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "post",
        url: "/api/room/agent-relay/message",
        data: JSON.stringify(request),
      }),
    );
  });
});
