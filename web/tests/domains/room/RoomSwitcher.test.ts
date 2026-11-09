import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/vue";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RoomSwitcher from "@/domains/room/RoomSwitcher.vue";
import { deleteRoom } from "@/services/roomApi";
import type * as roomApi from "@/services/roomApi";
import { useRoomsStore } from "@/stores/rooms";

import { roomFixture } from "../../fixtures/room";

const navigation = vi.hoisted(() => ({
  params: { roomId: "agent-relay" },
  push: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: navigation.params }),
  useRouter: () => navigation,
}));
vi.mock("@/services/roomApi", async (importOriginal) => ({
  ...(await importOriginal<typeof roomApi>()),
  deleteRoom: vi.fn(),
}));

describe("RoomSwitcher deletion", () => {
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
    render(RoomSwitcher, {
      global: {
        plugins: [pinia],
        stubs: {
          DropdownMenuRoot: { template: "<div><slot /></div>" },
          DropdownMenuTrigger: { template: "<div><slot /></div>" },
          DropdownMenuPortal: { template: "<div><slot /></div>" },
          DropdownMenuContent: { template: "<div><slot /></div>" },
          DropdownMenuItem: {
            emits: ["select"],
            template: "<div @click=\"$emit('select')\"><slot /></div>",
          },
          DropdownMenuSeparator: true,
          RoomSetupDialog: true,
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
    await fireEvent.click(screen.getByRole("button", { name: `删除聊天室：${name}` }));
    await screen.findByRole("heading", { name: "删除聊天室" });
  }

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

  it("keeps the selected room open when deleting another room", async () => {
    renderSwitcher();
    await requestDeletion("其他聊天室");
    await fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
    await waitFor(() => expect(deleteRoom).toHaveBeenCalledWith("other"));
    expect(navigation.replace).not.toHaveBeenCalled();
    expect(navigation.push).not.toHaveBeenCalled();
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
