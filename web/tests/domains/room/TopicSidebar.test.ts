import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import TopicSidebar from "@/domains/room/TopicSidebar.vue";

import { roomFixture } from "../../fixtures/room";

describe("TopicSidebar", () => {
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
});
