import { cleanup, fireEvent, render, screen, within } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MessageQueue from "@/domains/room/MessageQueue.vue";

import { roomFixture } from "../../fixtures/room";

function props() {
  const room = roomFixture();
  return {
    messages: [...room.messages].reverse(),
    hasMore: false,
    loading: false,
    loadingMore: false,
    removingId: null as string | null,
    error: null as string | null,
    removeError: null as string | null,
  };
}

describe("MessageQueue", () => {
  afterEach(cleanup);

  it("shows fifteen-character previews, delivery stages and row actions", async () => {
    const input = props();
    const message = input.messages[0];
    message.content = "一二三四五六七八九十甲乙丙丁😀额外内容";
    message.deliveries = [{ ...message.deliveries[0], status: "queued" }];
    const { emitted } = render(MessageQueue, { props: input });
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "消息",
      "状态",
      "操作",
    ]);
    expect(
      within(screen.getAllByRole("row")[1])
        .getAllByRole("cell")
        .map((cell) => cell.textContent?.trim()),
    ).toEqual(["一二三四五六七八九十甲乙丙丁😀…", "接收中", ""]);
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
    expect(stage()).toBe("发送中");
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
      props: { ...props(), messages: [], loading: true },
    });
    expect(screen.getByText("正在加载队列…")).toBeTruthy();
    expect(screen.queryByText("暂无发送中或接收中的消息")).toBeNull();
    await rerender({ loading: false, error: "队列暂不可用" });
    expect(screen.getByRole("alert").textContent).toContain("队列暂不可用");
    expect(screen.queryByText("暂无发送中或接收中的消息")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(emitted().refresh).toHaveLength(1);
    await rerender({ error: null });
    expect(screen.getByText("暂无发送中或接收中的消息")).toBeTruthy();
  });

  it("loads older messages on demand", async () => {
    const { emitted } = render(MessageQueue, { props: { ...props(), hasMore: true } });
    await fireEvent.click(screen.getByRole("button", { name: "加载更多消息" }));
    expect(emitted().loadMore).toHaveLength(1);
  });

  it("removes only the selected row and disables mutations while removing", async () => {
    const input = props();
    const message = input.messages[0];
    const { emitted, rerender } = render(MessageQueue, { props: input });
    expect(screen.getByRole("heading", { level: 3, name: "队列" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "清空队列" })).toBeNull();
    const remove = screen.getByRole("button", { name: `删除消息 #${message.seq} 的队列记录` });
    expect(screen.getAllByRole("button", { name: /删除消息 #\d+ 的队列记录/ })).toHaveLength(2);
    expect(remove.getAttribute("title")).toBe("移除这条待办记录，不会撤回已送入会话的内容");
    await fireEvent.click(remove);
    expect(emitted().remove).toEqual([[message.id]]);
    expect(emitted().select).toBeUndefined();
    await rerender({ removingId: message.id });
    expect(remove.getAttribute("aria-busy")).toBe("true");
    for (const button of screen.getAllByRole("button", { name: /删除消息 #\d+ 的队列记录/ }))
      expect(button.hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "刷新队列" }).hasAttribute("disabled")).toBe(true);
    await rerender({ removingId: null, removeError: "队列记录删除失败，请重试。" });
    expect(screen.getByRole("alert").textContent).toBe("队列记录删除失败，请重试。");
    expect(remove.hasAttribute("disabled")).toBe(false);
    await rerender({ messages: [], removeError: null });
    expect(screen.queryByRole("button", { name: /删除消息 #\d+ 的队列记录/ })).toBeNull();
  });
});
