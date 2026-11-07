import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import RoomComposer from "@/domains/room/RoomComposer.vue";
import type { CreateMessage } from "@/services/roomApi";

import { roomFixture } from "../../fixtures/room";

describe("RoomComposer", () => {
  afterEach(cleanup);

  function renderComposer(draft?: CreateMessage) {
    const room = roomFixture();
    return render(RoomComposer, {
      props: {
        roomId: room.room.id,
        topics: room.topics,
        members: room.members,
        draft,
        sending: false,
        error: null,
      },
    });
  }

  it("sends to topics without requiring a member selection", async () => {
    const { emitted } = renderComposer();
    await fireEvent.click(screen.getByRole("checkbox", { name: "消息话题：前端" }));
    await fireEvent.click(screen.getByRole("checkbox", { name: "消息话题：后端" }));
    await fireEvent.update(screen.getByRole("textbox", { name: "消息内容" }), " 一起核对接口 ");
    await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    expect(emitted().send).toEqual([
      [
        {
          content: "一起核对接口",
          topicIds: ["frontend", "backend"],
          mentionedMemberIds: [],
        },
      ],
    ]);
  });

  it("sends to a mentioned member without a topic, including in a room with no topics", async () => {
    const { emitted, rerender } = renderComposer();
    await rerender({ topics: [] });
    await fireEvent.click(screen.getByRole("checkbox", { name: "@ 前端 Worker" }));
    await fireEvent.update(screen.getByRole("textbox", { name: "消息内容" }), "请核对界面");
    await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    expect(emitted().send).toEqual([
      [{ content: "请核对界面", topicIds: [], mentionedMemberIds: ["frontend-worker"] }],
    ]);
  });

  it("combines topics with mentions regardless of their subscriptions", async () => {
    const { emitted } = renderComposer();
    await fireEvent.click(screen.getByRole("checkbox", { name: "消息话题：前端" }));
    await fireEvent.click(screen.getByRole("checkbox", { name: "@ 后端 Worker" }));
    await fireEvent.click(screen.getByRole("checkbox", { name: "@ 测试 Worker" }));
    await fireEvent.update(screen.getByRole("textbox", { name: "消息内容" }), "请一起联调");
    await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    expect(emitted().send).toEqual([
      [
        {
          content: "请一起联调",
          topicIds: ["frontend"],
          mentionedMemberIds: ["backend-worker", "test-worker"],
        },
      ],
    ]);
  });

  it("keeps mentioned members selected when topics change or are cleared", async () => {
    const { emitted } = renderComposer();
    await fireEvent.click(screen.getByRole("checkbox", { name: "消息话题：前端" }));
    await fireEvent.click(screen.getByRole("checkbox", { name: "@ 后端 Worker" }));
    await fireEvent.click(screen.getByRole("button", { name: "清空消息话题" }));
    await fireEvent.update(screen.getByRole("textbox", { name: "消息内容" }), "继续核对接口");
    await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    expect(emitted().send).toEqual([
      [{ content: "继续核对接口", topicIds: [], mentionedMemberIds: ["backend-worker"] }],
    ]);
  });

  it("continues a draft with the remaining topics and members after deletion", async () => {
    const room = roomFixture();
    const { emitted, rerender } = renderComposer({
      content: "继续讨论",
      topicIds: ["frontend", "backend"],
      mentionedMemberIds: ["backend-worker", "test-worker"],
    });
    await rerender({
      topics: room.topics.filter((topic) => topic.id === "frontend"),
      members: room.members.filter((member) => member.id !== "backend-worker"),
    });
    await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
    expect(emitted().send).toEqual([
      [{ content: "继续讨论", topicIds: ["frontend"], mentionedMemberIds: ["test-worker"] }],
    ]);
  });

  it("shows field errors for missing content and targets, clearing only the corrected error", async () => {
    const { emitted } = renderComposer();
    await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    expect(screen.getByText("请选择至少一个话题或 @ 一位成员")).toBeTruthy();
    expect(screen.getByText("请输入消息内容")).toBeTruthy();
    expect(screen.getByRole("group", { name: "消息话题" }).getAttribute("aria-invalid")).toBe(
      "true",
    );
    expect(screen.getByRole("group", { name: "@ 成员" }).getAttribute("aria-invalid")).toBe("true");
    expect(emitted().send).toBeUndefined();

    await fireEvent.click(screen.getByRole("checkbox", { name: "@ 测试 Worker" }));

    expect(screen.queryByText("请选择至少一个话题或 @ 一位成员")).toBeNull();
    expect(screen.getByText("请输入消息内容")).toBeTruthy();
    expect(screen.getByRole("group", { name: "@ 成员" }).getAttribute("aria-invalid")).toBe(
      "false",
    );
  });

  it("rejects an empty topic until a member or another topic is selected", async () => {
    const { emitted } = renderComposer();
    await fireEvent.click(screen.getByRole("checkbox", { name: "消息话题：汇总" }));
    await fireEvent.update(screen.getByRole("textbox", { name: "消息内容" }), "同步约定");
    await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    expect(screen.getByText("所选话题暂无成员，请选择其他话题或 @ 成员")).toBeTruthy();
    expect(emitted().send).toBeUndefined();

    await fireEvent.click(screen.getByRole("checkbox", { name: "@ 后端 Worker" }));
    await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

    expect(screen.queryByText("所选话题暂无成员，请选择其他话题或 @ 成员")).toBeNull();
    expect(emitted().send).toHaveLength(1);
  });

  it.each([{ topicIds: ["backend"] }, { topicIds: [] }])(
    "carries over the original mentions when replying with topics $topicIds",
    async ({ topicIds }) => {
      const room = roomFixture();
      const replyTo = {
        ...room.messages[1],
        topicIds,
        recipientIds: topicIds.length ? room.messages[1].recipientIds : ["test-worker"],
      };
      const draft = {
        content: "已有回复草稿",
        topicIds: ["frontend"],
        mentionedMemberIds: ["frontend-worker"],
      };
      const { emitted, rerender } = renderComposer(draft);
      await rerender({ replyTo });

      expect(
        screen.getByRole("checkbox", { name: "@ 测试 Worker" }).getAttribute("aria-checked"),
      ).toBe("true");
      expect(
        screen.getByRole("checkbox", { name: "@ 后端 Worker" }).getAttribute("aria-checked"),
      ).toBe("false");
      expect(
        screen.getByRole("checkbox", { name: "@ 前端 Worker" }).getAttribute("aria-checked"),
      ).toBe("false");
      await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));

      expect(emitted().send).toEqual([
        [
          {
            content: draft.content,
            topicIds,
            mentionedMemberIds: ["test-worker"],
            replyToMessageId: replyTo.id,
          },
        ],
      ]);
    },
  );

  it("preserves the draft when the parent reports a send failure", async () => {
    const draft = {
      content: "保留这条草稿",
      topicIds: [],
      mentionedMemberIds: ["test-worker"],
    };
    const { rerender } = renderComposer(draft);
    await fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
    await rerender({ error: "发送失败，请重试。请求 ID：req_send" });

    expect(screen.getByRole("alert").textContent).toContain("req_send");
    expect((screen.getByRole("textbox", { name: "消息内容" }) as HTMLTextAreaElement).value).toBe(
      draft.content,
    );
    expect(
      screen.getByRole("checkbox", { name: "@ 测试 Worker" }).getAttribute("aria-checked"),
    ).toBe("true");
    expect(
      screen.getByRole("checkbox", { name: "消息话题：后端" }).getAttribute("aria-checked"),
    ).toBe("false");
  });
});
