import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import MemberPanel from "@/domains/room/MemberPanel.vue";

import { roomFixture } from "../../fixtures/room";

describe("MemberPanel", () => {
  beforeEach(() => localStorage.clear());
  afterEach(cleanup);

  it("pins the fixed user without session status, editing or deletion", async () => {
    const snapshot = roomFixture();
    const { emitted } = render(MemberPanel, {
      props: { snapshot, busy: false, selectedMemberId: "user" },
    });
    const user = screen.getByRole("button", { name: "筛选成员：你" });
    expect(screen.getAllByRole("button", { name: /^筛选成员：/ })[0]).toBe(user);
    expect(user.textContent).not.toContain("空闲");
    expect(screen.queryByRole("button", { name: "编辑成员：你" })).toBeNull();
    expect(screen.queryByRole("button", { name: "删除成员：你" })).toBeNull();
    expect(screen.queryByRole("button", { name: "调整成员顺序：你" })).toBeNull();
    expect(screen.queryByText("管理员")).toBeNull();
    await fireEvent.click(user);
    expect(emitted().select).toEqual([["user"]]);
  });

  it("lists active senders independently of their subscriptions and exposes member actions", async () => {
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
    await fireEvent.click(screen.getByRole("button", { name: "编辑成员：前端 Worker" }));
    await fireEvent.click(screen.getByRole("button", { name: "删除成员：前端 Worker" }));
    await fireEvent.click(screen.getByRole("button", { name: "添加成员" }));
    expect(emitted().select).toEqual([[snapshot.members[0].id]]);
    expect(emitted().deleteMember).toEqual([[snapshot.members[0]]]);
    expect(emitted().editMember).toEqual([[snapshot.members[0]]]);
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
    ).toEqual(["筛选成员：你", "筛选成员：后端更新", "筛选成员：前端 Worker"]);
    expect(screen.getByRole("button", { name: "筛选成员：后端更新" }).textContent).toContain(
      "离线",
    );
    expect(screen.queryByRole("button", { name: "调整成员顺序：你" })).toBeNull();
  });
});
