import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import TopicSidebar from "@/domains/room/TopicSidebar.vue";

import { roomFixture } from "../../fixtures/room";

describe("TopicSidebar", () => {
  beforeEach(() => localStorage.clear());
  afterEach(cleanup);

  it("selects topics and exposes separate edit and delete actions", async () => {
    const snapshot = roomFixture();
    const topic = snapshot.topics[1];
    const { emitted } = render(TopicSidebar, { props: { snapshot, busy: false } });

    expect(screen.getByRole("heading", { level: 2, name: "话题" })).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "筛选话题：前端" }));
    await fireEvent.click(screen.getByRole("button", { name: "编辑话题：前端" }));
    await fireEvent.click(screen.getByRole("button", { name: "删除话题：前端" }));
    expect(emitted().select).toEqual([[topic.id]]);
    expect(emitted().editTopic).toEqual([[topic]]);
    expect(emitted().deleteTopic).toEqual([[topic]]);
  });

  it("reorders topics without moving all messages and restores the order after reopening", async () => {
    const snapshot = roomFixture();
    const { emitted, unmount } = render(TopicSidebar, { props: { snapshot, busy: false } });

    await fireEvent.keyDown(screen.getByRole("button", { name: "调整话题顺序：前端" }), {
      key: "ArrowUp",
    });
    expect(
      screen
        .getAllByRole("button", { name: /^(全部消息|筛选话题：)/ })
        .map((button) => button.getAttribute("aria-label")),
    ).toEqual([null, "筛选话题：前端", "筛选话题：汇总", "筛选话题：后端"]);
    expect(emitted().select).toBeUndefined();

    unmount();
    render(TopicSidebar, { props: { snapshot, busy: false } });
    expect(
      screen
        .getAllByRole("button", { name: /^筛选话题：/ })
        .map((button) => button.getAttribute("aria-label")),
    ).toEqual(["筛选话题：前端", "筛选话题：汇总", "筛选话题：后端"]);
  });
});
