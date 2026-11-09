import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/vue";
import { createPinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RoomSetupDialog from "@/domains/room/RoomSetupDialog.vue";
import type { SessionCandidate } from "@/services/roomApi";

import { roomFixture } from "../../fixtures/room";

const { createTopic } = vi.hoisted(() => ({ createTopic: vi.fn() }));

vi.mock("@/stores/rooms", () => ({ useRoomsStore: () => ({ createTopic }) }));

const availableSession: SessionCandidate = {
  id: "session-1",
  name: "已有会话",
  provider: "codex",
  projectPath: roomFixture().room.projectPath,
  presence: "busy",
  observedAt: "2026-11-07T03:04:05Z",
  archived: false,
  memberId: null,
  usable: true,
  unavailableReason: null,
};

describe("RoomSetupDialog form", () => {
  beforeEach(() => vi.resetAllMocks());
  afterEach(cleanup);

  function renderForm(sessions?: SessionCandidate[]) {
    const room = roomFixture();
    return render(RoomSetupDialog, {
      props: {
        mode: undefined,
        topics: room.topics,
        roomId: room.room.id,
        sessions: sessions ?? [
          availableSession,
          {
            id: "joined",
            name: "已加入会话",
            provider: "codex",
            projectPath: room.room.projectPath,
            presence: "offline",
            observedAt: "2026-11-07T03:04:05Z",
            archived: true,
            memberId: "member-1",
            usable: false,
            unavailableReason: "会话已归档",
          },
          {
            id: "not-connected",
            name: "未接入的会话",
            provider: "codex",
            projectPath: room.room.projectPath,
            presence: "unknown",
            observedAt: "2026-11-07T03:04:05Z",
            archived: false,
            memberId: null,
            usable: false,
            unavailableReason: "请使用共享 daemon 打开此会话后刷新",
          },
        ],
        saving: false,
        error: null,
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

  it("emits a new member with a selected session and an inline topic", async () => {
    const topic = {
      id: "review",
      name: "代码审查",
      description: "",
      messageCount: 0,
      createdAt: "2026-11-06T10:00:00Z",
      deletedAt: null,
    };
    createTopic.mockResolvedValue(topic);
    const { rerender, emitted } = renderForm();
    await rerender({ mode: "member" });
    expect(screen.getAllByRole("radio")).toHaveLength(1);
    await fireEvent.click(screen.getByRole("radio", { name: /^已有会话/ }));
    await fireEvent.update(screen.getByLabelText(/成员名称/), "审查 Worker");
    await fireEvent.update(screen.getByLabelText("新话题名称"), "代码审查");
    await fireEvent.click(screen.getByRole("button", { name: "添加话题" }));
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
          sessionId: "session-1",
          name: "审查 Worker",
          topicIds: ["review"],
        },
      ],
    ]);
  });

  it("folds unavailable sessions and preserves selection when inspecting their reasons", async () => {
    const { rerender } = renderForm();
    await rerender({ mode: "member" });
    const toggle = screen.getByRole("button", { name: /不可用会话.*2/ });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("已加入会话")).toBeNull();
    expect(screen.queryByText("未接入的会话")).toBeNull();

    const choice = screen.getByRole("radio", { name: /^已有会话/ });
    await fireEvent.click(choice);
    await fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(await screen.findByRole("list", { name: "不可用会话" })).toBeTruthy();
    expect(screen.getByText("已加入会话")).toBeTruthy();
    expect(screen.getByText("未接入的会话")).toBeTruthy();
    expect(screen.getByText("请使用共享 daemon 打开此会话后刷新")).toBeTruthy();
    expect(screen.getAllByRole("radio")).toHaveLength(1);
    expect(choice.getAttribute("aria-checked")).toBe("true");

    await fireEvent.click(toggle);
    await waitFor(() => expect(screen.queryByText("未接入的会话")).toBeNull());
    expect(choice.getAttribute("aria-checked")).toBe("true");
    await fireEvent.click(toggle);
    await rerender({ mode: undefined });
    await rerender({ mode: "member" });
    expect(screen.getByRole("button", { name: /不可用会话/ }).getAttribute("aria-expanded")).toBe(
      "false",
    );
  });

  it("explains when every candidate is unavailable, including a usable but joined session", async () => {
    const { rerender, emitted } = renderForm([
      { ...availableSession, id: "joined", name: "已加入会话", memberId: "member-1" },
      {
        ...availableSession,
        id: "archived",
        name: "历史会话",
        archived: true,
        usable: false,
        unavailableReason: "会话已归档",
      },
    ]);
    await rerender({ mode: "member" });
    expect(screen.getByText("暂无可加入的会话")).toBeTruthy();
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(screen.queryByText("已加入会话")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: /不可用会话/ }));
    expect(await screen.findByText("已加入")).toBeTruthy();
    expect(screen.getByText("此会话已加入当前聊天室。")).toBeTruthy();
    expect(screen.getByText("已归档")).toBeTruthy();
    expect(screen.getByText("会话已归档")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "添加成员" }));
    expect(screen.getByText("请选择要加入的会话")).toBeTruthy();
    expect(emitted().createMember).toBeUndefined();
  });

  it("clears a selection that becomes unavailable after refreshing", async () => {
    const { rerender, emitted } = renderForm([availableSession]);
    await rerender({ mode: "member" });
    expect(screen.queryByRole("button", { name: /不可用会话/ })).toBeNull();
    await fireEvent.click(screen.getByRole("radio", { name: /^已有会话/ }));
    await rerender({
      sessions: [{ ...availableSession, usable: false, unavailableReason: "会话接入未确认" }],
    });
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect((screen.getByLabelText(/成员名称/) as HTMLInputElement).value).toBe("");
    expect(screen.queryByText("会话接入未确认")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "添加成员" }));
    expect(screen.getByText("请选择要加入的会话")).toBeTruthy();
    expect(emitted().createMember).toBeUndefined();
  });

  it("requires a selected session and clears only its field error after selection", async () => {
    const { rerender, emitted } = renderForm();
    await rerender({ mode: "member" });
    await fireEvent.click(screen.getByRole("button", { name: "添加成员" }));
    expect(screen.getByRole("radiogroup").getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText("请选择要加入的会话")).toBeTruthy();
    expect(emitted().createMember).toBeUndefined();
    await fireEvent.click(screen.getByRole("radio", { name: /^已有会话/ }));
    expect(screen.queryByText("请选择要加入的会话")).toBeNull();
    await fireEvent.click(screen.getByRole("checkbox", { name: "# 前端" }));
    await fireEvent.submit(screen.getByRole("button", { name: "添加成员" }).closest("form")!);
    expect(emitted().createMember).toEqual([
      [
        {
          sessionId: "session-1",
          name: "已有会话",
          topicIds: ["frontend"],
        },
      ],
    ]);
  });

  it("adds a member without subscriptions when the room has no topics", async () => {
    const { rerender, emitted } = renderForm();
    await rerender({ mode: "member", topics: [] });
    await fireEvent.click(screen.getByRole("radio", { name: /^已有会话/ }));
    await fireEvent.click(screen.getByRole("button", { name: "添加成员" }));

    expect(emitted().createMember).toEqual([
      [{ sessionId: "session-1", name: "已有会话", topicIds: [] }],
    ]);
  });

  it("distinguishes empty sessions from loading and request failure and can refresh", async () => {
    const { rerender, emitted } = renderForm();
    await rerender({ mode: "member", sessions: [], sessionsLoading: true });
    expect(screen.getByRole("status").textContent).toContain("正在加载会话");
    await rerender({ sessionsLoading: false });
    expect(screen.getByText("当前项目目录下暂无 Codex 会话")).toBeTruthy();
    await rerender({ sessionsError: "会话服务不可用" });
    expect(screen.getByRole("alert").textContent).toBe("会话服务不可用");
    expect(screen.queryByText("当前项目目录下暂无 Codex 会话")).toBeNull();
    expect(screen.getByRole("button", { name: "添加成员" }).hasAttribute("disabled")).toBe(true);
    await fireEvent.click(screen.getByRole("button", { name: "刷新会话" }));
    expect(emitted().reloadSessions).toEqual([[]]);
  });

  it("prefills and saves the topic name and description", async () => {
    const topic = roomFixture().topics[1];
    const { rerender, emitted } = renderForm();
    await rerender({ mode: "topic", topic });
    expect((screen.getByLabelText(/话题名称/) as HTMLInputElement).value).toBe(topic.name);
    expect((screen.getByLabelText("话题说明") as HTMLInputElement).value).toBe(topic.description);
    await fireEvent.update(screen.getByLabelText(/话题名称/), "界面讨论");
    await fireEvent.update(screen.getByLabelText("话题说明"), "交互和界面实现");
    await fireEvent.click(screen.getByRole("button", { name: "保存话题" }));
    expect(emitted().updateTopic).toEqual([
      [topic.id, { name: "界面讨论", description: "交互和界面实现" }],
    ]);
  });
});
