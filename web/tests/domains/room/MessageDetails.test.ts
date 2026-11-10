import { cleanup, fireEvent, render, screen, within } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MessageDetails from "@/domains/room/MessageDetails.vue";
import type { RoomMessage } from "@/services/roomApi";
import { formatMinute } from "@/utils/time";

import { roomFixture } from "../../fixtures/room";

describe("MessageDetails", () => {
  afterEach(cleanup);

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
    expect(topicIdentity?.querySelector(".sidebar-item-meta")?.textContent).toBe(
      String(topic.messageCount),
    );
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
    expect(memberIdentity?.classList.contains("is-active")).toBe(false);
    expect(memberIdentity?.querySelector(".member-identity")).not.toBeNull();
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

  it("shows queue and receipt timestamps for recipients", () => {
    const room = roomFixture();
    const queuedAt = "2026-11-06T10:02:00Z";
    const message: RoomMessage = {
      ...room.messages[1],
      topicIds: ["frontend", "backend"],
      recipientIds: ["frontend-worker", "test-worker"],
      deliveries: room.messages[0].deliveries.map((delivery) =>
        delivery.targetMemberId === "test-worker" ? { ...delivery, queuedAt } : delivery,
      ),
    };
    render(MessageDetails, {
      props: { message, topics: room.topics, members: room.members, sessions: room.sessions },
    });

    expect(screen.getByText("# 前端")).toBeTruthy();
    expect(screen.getByText("# 后端")).toBeTruthy();
    const mentionedMembers = within(screen.getByRole("list", { name: "成员" }));
    expect(mentionedMembers.getAllByRole("listitem")).toHaveLength(1);
    expect(mentionedMembers.queryByText("前端 Worker")).toBeNull();
    expect(mentionedMembers.getByText("测试 Worker")).toBeTruthy();
    const deliveries = within(screen.getByRole("table", { name: "分发状态" }));
    expect(deliveries.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "成员",
      "入队",
      "接收",
    ]);
    const submitting = within(deliveries.getByRole("row", { name: /前端 Worker/ }));
    expect(submitting.getAllByRole("cell")[1].textContent?.trim()).toBe("—");
    const enqueued = within(deliveries.getByRole("row", { name: /测试 Worker/ }));
    const enqueuedCells = enqueued.getAllByRole("cell");
    expect(enqueuedCells[1].querySelector("time")?.getAttribute("datetime")).toBe(queuedAt);
    expect(enqueuedCells[1].textContent?.trim()).toBe(formatMinute(queuedAt));
    expect(enqueuedCells[2].textContent?.trim()).toBe("—");
    expect(screen.getByText(message.content)).toBeTruthy();
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
    const deliveries = within(screen.getByRole("table", { name: "分发状态" }));
    expect(deliveries.getByRole("row", { name: /前端 Worker/ })).toBeTruthy();
    expect(deliveries.queryByRole("row", { name: /测试 Worker/ })).toBeNull();
  });

  it("shows the recorded queue and receipt times separately", () => {
    const room = roomFixture();
    const queuedAt = "2026-11-06T10:03:00Z";
    const receivedAt = "2026-11-06T10:03:04Z";
    const delivery = {
      ...room.messages[0].deliveries[0],
      status: "received" as const,
      queuedAt,
      receivedAt,
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
    const cells = recipient.getAllByRole("cell");
    expect(cells[1].querySelector("time")?.getAttribute("datetime")).toBe(queuedAt);
    expect(cells[2].querySelector("time")?.getAttribute("datetime")).toBe(receivedAt);
    expect(cells[1].textContent?.trim()).toBe(formatMinute(queuedAt));
    expect(cells[2].textContent?.trim()).toBe(formatMinute(receivedAt));
  });

  it.each([
    { status: "pending", error: null },
    { status: "rejected", error: "队列拒绝接收" },
  ] as const)("does not invent timestamps for $status deliveries", ({ status, error }) => {
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
    const cells = recipient.getAllByRole("cell");
    expect(cells[1].querySelector(".dispatch-time")?.textContent?.trim()).toBe("—");
    expect(cells[2].textContent?.trim()).toBe("—");
    if (error) expect(within(cells[1]).getByText(error)).toBeTruthy();
  });

  it("shows the user as a member without inventing an agent delivery", () => {
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

    expect(within(screen.getByRole("list", { name: "成员" })).getByText("你")).toBeTruthy();
    expect(screen.queryByText("分发状态")).toBeNull();
    expect(screen.queryByText("暂无分发")).toBeNull();
    expect(screen.getByText("未选择话题")).toBeTruthy();
  });
});
