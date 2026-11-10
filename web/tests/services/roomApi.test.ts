import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/services/api";
import {
  addRoomMember,
  clearMessageQueue,
  deleteRoom,
  fetchRoom,
  fetchRoomEvents,
  fetchRoomMessage,
  fetchRoomMessages,
  fetchRoomMetadata,
  fetchMessageQueue,
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
      keyword: "接口%_",
      beforeSeq: 80,
      limit: 25,
    });
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "get",
        url: "/api/room/agent-relay",
        params: {
          topic_id: "frontend",
          member_id: "frontend-worker",
          keyword: "接口%_",
          before_seq: 80,
          limit: 25,
        },
      }),
    );
  });

  it("loads history, exact references, metadata and event catchup independently", async () => {
    const signal = new AbortController().signal;
    await fetchRoomMessages("room/one", { keyword: "接口", beforeSeq: 50 }, signal);
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/api/room/room%2Fone/message",
        params: expect.objectContaining({ keyword: "接口", before_seq: 50 }),
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

  it("loads a detail queue with resource filters and an older-message cursor", async () => {
    const signal = new AbortController().signal;
    await fetchMessageQueue(
      "room/one",
      { topicId: "frontend", memberId: "test-worker", beforeSeq: 50, limit: 25 },
      signal,
    );
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "get",
        url: "/api/room/room%2Fone/queue",
        params: {
          topic_id: "frontend",
          member_id: "test-worker",
          before_seq: 50,
          limit: 25,
        },
        signal,
      }),
    );
    await fetchMessageQueue("room/one");
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        params: { topic_id: undefined, member_id: undefined, before_seq: undefined, limit: 50 },
      }),
    );
  });

  it("clears the entire resource queue without a page cursor", async () => {
    adapterMock.mockImplementationOnce(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: { removedMessages: 80 },
      headers: { "content-type": "application/json" },
      status: 200,
      statusText: "",
    }));
    await expect(
      clearMessageQueue("room/one", { topicId: "frontend", memberId: "test-worker" }),
    ).resolves.toEqual({ removedMessages: 80 });
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "delete",
        url: "/api/room/room%2Fone/queue",
        params: { topic_id: "frontend", member_id: "test-worker" },
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

  it("deletes the selected room and accepts an empty successful response", async () => {
    adapterMock.mockImplementationOnce(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: "",
      headers: {},
      status: 204,
      statusText: "No Content",
    }));

    await expect(deleteRoom("room/one")).resolves.toBeUndefined();
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ method: "delete", url: "/api/room/room%2Fone" }),
    );
  });
});
