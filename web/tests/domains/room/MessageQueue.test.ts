import { cleanup, fireEvent, render, screen, within } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MessageQueue from "@/domains/room/MessageQueue.vue";

import { roomFixture } from "../../fixtures/room";

function props() {
  const room = roomFixture();
  return {
    messages: [...room.messages].reverse(),
    totalMessages: 2,
    hasMore: false,
    loading: false,
    loadingMore: false,
    clearing: false,
    error: null as string | null,
    clearError: null as string | null,
  };
}

describe("MessageQueue", () => {
  afterEach(cleanup);

  it("shows fifteen-character previews and one delivery stage column", async () => {
    const input = props();
    const message = input.messages[0];
    message.content = "一二三四五六七八九十甲乙丙丁😀额外内容";
    message.deliveries = [{ ...message.deliveries[0], status: "queued" }];
    const { emitted } = render(MessageQueue, { props: input });
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "消息",
      "状态",
    ]);
    expect(
      within(screen.getAllByRole("row")[1])
        .getAllByRole("cell")
        .map((cell) => cell.textContent?.trim()),
    ).toEqual(["一二三四五六七八九十甲乙丙丁😀…", "接收中"]);
    expect(screen.getByText(input.messages[1].content)).toBeTruthy();
    const preview = screen.getByRole("button", { name: "查看消息 #2 详情" });
    expect(preview.getAttribute("title")).toBe(message.content);
    await fireEvent.click(preview);
    expect(emitted().select).toEqual([[message.id]]);
  });

  it("summarizes the earliest unfinished stage and ignores manually removed deliveries", async () => {
    const input = props();
    const message = input.messages[0];
    message.deliveries = [{ ...message.deliveries[0], status: "queued" }];
    const { rerender } = render(MessageQueue, { props: input });
    const stage = () => within(screen.getAllByRole("row")[1]).getAllByRole("cell")[1].textContent;
    expect(stage()).toBe("接收中");
    await rerender({
      messages: [
        {
          ...message,
          deliveries: [
            ...message.deliveries,
            { ...message.deliveries[0], id: "received-delivery", status: "received" },
          ],
        },
      ],
    });
    expect(stage()).toBe("接收中");
    await rerender({
      messages: [
        {
          ...message,
          deliveries: [
            ...message.deliveries,
            { ...message.deliveries[0], id: "pending-delivery", status: "pending" },
          ],
        },
      ],
    });
    expect(stage()).toBe("入队中");
    await rerender({
      messages: [{ ...message, deliveries: [{ ...message.deliveries[0], status: "received" }] }],
    });
    expect(stage()).toBe("已接收");
    await rerender({
      messages: [
        {
          ...message,
          deliveries: [
            { ...message.deliveries[0], status: "received" },
            {
              ...message.deliveries[0],
              id: "removed-delivery",
              status: "pending",
              deletedAt: "2026-11-10T14:00:00Z",
            },
          ],
        },
      ],
    });
    expect(stage()).toBe("已接收");
  });

  it("shows an empty state only after a successful load and allows retrying failures", async () => {
    const { emitted, rerender } = render(MessageQueue, {
      props: { ...props(), messages: [], totalMessages: 0, loading: true },
    });
    expect(screen.getByText("正在加载队列…")).toBeTruthy();
    expect(screen.queryByText("暂无入队中或接收中的消息")).toBeNull();
    await rerender({ loading: false, error: "队列暂不可用" });
    expect(screen.getByRole("alert").textContent).toContain("队列暂不可用");
    expect(screen.queryByText("暂无入队中或接收中的消息")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(emitted().refresh).toHaveLength(1);
    await rerender({ error: null });
    expect(screen.getByText("暂无入队中或接收中的消息")).toBeTruthy();
  });

  it("loads older messages on demand", async () => {
    const { emitted } = render(MessageQueue, { props: { ...props(), hasMore: true } });
    await fireEvent.click(screen.getByRole("button", { name: "加载更多消息" }));
    expect(emitted().loadMore).toHaveLength(1);
  });

  it("clears the current queue and disables actions while clearing or when empty", async () => {
    const { emitted, rerender } = render(MessageQueue, { props: props() });
    expect(screen.getByRole("heading", { level: 3, name: "队列" })).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "清空队列" }));
    expect(emitted().clear).toEqual([[]]);
    await rerender({ clearing: true });
    expect(screen.getByRole("button", { name: "清空队列" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "刷新队列" }).hasAttribute("disabled")).toBe(true);
    await rerender({ clearing: false, clearError: "队列清空失败，请重试。" });
    expect(screen.getByRole("alert").textContent).toBe("队列清空失败，请重试。");
    await rerender({ messages: [], totalMessages: 0, clearError: null });
    expect(screen.getByRole("button", { name: "清空队列" }).hasAttribute("disabled")).toBe(true);
  });
});
