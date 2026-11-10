import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";

import RoomComposer from "@/domains/room/RoomComposer.vue";
import type { MessageDraft } from "@/services/roomApi";

import { roomFixture } from "../../fixtures/room";

describe("RoomComposer", () => {
  afterEach(cleanup);

  function renderComposer(draft?: MessageDraft) {
    const room = roomFixture();
    return render(RoomComposer, {
      props: {
        roomId: room.room.id,
        topics: room.topics,
        members: room.members,
        sessions: room.sessions,
        draft,
        sending: false,
        error: null,
      },
    });
  }

  it("sends with Enter and prevents inserting a newline", async () => {
    const { emitted } = renderComposer({
      content: " 第一行\n第二行 ",
      topicIds: ["frontend"],
      mentionedMemberIds: [],
    });
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      cancelable: true,
    });

    await fireEvent(screen.getByRole("textbox", { name: "消息内容" }), event);

    expect(event.defaultPrevented).toBe(true);
    expect(emitted().send).toEqual([
      [{ content: "第一行\n第二行", topicIds: ["frontend"], mentionedMemberIds: [] }],
    ]);
  });

  it.each([
    { name: "Shift+Enter", shiftKey: true },
    { name: "IME composition", isComposing: true },
    { name: "IME confirmation", keyCode: 229 },
  ])("keeps $name available for editing without sending", async ({ name, ...modifiers }) => {
    const { emitted } = renderComposer({
      content: "输入中的消息",
      topicIds: ["frontend"],
      mentionedMemberIds: [],
    });
    const input = screen.getByRole("textbox", { name: "消息内容" }) as HTMLTextAreaElement;
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      cancelable: true,
      ...modifiers,
    });

    await fireEvent(input, event);

    expect(event.defaultPrevented, name).toBe(false);
    expect(emitted().send).toBeUndefined();
    expect(input.value).toBe("输入中的消息");
  });

  it.each([{ sending: true }, { locked: true }])(
    "does not send with Enter when unavailable: %j",
    async (state) => {
      const { emitted, rerender } = renderComposer({
        content: "等待发送",
        topicIds: ["frontend"],
        mentionedMemberIds: [],
      });
      await rerender(state);
      await fireEvent.keyDown(screen.getByRole("textbox", { name: "消息内容" }), {
        key: "Enter",
      });

      expect(emitted().send).toBeUndefined();
    },
  );

  it("sends to topics without requiring a member selection", async () => {
    const { emitted } = renderComposer();
    expect(screen.queryByRole("checkbox", { name: "@ 你" })).toBeNull();
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

  it("names the user consistently when quoting their message", () => {
    const room = roomFixture();
    render(RoomComposer, {
      props: {
        roomId: room.room.id,
        topics: room.topics,
        members: room.members,
        sessions: room.sessions,
        replyTo: room.messages[0],
        sending: false,
        error: null,
      },
    });
    expect(screen.getByText("你", { selector: "strong" })).toBeTruthy();
    expect(screen.queryByText("YOU")).toBeNull();
  });

  it("keeps the reply author current and retains their identity after removal", async () => {
    const room = roomFixture();
    const { rerender } = render(RoomComposer, {
      props: {
        roomId: room.room.id,
        topics: room.topics,
        members: room.members,
        sessions: room.sessions,
        replyTo: room.messages[1],
        sending: false,
        error: null,
      },
    });
    await rerender({
      members: room.members.map((member) =>
        member.id === "backend-worker"
          ? { ...member, name: "后端开发", deletedAt: "2026-11-09T00:00:00Z" }
          : member,
      ),
    });

    expect(screen.getByText("后端开发", { selector: "strong" })).toBeTruthy();
    expect(screen.queryByRole("checkbox", { name: "@ 后端开发" })).toBeNull();
    expect(screen.queryByText("后端 Worker")).toBeNull();
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
    "reuses topics and mentions on every quote with topics $topicIds",
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
      const wrapper = mount(RoomComposer, {
        props: {
          roomId: room.room.id,
          topics: room.topics,
          members: room.members,
          sessions: room.sessions,
          replyTo,
          draft,
          sending: false,
          error: null,
        },
      });
      try {
        await wrapper.vm.quote(replyTo);
        await wrapper.get('button[aria-label="清空 @ 成员"]').trigger("click");
        await wrapper.vm.quote(replyTo);
        expect(
          wrapper.get('[role="checkbox"][aria-label="@ 测试 Worker"]').attributes("aria-checked"),
        ).toBe("true");
        expect(
          wrapper.get('[role="checkbox"][aria-label="@ 后端 Worker"]').attributes("aria-checked"),
        ).toBe("false");
        expect(
          wrapper.get('[role="checkbox"][aria-label="@ 前端 Worker"]').attributes("aria-checked"),
        ).toBe("false");
        await wrapper.get("form").trigger("submit");

        expect(wrapper.emitted("send")).toEqual([
          [
            {
              content: draft.content,
              topicIds,
              mentionedMemberIds: ["test-worker"],
              replyToMessageId: replyTo.id,
            },
          ],
        ]);
      } finally {
        wrapper.unmount();
      }
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

  it("adds heading targets once while preserving the existing draft, routing and reply", async () => {
    const room = roomFixture();
    const draft = {
      content: "保留这条草稿",
      topicIds: ["frontend"],
      mentionedMemberIds: ["frontend-worker"],
    };
    const wrapper = mount(RoomComposer, {
      props: {
        roomId: room.room.id,
        topics: room.topics,
        members: room.members,
        sessions: room.sessions,
        replyTo: room.messages[1],
        draft,
        sending: false,
        error: null,
      },
    });
    try {
      wrapper.vm.addTopic("backend");
      wrapper.vm.addTopic("backend");
      wrapper.vm.addMember("backend-worker");
      wrapper.vm.addMember("backend-worker");
      wrapper.vm.addMember("user");
      await wrapper.get("form").trigger("submit");

      expect(wrapper.emitted("send")).toEqual([
        [
          {
            ...draft,
            topicIds: ["frontend", "backend"],
            mentionedMemberIds: ["frontend-worker", "backend-worker"],
            replyToMessageId: room.messages[1].id,
          },
        ],
      ]);
    } finally {
      wrapper.unmount();
    }
  });

  it.each(["topic", "member"] as const)(
    "preserves the other routing category when selecting and clearing a sidebar %s",
    async (category) => {
      const room = roomFixture();
      const draft = {
        content: "保留草稿和引用",
        topicIds: ["frontend"],
        mentionedMemberIds: ["frontend-worker"],
      };
      const wrapper = mount(RoomComposer, {
        props: {
          roomId: room.room.id,
          topics: room.topics,
          members: room.members,
          sessions: room.sessions,
          replyTo: room.messages[1],
          draft,
          sending: false,
          error: null,
        },
      });
      try {
        wrapper.vm.addTopic("backend");
        wrapper.vm.addMember("backend-worker");
        if (category === "topic") wrapper.vm.selectTopic("backend");
        else wrapper.vm.selectMember("backend-worker");
        await wrapper.get("form").trigger("submit");

        const selected = {
          ...draft,
          topicIds: category === "topic" ? ["backend"] : ["frontend", "backend"],
          mentionedMemberIds:
            category === "member" ? ["backend-worker"] : ["frontend-worker", "backend-worker"],
          replyToMessageId: room.messages[1].id,
        };
        expect(wrapper.emitted("send")).toEqual([[selected]]);

        if (category === "topic") wrapper.vm.selectTopic();
        else wrapper.vm.selectMember();
        await wrapper.get("form").trigger("submit");

        expect(wrapper.emitted("send")?.[1]).toEqual([
          {
            ...selected,
            ...(category === "topic" ? { topicIds: [] } : { mentionedMemberIds: [] }),
          },
        ]);
      } finally {
        wrapper.unmount();
      }
    },
  );

  it.each([{ sending: true }, { locked: true }])(
    "preserves locked routing when adding heading targets: %j",
    async (state) => {
      const room = roomFixture();
      const draft = {
        content: "等待发送",
        topicIds: ["frontend"],
        mentionedMemberIds: ["frontend-worker"],
      };
      const wrapper = mount(RoomComposer, {
        props: {
          roomId: room.room.id,
          topics: room.topics,
          members: room.members,
          sessions: room.sessions,
          draft,
          sending: false,
          error: null,
          ...state,
        },
      });
      try {
        wrapper.vm.addTopic("backend");
        wrapper.vm.addMember("backend-worker");
        wrapper.vm.selectTopic("backend");
        wrapper.vm.selectMember("backend-worker");
        await wrapper.setProps({ sending: false, locked: false });
        await wrapper.get("form").trigger("submit");

        expect(wrapper.emitted("send")).toEqual([[draft]]);
      } finally {
        wrapper.unmount();
      }
    },
  );
});
