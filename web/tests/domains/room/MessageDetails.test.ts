import { cleanup, fireEvent, render, screen, within } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MessageDetails from "@/domains/room/MessageDetails.vue";
import type { RoomMessage } from "@/services/roomApi";

import { roomFixture } from "../../fixtures/room";

describe("MessageDetails", () => {
  afterEach(cleanup);

  it("keeps the queue inside each detail view and exposes the drawer collapse action", async () => {
    const room = roomFixture();
    const { container, emitted, rerender } = render(MessageDetails, {
      props: {
        message: room.messages[0],
        topics: room.topics,
        members: room.members,
        sessions: room.sessions,
      },
      slots: { queue: '<section aria-label="队列">队列内容</section>' },
    });
    const queue = screen.getByRole("region", { name: "队列" });
    expect(container.querySelector(".message-details-content")?.contains(queue)).toBe(true);
    await rerender({ message: undefined, topic: room.topics[1] });
    expect(
      within(screen.getByRole("complementary", { name: "话题详情" })).getByText("队列内容"),
    ).toBeTruthy();
    await rerender({ topic: undefined, member: room.members[0] });
    expect(
      within(screen.getByRole("complementary", { name: "成员详情" })).getByText("队列内容"),
    ).toBeTruthy();
    await rerender({ member: undefined });
    expect(screen.getByText("暂无详情")).toBeTruthy();
    expect(screen.getByText("队列内容")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "收起右侧面板" }));
    expect(emitted().collapse).toEqual([[]]);
  });

  it("manages the displayed topic and disables actions while saving", async () => {
    const room = roomFixture();
    const topic = room.topics[1];
    const { container, emitted, rerender } = render(MessageDetails, {
      props: { topic, topics: room.topics, members: room.members, sessions: room.sessions },
    });
    const topicIdentity = container.querySelector(".detail-object-identity");
    expect(topicIdentity?.classList.contains("is-active")).toBe(false);
    expect(topicIdentity?.querySelector(".topic-identity")).not.toBeNull();
    expect(container.querySelector(".detail-stats")).toBeNull();
    expect(topicIdentity?.querySelector(".sidebar-item-meta")).toBeNull();
    expect(topicIdentity?.querySelector("time")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "编辑话题：前端" }));
    await fireEvent.click(screen.getByRole("button", { name: "删除话题：前端" }));
    expect(emitted().editTopic).toEqual([[topic]]);
    expect(emitted().deleteTopic).toEqual([[topic]]);
    await rerender({ busy: true });
    expect(
      (screen.getByRole("button", { name: "编辑话题：前端" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(
      (screen.getByRole("button", { name: "删除话题：前端" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("manages agent members while leaving the fixed user and deleted members read only", async () => {
    const room = roomFixture();
    const member = room.members[0];
    const { emitted, rerender } = render(MessageDetails, {
      props: { member, topics: room.topics, members: room.members, sessions: room.sessions },
    });
    await fireEvent.click(screen.getByRole("button", { name: "编辑成员：前端 Worker" }));
    await fireEvent.click(screen.getByRole("button", { name: "删除成员：前端 Worker" }));
    expect(emitted().editMember).toEqual([[member]]);
    expect(emitted().deleteMember).toEqual([[member]]);
    const memberIdentity = screen.getByText(member.name).closest(".detail-object-identity");
    const subscribedTopic = screen.getByText("# 前端");
    expect(memberIdentity?.classList.contains("is-active")).toBe(false);
    expect(memberIdentity?.querySelector(".member-identity")).not.toBeNull();
    expect(subscribedTopic.classList.contains("topic-chip")).toBe(false);
    expect(memberIdentity?.querySelector(".sidebar-member-status")?.textContent?.trim()).toBe(
      "忙碌",
    );
    expect(memberIdentity?.querySelector(".detail-member-kind")).toBeNull();
    await rerender({ member: room.members[3] });
    expect(screen.queryByRole("button", { name: /^编辑成员/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /^删除成员/ })).toBeNull();
    await rerender({ member: { ...member, deletedAt: "2026-11-10T00:00:00Z" } });
    expect(screen.queryByRole("button", { name: /^编辑成员/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /^删除成员/ })).toBeNull();
  });

  it("shows the message sequence, sender and sent time before topics", async () => {
    const room = roomFixture();
    const { container, rerender } = render(MessageDetails, {
      props: {
        message: room.messages[0],
        topics: room.topics,
        members: room.members,
        sessions: room.sessions,
      },
    });

    expect(
      screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent),
    ).toEqual(["消息", "话题", "成员"]);
    expect(screen.getByText("序号").nextElementSibling?.textContent).toBe(
      `#${room.messages[0].seq}`,
    );
    expect(screen.getByText("发送人").nextElementSibling?.textContent).toContain("你");
    expect(screen.getByText("发送时间").nextElementSibling?.textContent).toContain(
      new Date(room.messages[0].createdAt).toLocaleString("zh-CN"),
    );
    expect(container.querySelector("time")?.getAttribute("datetime")).toBe(
      room.messages[0].createdAt,
    );

    const message = room.messages[1];
    await rerender({ message });
    expect(screen.getByText("序号").nextElementSibling?.textContent).toBe(`#${message.seq}`);
    expect(screen.getByText("发送人").nextElementSibling?.textContent).toContain("后端 Worker");
    expect(container.querySelector("time")?.getAttribute("datetime")).toBe(message.createdAt);

    await rerender({ members: [] });
    expect(screen.getByText("发送人").nextElementSibling?.textContent).toContain(
      message.senderName,
    );
  });

  it("shows one stage column for the recorded recipients", () => {
    const room = roomFixture();
    const message: RoomMessage = {
      ...room.messages[1],
      topicIds: ["frontend", "backend"],
      recipientIds: ["frontend-worker", "test-worker"],
      deliveries: room.messages[0].deliveries,
    };
    render(MessageDetails, {
      props: { message, topics: room.topics, members: room.members, sessions: room.sessions },
    });

    expect(screen.getByText("# 前端")).toBeTruthy();
    expect(screen.getByText("# 后端")).toBeTruthy();
    expect(screen.getAllByRole("heading", { name: "成员", level: 3 })).toHaveLength(1);
    const deliveries = within(screen.getByRole("table", { name: "成员" }));
    expect(deliveries.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "名称",
      "状态",
    ]);
    const submitting = within(deliveries.getByRole("row", { name: /前端 Worker/ }));
    expect(submitting.getAllByRole("cell")[1].textContent?.trim()).toBe("发送中");
    const enqueued = within(deliveries.getByRole("row", { name: /测试 Worker/ }));
    expect(enqueued.getAllByRole("cell")[1].textContent?.trim()).toBe("接收中");
  });

  it("shows topic-free messages using saved delivery targets rather than current subscriptions", () => {
    const room = roomFixture();
    const message: RoomMessage = {
      ...room.messages[0],
      topicIds: [],
      mentionedMemberIds: ["frontend-worker"],
      recipientIds: ["frontend-worker"],
      deliveries: [room.messages[0].deliveries[0]],
    };
    render(MessageDetails, {
      props: { message, topics: room.topics, members: room.members, sessions: room.sessions },
    });

    expect(screen.getByText("未选择话题")).toBeTruthy();
    const deliveries = within(screen.getByRole("table", { name: "成员" }));
    expect(deliveries.getByRole("row", { name: /前端 Worker/ })).toBeTruthy();
    expect(deliveries.queryByRole("row", { name: /测试 Worker/ })).toBeNull();
  });

  it("shows received after receipt confirmation", () => {
    const room = roomFixture();
    const delivery = {
      ...room.messages[0].deliveries[0],
      status: "received" as const,
    };
    const message = {
      ...room.messages[0],
      recipientIds: [delivery.targetMemberId],
      deliveries: [delivery],
    };
    render(MessageDetails, {
      props: { message, topics: room.topics, members: room.members, sessions: room.sessions },
    });
    const recipient = within(screen.getByRole("row", { name: /前端 Worker/ }));
    expect(recipient.getAllByRole("cell")[1].textContent?.trim()).toBe("已接收");
  });

  it("does not present manually removed deliveries as active", () => {
    const room = roomFixture();
    const delivery = {
      ...room.messages[0].deliveries[0],
      status: "queued" as const,
      deletedAt: "2026-11-06T10:04:00Z",
    };
    render(MessageDetails, {
      props: {
        message: {
          ...room.messages[0],
          recipientIds: [delivery.targetMemberId],
          deliveries: [delivery],
        },
        topics: room.topics,
        members: room.members,
        sessions: room.sessions,
      },
    });
    const recipient = within(screen.getByRole("row", { name: /前端 Worker/ }));
    expect(screen.queryByText("人为删除")).toBeNull();
    expect(recipient.getAllByRole("cell")[1].textContent?.trim()).toBe("-");
  });

  it.each([
    { status: "rejected", error: "队列拒绝接收" },
    { status: "unknown", error: "入队结果待确认" },
  ] as const)("keeps the failure explanation for $status deliveries", ({ status, error }) => {
    const room = roomFixture();
    const delivery = { ...room.messages[0].deliveries[0], status, error };
    const message = {
      ...room.messages[0],
      recipientIds: [delivery.targetMemberId],
      deliveries: [delivery],
    };
    render(MessageDetails, {
      props: { message, topics: room.topics, members: room.members, sessions: room.sessions },
    });

    const recipient = within(screen.getByRole("row", { name: /前端 Worker/ }));
    expect(recipient.getByText(status === "rejected" ? "发送失败" : "发送待确认")).toBeTruthy();
    expect(recipient.getByText(error)).toBeTruthy();
  });

  it("omits the Agent delivery table for messages addressed only to the room user", () => {
    const room = roomFixture();
    const message: RoomMessage = {
      ...room.messages[1],
      topicIds: [],
      mentionedMemberIds: ["user"],
      recipientIds: ["user"],
      deliveries: [],
    };
    render(MessageDetails, {
      props: { message, topics: room.topics, members: room.members, sessions: room.sessions },
    });

    expect(screen.queryByRole("table", { name: "成员" })).toBeNull();
    expect(screen.getByText("未选择话题")).toBeTruthy();
  });
});
