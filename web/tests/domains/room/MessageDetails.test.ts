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
      "入队状态",
      "接收状态",
      "回执状态",
    ]);
    const queued = within(screen.getByRole("row", { name: /前端 Worker/ }));
    expect(queued.getByText("排队中")).toBeTruthy();
    expect(queued.getByText("待接收")).toBeTruthy();
    const enqueued = within(screen.getByRole("row", { name: /测试 Worker/ }));
    expect(enqueued.getByText("已入队")).toBeTruthy();
    expect(enqueued.getByText("未确认")).toBeTruthy();
    expect(enqueued.getByText("待回执")).toBeTruthy();
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
});
