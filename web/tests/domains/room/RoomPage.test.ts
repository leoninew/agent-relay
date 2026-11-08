import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/vue";
import { createPinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import RoomPage from "@/domains/room/RoomPage.vue";
import { fetchPublication, fetchRoom, fetchRooms, postRoomMessage } from "@/services/roomApi";
import type * as roomApi from "@/services/roomApi";
import { useToastsStore } from "@/stores/toasts";

import { roomFixture } from "../../fixtures/room";

vi.mock("@/services/roomApi", async (importOriginal) => ({
  ...(await importOriginal<typeof roomApi>()),
  fetchRooms: vi.fn(),
  fetchRoom: vi.fn(),
  fetchPublication: vi.fn(),
  postRoomMessage: vi.fn(),
}));

vi.mock("@/services/roomEvents", () => ({ subscribeRoomEvents: vi.fn(() => vi.fn()) }));

describe("RoomPage publication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    vi.mocked(fetchRooms).mockResolvedValue([roomFixture().room]);
    vi.mocked(fetchRoom).mockImplementation(async () => roomFixture());
    vi.mocked(postRoomMessage).mockImplementation(async (_room, request) => ({
      ...roomFixture().messages[0],
      ...request,
    }));
  });

  afterEach(cleanup);

  async function openRoom() {
    const pinia = createPinia();
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/room/:roomId", name: "room-detail", component: RoomPage }],
    });
    await router.push("/room/agent-relay");
    await router.isReady();
    render(RoomPage, { props: { roomId: "agent-relay" }, global: { plugins: [pinia, router] } });
    await screen.findByRole("textbox", { name: "消息内容" });
    return pinia;
  }

  it("keeps explicit draft routing while browsing and publishes with a stable identity", async () => {
    const pinia = await openRoom();
    await fireEvent.click(screen.getByRole("checkbox", { name: "消息话题：后端" }));
    await fireEvent.click(screen.getByRole("button", { name: "筛选话题：前端" }));
    await waitFor(() =>
      expect(fetchRoom).toHaveBeenLastCalledWith(
        "agent-relay",
        expect.objectContaining({ topicId: "frontend" }),
        expect.any(AbortSignal),
      ),
    );
    expect(
      screen.getByRole("checkbox", { name: "消息话题：后端" }).getAttribute("aria-checked"),
    ).toBe("true");
    expect(
      screen.getByRole("checkbox", { name: "消息话题：前端" }).getAttribute("aria-checked"),
    ).toBe("false");
    await fireEvent.update(screen.getByRole("textbox", { name: "消息内容" }), "核对后端");
    await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
    await waitFor(() => expect(postRoomMessage).toHaveBeenCalledTimes(1));
    expect(vi.mocked(postRoomMessage).mock.calls[0]).toEqual([
      "agent-relay",
      {
        publicationId: expect.any(String),
        content: "核对后端",
        topicIds: ["backend"],
        mentionedMemberIds: [],
      },
    ]);
    await waitFor(() => expect(useToastsStore(pinia).items.at(-1)?.tone).toBe("success"));
    expect(sessionStorage.getItem("relay-publication:agent-relay")).toBeNull();
    expect(screen.getByRole("button", { name: "刷新聊天室" })).toBeTruthy();
  });

  it("finds a saved publication after reopening the page and continues composing", async () => {
    const request = {
      publicationId: "saved-publication",
      content: "待核对发布",
      topicIds: ["frontend"],
      mentionedMemberIds: [],
    };
    sessionStorage.setItem("relay-publication:agent-relay", JSON.stringify(request));
    vi.mocked(fetchPublication).mockResolvedValue({ ...roomFixture().messages[0], ...request });
    await openRoom();
    await fireEvent.click(screen.getByRole("button", { name: "核对发布结果" }));
    await waitFor(() =>
      expect(fetchPublication).toHaveBeenCalledWith("agent-relay", "saved-publication"),
    );
    await waitFor(() => expect(sessionStorage.getItem("relay-publication:agent-relay")).toBeNull());
    expect((screen.getByRole("textbox", { name: "消息内容" }) as HTMLTextAreaElement).value).toBe(
      "",
    );
    expect((screen.getByRole("button", { name: "发送消息" }) as HTMLButtonElement).disabled).toBe(
      false,
    );
  });
});
