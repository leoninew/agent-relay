import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MemberPanel from "@/domains/room/MemberPanel.vue";

import { roomFixture } from "../../fixtures/room";

describe("MemberPanel", () => {
  afterEach(cleanup);

  it("filters subscribed members by topic and keeps member actions available", async () => {
    const snapshot = roomFixture();
    const { rerender, emitted } = render(MemberPanel, { props: { snapshot, busy: false } });

    await rerender({ selectedTopicId: "frontend" });
    expect(screen.getByRole("button", { name: "筛选成员：前端 Worker" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "筛选成员：测试 Worker" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "筛选成员：后端 Worker" })).toBeNull();

    await rerender({ selectedTopicId: "backend" });
    expect(screen.getByRole("button", { name: "筛选成员：后端 Worker" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "筛选成员：测试 Worker" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "筛选成员：前端 Worker" })).toBeNull();

    await rerender({ selectedTopicId: undefined });
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
