import { cleanup, fireEvent, render, screen, within } from "@testing-library/vue";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MessageTimeline from "@/domains/room/MessageTimeline.vue";
import type { Delivery } from "@/services/roomApi";
import { useToastsStore } from "@/stores/toasts";

import { roomFixture } from "../../fixtures/room";

describe("MessageTimeline history", () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("copies the full original body without selecting the message and keeps quote replies", async () => {
    const snapshot = roomFixture();
    snapshot.messages[0].content = "  **消息正文**\n第二行\n";
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const { emitted } = render(MessageTimeline, {
      props: {
        messages: snapshot.messages,
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    await fireEvent.click(screen.getByRole("button", { name: "复制消息 #1 正文" }));

    expect(writeText).toHaveBeenCalledOnce();
    expect(writeText).toHaveBeenCalledWith(snapshot.messages[0].content);
    expect(useToastsStore().items).toMatchObject([{ tone: "success", message: "消息正文已复制" }]);
    expect(emitted().select).toBeUndefined();
    expect(emitted().reply).toBeUndefined();

    await fireEvent.click(screen.getByRole("button", { name: "引用消息 #1" }));
    expect(emitted().reply).toEqual([[snapshot.messages[0]]]);
    expect(emitted().select).toBeUndefined();
  });

  it("renders Markdown structure in message bodies", () => {
    const snapshot = roomFixture();
    const message = {
      ...snapshot.messages[0],
      content: [
        "## 发布摘要",
        "",
        "完成 **登录流程** 和 `member_context`。",
        "",
        "- 支持话题消息",
        "- 保留原始正文",
        "",
        "```ts",
        "const ready = true;",
        "```",
      ].join("\n"),
    };
    const { container } = render(MessageTimeline, {
      props: {
        messages: [message],
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    const body = container.querySelector(".message-content");
    expect(body?.querySelector("h2")?.textContent).toBe("发布摘要");
    expect(body?.querySelector("strong")?.textContent).toBe("登录流程");
    expect(body?.querySelector("code")?.textContent).toBe("member_context");
    expect(body?.querySelectorAll("li")).toHaveLength(2);
    expect(body?.querySelector("pre code")?.textContent).toBe("const ready = true;\n");
  });

  it("reports a clipboard failure without claiming the message was copied", async () => {
    const snapshot = roomFixture();
    const writeText = vi.fn().mockRejectedValue(new Error("Clipboard denied"));
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    render(MessageTimeline, {
      props: {
        messages: snapshot.messages,
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    await fireEvent.click(screen.getByRole("button", { name: "复制消息 #1 正文" }));

    expect(useToastsStore().items).toMatchObject([
      { tone: "error", message: "复制失败，请重试或手动复制消息正文" },
    ]);
  });

  it("distinguishes an empty search result from a room with no messages", async () => {
    const snapshot = roomFixture();
    const { rerender } = render(MessageTimeline, {
      props: {
        messages: [],
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
        searching: true,
      },
    });

    expect(screen.getByText("未找到匹配的消息")).toBeTruthy();
    await rerender({ searching: false });
    expect(screen.getByText("暂无消息")).toBeTruthy();
  });

  it("offers older and latest pages and lets an off-page reference be located", async () => {
    const snapshot = roomFixture();
    snapshot.messages[1].replyToMessageId = "off-page-message";
    const { emitted } = render(MessageTimeline, {
      props: {
        messages: snapshot.messages,
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: true,
        hasNewer: true,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    await fireEvent.click(screen.getByRole("button", { name: "加载更早消息" }));
    await fireEvent.click(screen.getByRole("button", { name: "返回最新消息" }));
    await fireEvent.click(screen.getByRole("button", { name: "引用 off-page-message" }));

    expect(emitted().loadOlder).toEqual([[]]);
    expect(emitted().latest).toEqual([[]]);
    expect(emitted().reference).toEqual([["off-page-message"]]);
  });

  it("adds heading topics, authors and mentions to routing without selecting the message", async () => {
    const snapshot = roomFixture();
    const { emitted } = render(MessageTimeline, {
      props: {
        messages: snapshot.messages,
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });
    const agentMessage = within(screen.getByRole("article", { name: "后端 Worker的消息" }));
    const userMessage = within(screen.getByRole("article", { name: "你的消息" }));

    await fireEvent.click(agentMessage.getByRole("button", { name: "勾选话题：后端" }));
    await fireEvent.click(agentMessage.getByRole("button", { name: "勾选成员：后端 Worker" }));
    await fireEvent.click(agentMessage.getByRole("button", { name: "勾选成员：测试 Worker" }));

    expect(emitted().addTopic).toEqual([["backend"]]);
    expect(emitted().addMember).toEqual([["backend-worker"], ["test-worker"]]);
    expect(userMessage.getByRole("button", { name: "勾选成员：你" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(emitted().select).toBeUndefined();
  });

  it("identifies messages addressed to the room user", () => {
    const snapshot = roomFixture();
    snapshot.messages[1].mentionedMemberIds = ["user"];
    snapshot.messages[1].recipientIds = ["user"];
    snapshot.messages[1].deliveries = [];
    snapshot.messages[1].replyToMessageId = snapshot.messages[0].id;
    render(MessageTimeline, {
      props: {
        messages: snapshot.messages,
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    const userRecipientMessage = screen.getByRole("article", {
      name: "后端 Worker的消息",
    });
    expect(userRecipientMessage.querySelector(".message-mentions")?.textContent?.trim()).toBe("你");
    expect(screen.getByRole("button", { name: "引用 #1 · 你" })).toBeTruthy();
    expect(screen.queryByText("YOU")).toBeNull();
    expect(userRecipientMessage.querySelector(".message-delivery-summary")).toBeNull();
  });

  it("shows one stage based on the earliest unfinished delivery", async () => {
    const snapshot = roomFixture();
    const queuedAt = "2026-11-06T10:02:00Z";
    const receivedAt = "2026-11-06T10:02:04Z";
    const message = {
      ...snapshot.messages[0],
      deliveries: snapshot.messages[0].deliveries.map((delivery, index) =>
        index === 0
          ? { ...delivery, status: "received" as const, queuedAt, receivedAt }
          : { ...delivery, status: "queued" as const, queuedAt },
      ),
    };
    const { rerender } = render(MessageTimeline, {
      props: {
        messages: [snapshot.messages[0]],
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    expect(screen.getByText("发送中").getAttribute("data-tone")).toBe("info");
    expect(screen.getByLabelText("分发状态").textContent?.trim()).toBe("发送中");

    await rerender({ messages: [message] });

    expect(screen.getByText("接收中").getAttribute("data-tone")).toBe("info");
    expect(screen.getByLabelText("分发状态").textContent?.trim()).toBe("接收中");
    expect(screen.getByLabelText("分发状态").classList.contains("is-complete")).toBe(false);

    await rerender({
      messages: [
        {
          ...message,
          deliveries: message.deliveries.map((delivery) => ({
            ...delivery,
            status: "received" as const,
            receivedAt,
          })),
        },
      ],
    });

    expect(screen.getByText("已接收").getAttribute("data-tone")).toBe("success");
    expect(screen.getByLabelText("分发状态").textContent?.trim()).toBe("已接收");
    expect(screen.getByLabelText("分发状态").classList.contains("is-complete")).toBe(true);
  });

  it("omits manually removed deliveries from queue and receipt summaries", () => {
    const snapshot = roomFixture();
    render(MessageTimeline, {
      props: {
        messages: [
          {
            ...snapshot.messages[0],
            deliveries: snapshot.messages[0].deliveries.map((delivery) => ({
              ...delivery,
              deletedAt: "2026-11-10T13:00:00Z",
            })),
          },
        ],
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });
    expect(screen.queryByLabelText("分发状态")).toBeNull();
    expect(screen.queryByText("人为删除")).toBeNull();
    expect(screen.queryByText("发送中")).toBeNull();
    expect(screen.queryByText("接收中")).toBeNull();
  });

  it.each<{
    statuses: Delivery["status"][];
    label: string;
    tone: string;
  }>([
    { statuses: ["rejected"], label: "发送失败", tone: "error" },
    { statuses: ["unknown"], label: "发送待确认", tone: "warning" },
    { statuses: ["received", "rejected"], label: "发送失败", tone: "error" },
    {
      statuses: ["received", "unknown"],
      label: "发送待确认",
      tone: "warning",
    },
    { statuses: ["rejected", "unknown"], label: "发送失败", tone: "error" },
  ])("reports abnormal delivery outcomes for $statuses", ({ statuses, label, tone }) => {
    const snapshot = roomFixture();
    const message = {
      ...snapshot.messages[0],
      deliveries: statuses.map((status, index) => ({
        ...snapshot.messages[0].deliveries[index],
        status,
      })),
    };
    render(MessageTimeline, {
      props: {
        messages: [message],
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    expect(screen.getByText(label).getAttribute("data-tone")).toBe(tone);
    expect(screen.getByLabelText("分发状态").textContent?.trim()).toBe(label);
    expect(screen.queryByText("发送中")).toBeNull();
    expect(screen.queryByText("接收中")).toBeNull();
    expect(screen.getByLabelText("分发状态").classList.contains("is-complete")).toBe(false);
  });

  it("shows one standalone time marker per minute before its message group", () => {
    const snapshot = roomFixture();
    const messages = snapshot.messages.map((message, index) => ({
      ...message,
      createdAt: index === 0 ? "2026-11-06T10:00:23Z" : "2026-11-06T10:00:48Z",
    }));
    messages.push({
      ...messages[1],
      id: "msg-0003",
      seq: 3,
      createdAt: "2026-11-06T10:01:00Z",
    });
    const { container } = render(MessageTimeline, {
      props: {
        messages,
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    const markers = Array.from(container.querySelectorAll(".timeline-time time"));
    expect(markers).toHaveLength(2);
    expect(markers.map((marker) => marker.getAttribute("datetime"))).toEqual([
      messages[0].createdAt,
      messages[2].createdAt,
    ]);
    expect(markers.every((marker) => /^\d{2}:\d{2}$/.test(marker.textContent ?? ""))).toBe(true);
    expect(container.querySelectorAll(".message-content .message-time")).toHaveLength(0);
    expect(markers[0].parentElement?.nextElementSibling?.classList.contains("message")).toBe(true);
    expect(markers[1].parentElement?.nextElementSibling?.classList.contains("message")).toBe(true);
  });

  it("updates authors and references when members are renamed without reloading messages", async () => {
    const snapshot = roomFixture();
    snapshot.messages[0].replyToMessageId = snapshot.messages[1].id;
    const { rerender } = render(MessageTimeline, {
      props: {
        messages: snapshot.messages,
        members: snapshot.members,
        sessions: snapshot.sessions,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    expect(screen.getByRole("article", { name: "后端 Worker的消息" })).toBeTruthy();
    await rerender({
      members: snapshot.members.map((member) =>
        member.id === "backend-worker" ? { ...member, name: "后端开发" } : member,
      ),
    });

    expect(screen.getByRole("article", { name: "后端开发的消息" })).toBeTruthy();
    expect(screen.getByText("后端开发", { selector: ".message-author" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "引用 #2 · 后端开发" })).toBeTruthy();
    expect(screen.queryByText("后端 Worker")).toBeNull();
  });
});
