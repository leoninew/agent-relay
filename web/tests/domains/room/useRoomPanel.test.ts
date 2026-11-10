import { ref } from "vue";

import { describe, expect, it } from "vitest";

import { useRoomPanel } from "@/domains/room/useRoomPanel";
import type { RoomMessage } from "@/services/roomApi";

import { roomFixture } from "../../fixtures/room";

describe("room panel", () => {
  it("derives the last message from the current results when nothing is selected", () => {
    const messages = ref<RoomMessage[]>([]);
    const panel = useRoomPanel(() => messages.value);
    expect(panel.target.value).toBeUndefined();
    expect(panel.message.value).toBeUndefined();
    expect(panel.drawerOpen.value).toBe(false);
    messages.value = roomFixture().messages;
    expect(panel.message.value?.id).toBe(messages.value.at(-1)?.id);
    messages.value = [messages.value[0]];
    expect(panel.message.value?.id).toBe(messages.value[0].id);
    messages.value = [];
    expect(panel.message.value).toBeUndefined();
  });

  it("opens the drawer without changing selection and clears selection on close or room reset", () => {
    const messages = roomFixture().messages;
    const panel = useRoomPanel(() => messages);
    panel.selectSidebar("member", "test-worker");
    panel.drawerOpen.value = false;
    panel.openDrawer();
    expect(panel.drawerOpen.value).toBe(true);
    expect(panel.target.value).toEqual({ kind: "member", id: "test-worker" });
    panel.closeDetails();
    panel.openDrawer();
    expect(panel.target.value).toBeUndefined();
    expect(panel.message.value?.id).toBe(messages.at(-1)?.id);
    expect(panel.drawerOpen.value).toBe(true);
    panel.selectSidebar("topic", "frontend");
    panel.reset();
    expect(panel.target.value).toBeUndefined();
    expect(panel.selectedTopicId.value).toBeUndefined();
    expect(panel.selectedMemberId.value).toBeUndefined();
    expect(panel.drawerOpen.value).toBe(false);
    expect(panel.message.value?.id).toBe(messages.at(-1)?.id);
  });

  it("uses one sidebar transition for combined filters, repeated selections and both all entries", () => {
    const messages = roomFixture().messages;
    const panel = useRoomPanel(() => messages);
    expect(panel.selectSidebar("topic", "frontend")).toBe(true);
    expect(panel.selectSidebar("topic", "frontend")).toBe(false);
    expect(panel.selectedTopicId.value).toBe("frontend");
    expect(panel.target.value).toEqual({ kind: "topic", id: "frontend" });
    expect(panel.queueScope.value).toEqual({ topicId: "frontend" });
    expect(panel.message.value).toBeUndefined();
    expect(panel.selectSidebar("member", "test-worker")).toBe(true);
    expect(panel.target.value).toEqual({ kind: "member", id: "test-worker" });
    expect(panel.queueScope.value).toEqual({ memberId: "test-worker" });
    panel.showMessage(messages[0]);
    expect(panel.queueScope.value).toEqual({});
    expect(panel.selectSidebar("member", "test-worker")).toBe(false);
    expect(panel.queueScope.value).toEqual({ memberId: "test-worker" });
    expect(panel.selectSidebar("topic", undefined)).toBe(true);
    expect(panel.selectedMemberId.value).toBe("test-worker");
    expect(panel.target.value).toEqual({ kind: "member", id: "test-worker" });
    expect(panel.selectSidebar("member", undefined)).toBe(true);
    expect(panel.target.value).toBeUndefined();
    expect(panel.queueScope.value).toEqual({});
    expect(panel.message.value?.id).toBe(messages.at(-1)?.id);
    panel.showMessage(messages[0]);
    expect(panel.selectSidebar("topic", undefined)).toBe(false);
    expect(panel.message.value?.id).toBe(messages.at(-1)?.id);
    panel.closeDetails();
    expect(panel.selectSidebar("member", undefined)).toBe(false);
    expect(panel.message.value?.id).toBe(messages.at(-1)?.id);
    expect(panel.drawerOpen.value).toBe(true);
  });

  it("keeps explicit selection across result changes and updates only matching receipts", () => {
    const [selected, newer] = roomFixture().messages;
    const messages = ref([selected]);
    const panel = useRoomPanel(() => messages.value);
    panel.showMessage(selected);
    messages.value = [newer];
    panel.syncMessages([newer]);
    expect(panel.message.value?.id).toBe(selected.id);
    const completed = {
      ...selected,
      deliveries: selected.deliveries.map((delivery) => ({
        ...delivery,
        status: "received" as const,
      })),
    };
    panel.syncMessages([completed, newer]);
    expect(panel.message.value).toEqual(completed);
    messages.value = [];
    expect(panel.message.value?.id).toBe(selected.id);
    panel.closeDetails();
    panel.syncMessages([newer]);
    expect(panel.target.value).toBeUndefined();
    expect(panel.message.value).toBeUndefined();
    messages.value = [newer];
    expect(panel.message.value?.id).toBe(newer.id);
  });
});
