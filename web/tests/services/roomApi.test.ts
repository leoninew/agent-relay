import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/services/api";
import {
  addRoomMember,
  fetchRoom,
  fetchRoomEvents,
  fetchRoomMessage,
  fetchRoomMessages,
  fetchRoomMetadata,
  fetchRoomSessions,
  fetchRooms,
  postRoomMessage,
} from "@/services/roomApi";

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

  it("loads a room and sends combined filters and a pagination cursor", async () => {
    await expect(fetchRooms()).resolves.toEqual([roomFixture().room]);
    await expect(fetchRoom("agent-relay")).resolves.toEqual(roomFixture());
    await fetchRoom("agent-relay", {
      topicId: "frontend",
      memberId: "frontend-worker",
      beforeSeq: 80,
      limit: 25,
    });
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "get",
        url: "/api/room/agent-relay",
        params: { topic_id: "frontend", member_id: "frontend-worker", before_seq: 80, limit: 25 },
      }),
    );
  });

  it("loads history, exact references, metadata and event catchup independently", async () => {
    const signal = new AbortController().signal;
    await fetchRoomMessages("room/one", { beforeSeq: 50 }, signal);
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/api/room/room%2Fone/message",
        params: expect.objectContaining({ before_seq: 50 }),
        signal,
      }),
    );
    await fetchRoomMessage("room/one", "message/one", signal);
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/api/room/room%2Fone/message/message%2Fone",
        signal,
      }),
    );
    await fetchRoomMetadata("room/one", signal);
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/api/room/room%2Fone/metadata",
        signal,
      }),
    );
    await fetchRoomEvents("room/one", 123, signal);
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/api/room/room%2Fone/event",
        params: { after_event_id: 123 },
        signal,
      }),
    );
  });

  it("posts structured routing fields to the message endpoint", async () => {
    const request = {
      publicationId: "test-publication",
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

  it("loads project sessions and joins the selected session without creation fields", async () => {
    await fetchRoomSessions("room/one");
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "get",
        url: "/api/room/room%2Fone/session",
      }),
    );
    const request = {
      sessionId: "existing-session",
      name: "Worker",
      topicIds: ["frontend"],
    };
    await addRoomMember("room/one", request);
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "post",
        url: "/api/room/room%2Fone/member",
        data: JSON.stringify(request),
      }),
    );
  });

  it("does not automatically retry a failed join request", async () => {
    adapterMock.mockRejectedValueOnce(new Error("connection lost"));
    await expect(
      addRoomMember("room", {
        sessionId: "existing",
        name: "Worker",
        topicIds: ["frontend"],
      }),
    ).rejects.toThrow();
    expect(adapterMock).toHaveBeenCalledTimes(1);
  });
});
