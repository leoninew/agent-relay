import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/services/api";
import type { CreateMessage, SessionCandidate } from "@/services/roomApi";
import {
  addRoomMember,
  clearRoom,
  deleteQueueMessage,
  deleteRoom,
  fetchRoom,
  fetchRoomEvents,
  fetchRoomMessage,
  fetchRoomMessages,
  fetchRoomMetadata,
  fetchRoomMessageUpdates,
  fetchRoomActivity,
  fetchMessageQueue,
  fetchRoomSessions,
  fetchRooms,
  fetchRoomSkills,
  fetchMemberModels,
  updateMemberModel,
  interruptRoomMember,
  postRoomMessage,
  updateRoom,
} from "@/services/roomApi";

import { roomFixture } from "../fixtures/room";

const adapterMock = vi.fn();
let originalAdapter: typeof apiClient.defaults.adapter;

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

  it("sends a scoped batch body and a separate lightweight activity request", async () => {
    const signal = new AbortController().signal;
    const query = { messageIds: ["changed"], retainedIds: [], topicId: "topic", keyword: "needle" };
    await fetchRoomMessageUpdates("room/a", query, signal, "channel/b");
    expect(adapterMock.mock.calls[0][0]).toMatchObject({
      method: "post",
      url: "/api/room/room%2Fa/channel/channel%2Fb/message/updates",
      signal,
    });
    expect(JSON.parse(adapterMock.mock.calls[0][0].data)).toEqual(query);
    await fetchRoomActivity("room/a", signal, "channel/b");
    expect(adapterMock.mock.calls[1][0]).toMatchObject({
      method: "get",
      url: "/api/room/room%2Fa/channel/channel%2Fb/activity",
      signal,
    });
  });

  it("posts a scoped interrupt without forwarding session IDs or queue options", async () => {
    await interruptRoomMember("room/a", "member/b", "channel/c");
    expect(adapterMock.mock.calls[0][0]).toMatchObject({
      method: "post",
      url: "/api/room/room%2Fa/channel/channel%2Fc/member/member%2Fb/interrupt",
    });
    expect(adapterMock.mock.calls[0][0].data).toBeUndefined();
  });

  it("reads and updates the selected member model with escaped scope and the original binding", async () => {
    await fetchMemberModels("room/a", "member/b", "channel/c");
    expect(adapterMock.mock.calls[0][0]).toMatchObject({
      method: "get",
      url: "/api/room/room%2Fa/channel/channel%2Fc/member/member%2Fb/model",
    });
    await updateMemberModel("room/a", "member/b", "channel/c", {
      sessionId: "thread",
      model: "provider/model",
    });
    expect(adapterMock.mock.calls[1][0]).toMatchObject({
      method: "patch",
      url: "/api/room/room%2Fa/channel/channel%2Fc/member/member%2Fb/model",
    });
    expect(JSON.parse(adapterMock.mock.calls[1][0].data)).toEqual({
      sessionId: "thread",
      model: "provider/model",
    });
  });

  it("requests room skills with an escaped identity and explicit reload", async () => {
    const signal = new AbortController().signal;
    await fetchRoomSkills("room/a", true, signal, "channel-default");
    expect(adapterMock.mock.calls[0][0]).toMatchObject({
      url: "/api/room/room%2Fa/channel/channel-default/skills",
      params: { force_reload: true },
      signal,
    });
  });

  it("loads a room and sends combined filters and a pagination cursor", async () => {
    await expect(fetchRooms()).resolves.toEqual([roomFixture().room]);
    await expect(fetchRoom("conflua", {}, undefined, "channel-default")).resolves.toEqual(
      roomFixture(),
    );
    await fetchRoom(
      "conflua",
      {
        topicId: "frontend",
        memberId: "frontend-worker",
        keyword: "接口%_",
        beforeSeq: 80,
        limit: 25,
      },
      undefined,
      "channel-default",
    );
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "get",
        url: "/api/room/conflua/channel/channel-default/snapshot",
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
    await fetchRoomMessages(
      "room/one",
      { keyword: "接口", beforeSeq: 50 },
      signal,
      "channel-default",
    );
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/api/room/room%2Fone/channel/channel-default/message",
        params: expect.objectContaining({ keyword: "接口", before_seq: 50 }),
        signal,
      }),
    );
    await fetchRoomMessage("room/one", "message/one", signal, "channel-default");
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/api/room/room%2Fone/channel/channel-default/message/message%2Fone",
        signal,
      }),
    );
    await fetchRoomMetadata("room/one", signal, "channel-default");
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/api/room/room%2Fone/channel/channel-default/metadata",
        signal,
      }),
    );
    await fetchRoomEvents("room/one", 123, signal, "channel-default");
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        url: "/api/room/room%2Fone/channel/channel-default/event",
        params: { after_event_id: 123 },
        signal,
      }),
    );
  });

  it("posts structured routing and capability references to the message endpoint", async () => {
    const request: CreateMessage = {
      publicationId: "test-publication",
      content: "核对契约",
      topicIds: ["frontend", "backend"],
      mentionedMemberIds: ["test-worker"],
      replyToMessageId: "msg-0001",
      capabilities: [
        { type: "skill", id: "skill-example", name: "Example skill" },
        { type: "mcp_server", id: "example", name: "Example MCP" },
      ],
    };
    await expect(postRoomMessage("conflua", request, "channel-default")).resolves.toEqual(
      roomFixture().messages[0],
    );
    expect(adapterMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "post",
        url: "/api/room/conflua/channel/channel-default/message",
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
      "channel-default",
    );
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "get",
        url: "/api/room/room%2Fone/channel/channel-default/queue",
        params: {
          topic_id: "frontend",
          member_id: "test-worker",
          before_seq: 50,
          limit: 25,
        },
        signal,
      }),
    );
    await fetchMessageQueue("room/one", {}, undefined, "channel-default");
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        params: { topic_id: undefined, member_id: undefined, before_seq: undefined, limit: 50 },
      }),
    );
  });

  it("removes one queue message using escaped room and message identities", async () => {
    adapterMock.mockImplementationOnce(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: { removedMessages: 1 },
      headers: { "content-type": "application/json" },
      status: 200,
      statusText: "",
    }));
    await expect(deleteQueueMessage("room/one", "message/one", "channel-default")).resolves.toEqual(
      {
        removedMessages: 1,
      },
    );
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "delete",
        url: "/api/room/room%2Fone/channel/channel-default/queue/message%2Fone",
      }),
    );
  });

  it("loads project sessions and joins the selected session without creation fields", async () => {
    const signal = new AbortController().signal;
    const sessions: SessionCandidate[] = [
      {
        id: "existing-session",
        name: "Worker",
        provider: "codex",
        presence: "available",
        observedAt: null,
        archived: false,
        memberId: null,
        joinedChannels: [
          { id: "channel-api", name: "API" },
          { id: "channel-web", name: "Web" },
        ],
        usable: true,
        unavailableReason: null,
      },
    ];
    adapterMock.mockImplementationOnce(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: sessions,
      headers: { "content-type": "application/json" },
      status: 200,
      statusText: "",
    }));
    await expect(fetchRoomSessions("room/one", signal, "channel-default")).resolves.toEqual(
      sessions,
    );
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "get",
        url: "/api/room/room%2Fone/channel/channel-default/session",
        signal,
      }),
    );
    const request = {
      sessionId: "existing-session",
      name: "Worker",
      topicIds: ["frontend"],
    };
    await addRoomMember("room/one", request, "channel-default");
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "post",
        url: "/api/room/room%2Fone/channel/channel-default/member",
        data: JSON.stringify(request),
      }),
    );
  });

  it("adds an optional role ID to the existing join request", async () => {
    const request = {
      name: "Worker",
      sessionId: "existing",
      topicIds: [],
      roleId: "role-reviewer",
    };
    await addRoomMember("room", request, "channel-default");
    expect(adapterMock).toHaveBeenCalledOnce();
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "post",
        url: "/api/room/room/channel/channel-default/member",
        data: JSON.stringify(request),
      }),
    );
  });

  it("does not automatically retry a failed join request", async () => {
    adapterMock.mockRejectedValueOnce(new Error("connection lost"));
    await expect(
      addRoomMember(
        "room",
        {
          sessionId: "existing",
          name: "Worker",
          topicIds: ["frontend"],
        },
        "channel-default",
      ),
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

  it("clears the entire room without passing message filters", async () => {
    const result = { removedMessages: 2, removedMembers: 1, metadata: roomFixture() };
    adapterMock.mockImplementationOnce(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: result,
      headers: { "content-type": "application/json" },
      status: 200,
      statusText: "OK",
    }));

    await expect(clearRoom("room/one", "channel-default")).resolves.toEqual(result);
    expect(adapterMock).toHaveBeenCalledOnce();
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "post",
        url: "/api/room/room%2Fone/channel/channel-default/clear",
      }),
    );
    expect(adapterMock.mock.calls[0][0].params).toBeUndefined();
  });

  it("renames a room without sending its workspace path", async () => {
    adapterMock.mockImplementationOnce(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: { ...roomFixture().room, name: "Renamed" },
      headers: { "content-type": "application/json" },
      status: 200,
      statusText: "OK",
    }));

    await expect(updateRoom("room/one", { name: "Renamed" })).resolves.toMatchObject({
      name: "Renamed",
    });
    expect(adapterMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: "patch",
        url: "/api/room/room%2Fone",
        data: JSON.stringify({ name: "Renamed" }),
      }),
    );
  });
});
