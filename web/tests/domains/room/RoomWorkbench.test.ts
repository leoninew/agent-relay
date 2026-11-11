import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RoomWorkbench from "@/domains/room/RoomWorkbench.vue";

function setViewport(width: number): void {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: width <= Number(query.match(/\d+/)?.[0]),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

function renderWorkbench() {
  return render(RoomWorkbench, {
    props: { detailsOpen: false },
    slots: {
      sidebar: '<aside aria-label="话题与成员">导航内容</aside>',
      default: '<section aria-label="聊天室">消息内容</section>',
      details: '<aside aria-label="详情与队列">详情内容</aside>',
    },
  });
}

describe("RoomWorkbench", () => {
  beforeEach(() => {
    setViewport(1440);
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
      new DOMRect(0, 0, 1400, 800),
    );
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it.each([
    ["左", "话题与成员", "ArrowRight"],
    ["右", "详情与队列", "ArrowLeft"],
  ])(
    "collapses the %s panel and restores its contents from the bottom icon",
    async (side, label, key) => {
      renderWorkbench();
      expect(screen.getByRole("complementary", { name: label })).toBeTruthy();

      const handle = screen.getByRole("separator", { name: `调整${side}侧面板宽度` });
      await waitFor(() => expect(handle.getAttribute("aria-valuenow")).not.toBeNull());
      const initialSize = handle.getAttribute("aria-valuenow");
      await fireEvent.keyDown(handle, { key });
      expect(handle.getAttribute("aria-valuenow")).not.toBe(initialSize);
      await fireEvent.doubleClick(handle);

      expect(screen.queryByRole("complementary", { name: label })).toBeNull();
      expect(screen.getByRole("region", { name: "聊天室" })).toBeTruthy();
      await fireEvent.click(screen.getByRole("button", { name: `展开${side}侧面板` }));

      expect(screen.getByRole("complementary", { name: label })).toBeTruthy();
      expect(screen.queryByRole("button", { name: `展开${side}侧面板` })).toBeNull();
      expect(handle.getAttribute("aria-valuenow")).toBe(initialSize);

      await fireEvent.keyDown(handle, { key: "Enter" });
      expect(screen.queryByRole("complementary", { name: label })).toBeNull();
      await fireEvent.keyDown(handle, { key: "Enter" });
      expect(screen.getByRole("complementary", { name: label })).toBeTruthy();
      expect(handle.getAttribute("aria-valuenow")).toBe(initialSize);
    },
  );

  it("reopens collapsed details when a new selection asks to show them", async () => {
    const { emitted, rerender } = renderWorkbench();
    const handle = screen.getByRole("separator", { name: "调整右侧面板宽度" });
    await waitFor(() => expect(handle.getAttribute("aria-valuenow")).not.toBeNull());

    await fireEvent.keyDown(handle, { key: "Enter" });
    expect(screen.queryByRole("complementary", { name: "详情与队列" })).toBeNull();
    expect(emitted().collapseDetails).toEqual([[]]);

    await rerender({ detailsOpen: true });

    expect(screen.getByRole("complementary", { name: "详情与队列" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "展开右侧面板" })).toBeNull();
  });

  it("keeps details in the drawer on compact screens", () => {
    setViewport(1000);
    renderWorkbench();
    expect(screen.getAllByRole("separator")).toHaveLength(1);
    expect(
      screen.getByText("详情内容").closest(".room-context-panel")?.classList.contains("is-open"),
    ).toBe(false);
  });

  it("lets phone users expand and collapse navigation while keeping the conversation available", async () => {
    setViewport(390);
    renderWorkbench();
    const toggle = screen.getByRole("button", { name: "话题与成员" });
    expect(screen.queryByRole("separator")).toBeNull();
    expect(screen.queryByRole("complementary", { name: "话题与成员" })).toBeNull();
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByRole("region", { name: "聊天室" })).toBeTruthy();

    await fireEvent.click(toggle);
    expect(await screen.findByRole("complementary", { name: "话题与成员" })).toBeTruthy();
    expect(toggle.getAttribute("aria-expanded")).toBe("true");

    await fireEvent.click(toggle);
    await waitFor(() =>
      expect(screen.queryByRole("complementary", { name: "话题与成员" })).toBeNull(),
    );
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByRole("region", { name: "聊天室" })).toBeTruthy();
  });
});
