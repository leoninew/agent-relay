import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import MemberPanel from "@/domains/room/MemberPanel.vue";

import { roomFixture } from "../../fixtures/room";

describe("MemberPanel", () => {
  beforeEach(() => localStorage.clear());
  afterEach(cleanup);

  it("defaults to all members and keeps explicit member selections", async () => {
    const snapshot = roomFixture();
    const { emitted, rerender } = render(MemberPanel, {
      props: { snapshot, busy: false },
    });
    const allMembers = screen.getByRole("button", { name: "筛选成员：全部成员" });
    const user = screen.getByRole("button", { name: "筛选成员：你" });
    expect(screen.getAllByRole("button", { name: /^筛选成员：/ }).slice(0, 2)).toEqual([
      allMembers,
      user,
    ]);
    expect(allMembers.getAttribute("aria-pressed")).toBe("true");
    expect(user.getAttribute("aria-pressed")).toBe("false");
    expect(allMembers.closest(".sidebar-sortable-list")).toBeNull();
    expect(screen.queryByRole("button", { name: "调整成员顺序：全部成员" })).toBeNull();
    expect(user.textContent).not.toContain("空闲");
    expect(screen.queryByRole("button", { name: "调整成员顺序：你" })).toBeNull();
    expect(screen.queryByText("管理员")).toBeNull();
    await fireEvent.click(allMembers);
    await fireEvent.click(user);
    await rerender({ selectedMemberId: "user" });
    expect(allMembers.getAttribute("aria-pressed")).toBe("false");
    expect(user.getAttribute("aria-pressed")).toBe("true");
    await fireEvent.click(user);
    await fireEvent.click(allMembers);
    await rerender({ selectedMemberId: undefined });
    expect(allMembers.getAttribute("aria-pressed")).toBe("true");
    expect(user.getAttribute("aria-pressed")).toBe("false");
    expect(emitted().select).toEqual([[undefined], ["user"], ["user"], [undefined]]);
  });

  it("lists active senders independently of subscriptions", async () => {
    const snapshot = roomFixture();
    snapshot.members[2].topicIds = [];
    snapshot.members[0].presence = "unknown";
    const { emitted } = render(MemberPanel, { props: { snapshot, busy: false } });
    expect(screen.getByRole("button", { name: "筛选成员：前端 Worker" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "筛选成员：测试 Worker" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "筛选成员：后端 Worker" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "筛选成员：前端 Worker" }).textContent).toContain(
      "接入未确认",
    );
    await fireEvent.click(screen.getByRole("button", { name: "筛选成员：前端 Worker" }));
    await fireEvent.click(screen.getByRole("button", { name: "添加成员" }));
    expect(emitted().select).toEqual([[snapshot.members[0].id]]);
    expect(emitted().addMember).toEqual([[]]);
    expect(screen.getByRole("button", { name: "筛选成员：后端 Worker" })).toBeTruthy();
  });

  it("reorders agents while keeping the user fixed above them", async () => {
    const snapshot = roomFixture();
    const { emitted, rerender } = render(MemberPanel, { props: { snapshot, busy: false } });

    await fireEvent.keyDown(screen.getByRole("button", { name: "调整成员顺序：后端 Worker" }), {
      key: "ArrowUp",
    });
    expect(emitted().select).toBeUndefined();

    const refreshed = roomFixture();
    refreshed.members[1].name = "后端更新";
    refreshed.members[1].presence = "offline";
    refreshed.members[2].deletedAt = "2026-11-09T10:00:00Z";
    await rerender({ snapshot: refreshed });

    expect(
      screen
        .getAllByRole("button", { name: /^筛选成员：/ })
        .map((button) => button.getAttribute("aria-label")),
    ).toEqual([
      "筛选成员：全部成员",
      "筛选成员：你",
      "筛选成员：后端更新",
      "筛选成员：前端 Worker",
    ]);
    expect(screen.getByRole("button", { name: "筛选成员：后端更新" }).textContent).toContain(
      "离线",
    );
    expect(screen.queryByRole("button", { name: "调整成员顺序：你" })).toBeNull();
  });
});
