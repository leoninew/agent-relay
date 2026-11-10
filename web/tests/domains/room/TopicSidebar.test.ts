import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import TopicSidebar from "@/domains/room/TopicSidebar.vue";

import { roomFixture } from "../../fixtures/room";

describe("TopicSidebar", () => {
  beforeEach(() => localStorage.clear());
  afterEach(cleanup);

  it("defaults to all topics and emits explicit selection changes", async () => {
    const snapshot = roomFixture();
    const topic = snapshot.topics[1];
    const { emitted, rerender } = render(TopicSidebar, { props: { snapshot, busy: false } });
    const allTopics = screen.getByRole("button", { name: "筛选话题：全部话题" });
    const frontend = screen.getByRole("button", { name: "筛选话题：前端" });

    expect(screen.getByRole("heading", { level: 2, name: "话题" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /^筛选话题：/ })[0]).toBe(allTopics);
    expect(allTopics.getAttribute("aria-pressed")).toBe("true");
    expect(frontend.getAttribute("aria-pressed")).toBe("false");
    expect(allTopics.closest(".sidebar-sortable-list")).toBeNull();
    expect(screen.queryByRole("button", { name: "调整话题顺序：全部话题" })).toBeNull();
    await fireEvent.click(allTopics);
    await fireEvent.click(frontend);
    await rerender({ selectedTopicId: topic.id });
    expect(allTopics.getAttribute("aria-pressed")).toBe("false");
    expect(frontend.getAttribute("aria-pressed")).toBe("true");
    await fireEvent.click(frontend);
    await fireEvent.click(allTopics);
    await rerender({ selectedTopicId: undefined });
    expect(allTopics.getAttribute("aria-pressed")).toBe("true");
    expect(frontend.getAttribute("aria-pressed")).toBe("false");
    expect(emitted().select).toEqual([[undefined], [topic.id], [topic.id], [undefined]]);
  });

  it("reorders topics and restores the order after reopening", async () => {
    const snapshot = roomFixture();
    const { emitted, unmount } = render(TopicSidebar, { props: { snapshot, busy: false } });

    await fireEvent.keyDown(screen.getByRole("button", { name: "调整话题顺序：前端" }), {
      key: "ArrowUp",
    });
    expect(
      screen
        .getAllByRole("button", { name: /^筛选话题：/ })
        .map((button) => button.getAttribute("aria-label")),
    ).toEqual(["筛选话题：全部话题", "筛选话题：前端", "筛选话题：汇总", "筛选话题：后端"]);
    expect(emitted().select).toBeUndefined();

    unmount();
    render(TopicSidebar, { props: { snapshot, busy: false } });
    expect(
      screen
        .getAllByRole("button", { name: /^筛选话题：/ })
        .map((button) => button.getAttribute("aria-label")),
    ).toEqual(["筛选话题：全部话题", "筛选话题：前端", "筛选话题：汇总", "筛选话题：后端"]);
  });
});
