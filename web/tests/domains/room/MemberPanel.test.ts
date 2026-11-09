import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MemberPanel from "@/domains/room/MemberPanel.vue";

import { roomFixture } from "../../fixtures/room";

describe("MemberPanel", () => {
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
    expect(screen.queryByRole("region", { name: "你的查阅位置" })).toBeNull();
    expect(screen.queryByText("管理员")).toBeNull();
    await fireEvent.click(user);
    expect(emitted().select).toEqual([["user"]]);
  });

  it("lists active senders independently of their subscriptions and exposes member actions", async () => {
    const snapshot = roomFixture();
    snapshot.members[2].topicIds = [];
    snapshot.members[0].presence = "unknown";
    snapshot.members[0].activity = "当前 Codex daemon 未加载会话；宿主运行状态未知";
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
});
