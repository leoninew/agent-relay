import { cleanup, render, screen, within } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MessageDetails from "@/domains/room/MessageDetails.vue";
import type { RoomMessage } from "@/services/roomApi";

import { roomFixture } from "../../fixtures/room";

describe("MessageDetails", () => {
  afterEach(cleanup);

  it("shows topics and recipient queue states without inferring session entry", () => {
    const room = roomFixture();
    const message: RoomMessage = {
      ...room.messages[1],
      topicIds: ["frontend", "backend"],
      recipientIds: ["frontend-worker", "test-worker"],
      deliveries: room.messages[0].deliveries,
    };
    render(MessageDetails, { props: { message, topics: room.topics, members: room.members } });

    expect(screen.getByText("# 前端")).toBeTruthy();
    expect(screen.getByText("# 后端")).toBeTruthy();
    const mentionedMembers = within(screen.getByRole("list", { name: "@ 成员" }));
    expect(mentionedMembers.getAllByRole("listitem")).toHaveLength(1);
    expect(mentionedMembers.queryByText("前端 Worker")).toBeNull();
    expect(mentionedMembers.getByText("测试 Worker")).toBeTruthy();
    const deliveries = within(screen.getByRole("table", { name: "分发状态" }));
    expect(deliveries.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "成员",
      "入队",
      "进入会话",
    ]);
    const queued = within(deliveries.getByRole("row", { name: /前端 Worker/ }));
    expect(queued.getByText("提交中")).toBeTruthy();
    const enqueued = within(deliveries.getByRole("row", { name: /测试 Worker/ }));
    expect(enqueued.getByText("已入队")).toBeTruthy();
    expect(enqueued.getAllByRole("cell")[2].textContent?.trim()).toBe("—");
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
    render(MessageDetails, { props: { message, topics: room.topics, members: room.members } });

    expect(screen.getByText("未选择话题")).toBeTruthy();
    const deliveries = within(screen.getByRole("table", { name: "分发状态" }));
    expect(deliveries.getByRole("row", { name: /前端 Worker/ })).toBeTruthy();
    expect(deliveries.queryByRole("row", { name: /测试 Worker/ })).toBeNull();
  });

  it("shows queue acceptance and confirmed session entry separately", () => {
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
    render(MessageDetails, { props: { message, topics: room.topics, members: room.members } });
    const recipient = within(screen.getByRole("row", { name: /前端 Worker/ }));
    const cells = recipient.getAllByRole("cell");
    expect(cells[1].textContent?.trim()).toBe("已入队");
    expect(cells[2].textContent?.trim()).toBe("已进入");
  });

  it.each([
    { status: "pending", label: "待提交", error: null },
    { status: "rejected", label: "已拒绝", error: "队列拒绝接收" },
  ] as const)("shows $status without implying session entry", ({ status, label, error }) => {
    const room = roomFixture();
    const delivery = { ...room.messages[0].deliveries[0], status, error };
    const message = {
      ...room.messages[0],
      recipientIds: [delivery.targetMemberId],
      deliveries: [delivery],
    };
    render(MessageDetails, { props: { message, topics: room.topics, members: room.members } });

    const recipient = within(screen.getByRole("row", { name: /前端 Worker/ }));
    expect(recipient.getByText(label)).toBeTruthy();
    expect(recipient.getAllByRole("cell")[2].textContent?.trim()).toBe("—");
    if (error) expect(recipient.getByText(error)).toBeTruthy();
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
    render(MessageDetails, { props: { message, topics: room.topics, members: room.members } });

    expect(within(screen.getByRole("list", { name: "@ 成员" })).getAllByText("你")).toHaveLength(2);
    expect(screen.queryByText("分发状态")).toBeNull();
    expect(screen.queryByText("暂无分发")).toBeNull();
    expect(screen.getByText("未选择话题")).toBeTruthy();
  });
});
