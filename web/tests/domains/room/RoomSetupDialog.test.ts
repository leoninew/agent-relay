import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/vue";
import { createPinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RoomSetupDialog from "@/domains/room/RoomSetupDialog.vue";

import { roomFixture } from "../../fixtures/room";

const { createTopic } = vi.hoisted(() => ({ createTopic: vi.fn() }));

vi.mock("@/stores/rooms", () => ({ useRoomsStore: () => ({ createTopic }) }));

describe("RoomSetupDialog form", () => {
  beforeEach(() => vi.resetAllMocks());
  afterEach(cleanup);

  function renderForm() {
    const room = roomFixture();
    return render(RoomSetupDialog, {
      props: {
        mode: undefined,
        topics: room.topics,
        roomId: room.room.id,
        roles: ["前端开发", "集成测试"],
        saving: false,
        error: null,
        sessions: [
          {
            id: "session-review",
            name: "审查会话",
            provider: "Codex",
            projectPath: room.room.projectPath,
            presence: "available",
          },
        ],
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          AppDialog: {
            props: ["open", "title", "busy"],
            template: '<section v-if="open"><h2>{{ title }}</h2><slot /></section>',
          },
        },
      },
    });
  }

  it("emits a new member with a custom role and an inline topic", async () => {
    const topic = { id: "review", name: "代码审查", description: "", messageCount: 0 };
    createTopic.mockResolvedValue(topic);
    const { rerender, emitted } = renderForm();
    await rerender({ mode: "member" });
    await fireEvent.click(screen.getByRole("radio", { name: /审查会话/ }));
    await fireEvent.update(screen.getByLabelText(/成员名称/), "审查 Worker");
    await fireEvent.update(screen.getByLabelText(/^角色/), "代码审查");
    await fireEvent.update(screen.getByLabelText("新主题名称"), "代码审查");
    await fireEvent.click(screen.getByRole("button", { name: "添加主题" }));
    await waitFor(() =>
      expect(createTopic).toHaveBeenCalledWith("agent-relay", {
        name: "代码审查",
        description: "",
      }),
    );
    await rerender({ topics: [...roomFixture().topics, topic] });
    await fireEvent.click(screen.getByRole("button", { name: "添加成员" }));

    expect(emitted().createMember).toEqual([
      [
        {
          sessionId: "session-review",
          name: "审查 Worker",
          role: "代码审查",
          topicIds: ["review"],
        },
      ],
    ]);
  });

  it("emits an edited member using an existing role and multiple subscriptions", async () => {
    const member = roomFixture().members[0];
    const { rerender, emitted } = renderForm();
    await rerender({ mode: "member", member });
    await fireEvent.click(screen.getByRole("button", { name: "集成测试" }));
    await fireEvent.click(screen.getByRole("checkbox", { name: "# 后端" }));
    await fireEvent.click(screen.getByRole("button", { name: "保存成员" }));

    expect(emitted().updateMember).toEqual([
      [member.id, { name: member.name, role: "集成测试", topicIds: ["frontend", "backend"] }],
    ]);
  });
});
