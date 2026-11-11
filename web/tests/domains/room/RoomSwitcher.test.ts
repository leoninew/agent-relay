/* eslint-disable vue/one-component-per-file */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/vue";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RoomSwitcher from "@/domains/room/RoomSwitcher.vue";
import { deleteRoom, updateRoom } from "@/services/roomApi";
import type * as roomApi from "@/services/roomApi";
import { useRoomsStore } from "@/stores/rooms";
import type * as rekaUi from "reka-ui";

import { roomFixture } from "../../fixtures/room";

const navigation = vi.hoisted(() => ({
  params: { roomId: "agent-relay" },
  push: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: navigation.params }),
  useRouter: () => navigation,
  RouterLink: {
    props: ["to"],
    template: '<a href="#"><slot /></a>',
  },
}));
vi.mock("@/services/roomApi", async (importOriginal) => ({
  ...(await importOriginal<typeof roomApi>()),
  deleteRoom: vi.fn(),
  updateRoom: vi.fn(),
}));
vi.mock("reka-ui", async (importOriginal) => {
  const actual = await importOriginal<typeof rekaUi>();
  const { defineComponent, h, inject, provide, ref } = await import("vue");
  const menuKey = Symbol("dropdown-menu");
  const DropdownMenuRoot = defineComponent({
    setup(_, { slots }) {
      provide(menuKey, ref(false));
      return () => h("div", slots.default?.());
    },
  });
  const DropdownMenuTrigger = defineComponent({
    setup(_, { slots }) {
      const open = inject<{ value: boolean }>(menuKey);
      return () =>
        h("div", { onClick: () => open && (open.value = !open.value) }, slots.default?.());
    },
  });
  const DropdownMenuPortal = defineComponent({
    setup(_, { slots }) {
      return () => h("div", slots.default?.());
    },
  });
  const DropdownMenuContent = defineComponent({
    setup(_, { slots }) {
      const open = inject<{ value: boolean }>(menuKey);
      return () => (open?.value ? h("div", { role: "menu" }, slots.default?.()) : null);
    },
  });
  const DropdownMenuItem = defineComponent({
    emits: ["select"],
    setup(_, { emit, slots }) {
      const open = inject<{ value: boolean }>(menuKey);
      return () =>
        h(
          "div",
          {
            role: "menuitem",
            onClick: () => {
              emit("select");
              if (open) open.value = false;
            },
          },
          slots.default?.(),
        );
    },
  });
  return {
    ...actual,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuPortal,
    DropdownMenuRoot,
    DropdownMenuTrigger,
  };
});

describe("RoomSwitcher", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    navigation.params.roomId = "agent-relay";
    vi.mocked(deleteRoom).mockResolvedValue();
  });
  afterEach(cleanup);

  function renderSwitcher(withOtherRoom = true) {
    const pinia = createPinia();
    setActivePinia(pinia);
    const rooms = useRoomsStore();
    const room = roomFixture().room;
    rooms.rooms = withOtherRoom ? [room, { ...room, id: "other", name: "其他聊天室" }] : [room];
    rooms.loaded = true;
    vi.mocked(updateRoom).mockImplementation(async (roomId, request) => ({
      ...room,
      id: roomId,
      name: request.name,
    }));
    render(RoomSwitcher, {
      global: {
        plugins: [pinia],
        stubs: {
          RoomSetupDialog: {
            props: ["mode", "room", "error", "saving"],
            emits: ["close", "createRoom", "updateRoom"],
            template: `
              <section v-if="mode" data-testid="room-setup">
                <h2>{{ room ? "编辑聊天室" : "新建聊天室" }}</h2>
                <p>{{ room?.name }}</p>
                <p v-if="error" role="alert">{{ error }}</p>
                <button v-if="room" @click="$emit('updateRoom', { name: 'Renamed' })">
                  保存名称
                </button>
                <button @click="$emit('close')">取消</button>
              </section>
            `,
          },
          AppDialog: {
            props: ["open", "title", "busy"],
            template: '<section v-if="open"><h2>{{ title }}</h2><slot /></section>',
          },
        },
      },
    });
    return rooms;
  }

  async function requestDeletion(name = "Agent Relay 开发室") {
    await fireEvent.click(screen.getByRole("button", { name: `管理项目：${name}` }));
    await fireEvent.click(await screen.findByRole("menuitem", { name: "删除" }));
    await screen.findByRole("heading", { name: "删除聊天室" });
  }

  it("renders projects as links without paths and marks the selected one", () => {
    renderSwitcher();

    const current = screen.getByRole("link", { name: "切换项目：Agent Relay 开发室" });
    expect(current.getAttribute("aria-current")).toBe("page");
    expect(
      screen.getByRole("link", { name: "切换项目：其他聊天室" }).getAttribute("aria-current"),
    ).toBeNull();
    expect(screen.queryByText("D:/work/agent-relay")).toBeNull();
    const create = screen.getByRole("button", { name: "新建聊天室" });
    const lastProject = screen.getByRole("button", { name: "管理项目：其他聊天室" }).closest("li")!;
    expect(lastProject.nextElementSibling?.contains(create)).toBe(true);
    expect(screen.getByRole("button", { name: "管理项目：Agent Relay 开发室" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "管理项目：其他聊天室" })).toBeTruthy();
  });

  it("keeps the create action available when no projects exist", () => {
    const rooms = renderSwitcher(false);
    rooms.rooms = [];

    expect(screen.getByRole("button", { name: "新建聊天室" })).toBeTruthy();
  });

  it("opens a per-project menu with edit and delete actions", async () => {
    renderSwitcher();

    await fireEvent.click(screen.getByRole("button", { name: "管理项目：其他聊天室" }));

    expect(await screen.findByRole("menuitem", { name: "编辑名称" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "删除" })).toBeTruthy();
  });

  it("edits only the room name from the project menu", async () => {
    const rooms = renderSwitcher();

    await fireEvent.click(screen.getByRole("button", { name: "管理项目：其他聊天室" }));
    await fireEvent.click(await screen.findByRole("menuitem", { name: "编辑名称" }));

    expect(await screen.findByRole("heading", { name: "编辑聊天室" })).toBeTruthy();
    expect(screen.getByTestId("room-setup").textContent).toContain("其他聊天室");
    expect(screen.queryByLabelText(/项目路径/)).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "保存名称" }));

    await waitFor(() =>
      expect(updateRoom).toHaveBeenCalledWith("other", {
        name: "Renamed",
      }),
    );
    expect(rooms.rooms[1].name).toBe("Renamed");
    expect(rooms.rooms[1].projectPath).toBe(roomFixture().room.projectPath);
    await waitFor(() => expect(screen.queryByRole("heading", { name: "编辑聊天室" })).toBeNull());
  });

  it("requires confirmation, supports cancellation and switches away after deletion", async () => {
    const rooms = renderSwitcher();
    await requestDeletion();
    expect(screen.getByText(/永久移除此聊天室/)).toBeTruthy();
    expect(deleteRoom).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.queryByRole("button", { name: "确认删除" })).toBeNull();
    expect(rooms.rooms).toHaveLength(2);

    await requestDeletion();
    await fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
    await waitFor(() =>
      expect(navigation.replace).toHaveBeenCalledWith({
        name: "room-detail",
        params: { roomId: "other" },
      }),
    );
    expect(deleteRoom).toHaveBeenCalledTimes(1);
    expect(deleteRoom).toHaveBeenCalledWith("agent-relay");
    expect(rooms.rooms.map((room) => room.id)).toEqual(["other"]);
  });

  it("returns to the empty home after deleting the last room", async () => {
    renderSwitcher(false);
    await requestDeletion();
    await fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith({ name: "room" }));
  });

  it("keeps the dialog and room when deletion fails and allows retrying", async () => {
    const rooms = renderSwitcher();
    vi.mocked(deleteRoom).mockRejectedValueOnce(new Error("unavailable"));
    await requestDeletion();
    await fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
    expect((await screen.findByRole("alert")).textContent).toContain("删除失败，请重试。");
    expect(rooms.rooms).toHaveLength(2);
    expect(navigation.replace).not.toHaveBeenCalled();

    await fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
    await waitFor(() => expect(rooms.rooms).toHaveLength(1));
    expect(screen.queryByRole("button", { name: "确认删除" })).toBeNull();
  });
});
