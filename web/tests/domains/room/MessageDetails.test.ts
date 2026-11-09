import { cleanup, render, screen, within } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MessageDetails from "@/domains/room/MessageDetails.vue";
import type { RoomMessage } from "@/services/roomApi";

import { roomFixture } from "../../fixtures/room";

describe("MessageDetails", () => {
  afterEach(cleanup);

  it("shows topics and recipient dispatch states without inferring reception or receipts", () => {
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
    const memberTags = within(screen.getByRole("list", { name: "@ 成员" }));
    expect(memberTags.getAllByRole("listitem")).toHaveLength(1);
    expect(memberTags.queryByText("前端 Worker")).toBeNull();
    expect(memberTags.getByText("测试 Worker")).toBeTruthy();
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "成员",
      "投递状态",
    ]);
    const queued = within(screen.getByRole("row", { name: /前端 Worker/ }));
    expect(queued.getByText("提交中")).toBeTruthy();
    const enqueued = within(screen.getByRole("row", { name: /测试 Worker/ }));
    expect(enqueued.getByText("已入队")).toBeTruthy();
    expect(screen.queryByText(message.content)).toBeNull();
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
    expect(screen.getByRole("row", { name: /前端 Worker/ })).toBeTruthy();
    expect(screen.queryByRole("row", { name: /测试 Worker/ })).toBeNull();
  });

  it("shows confirmed original-session input evidence separately from queue acceptance", () => {
    const room = roomFixture();
    const delivery = {
      ...room.messages[0].deliveries[0],
      status: "received" as const,
      queuedAt: "2026-11-08T04:00:01Z",
      receivedAt: "2026-11-08T04:00:03Z",
      updatedAt: "2026-11-08T04:00:03Z",
      receivedItemId: "original-input",
      receivedTurnId: "original-turn",
    };
    const message = {
      ...room.messages[0],
      recipientIds: [delivery.targetMemberId],
      deliveries: [delivery],
    };
    render(MessageDetails, { props: { message, topics: room.topics, members: room.members } });
    expect(screen.getByText("已进入会话")).toBeTruthy();
    expect(screen.getByText("投递凭证")).toBeTruthy();
    expect(screen.getByText("original-input")).toBeTruthy();
    expect(screen.getByText(/入队 \d{2}:\d{2}:\d{2}/)).toBeTruthy();
    expect(document.querySelector("time")?.getAttribute("datetime")).toBe(delivery.receivedAt);
  });

  it("shows an unsubmitted delivery without implying queue acceptance", () => {
    const room = roomFixture();
    const delivery = { ...room.messages[0].deliveries[0], status: "pending" as const };
    const message = {
      ...room.messages[0],
      recipientIds: [delivery.targetMemberId],
      deliveries: [delivery],
    };
    render(MessageDetails, { props: { message, topics: room.topics, members: room.members } });

    expect(screen.getByText("待提交")).toBeTruthy();
    expect(screen.queryByText("已入队")).toBeNull();
    expect(screen.queryByText("待接收")).toBeNull();
    expect(screen.queryByText("待回执")).toBeNull();
    const time = screen.getByText(/\d{2}:\d{2}:\d{2}/);
    expect(time.getAttribute("datetime")).toBe(delivery.updatedAt);
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
