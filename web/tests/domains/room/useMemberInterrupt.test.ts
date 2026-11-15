import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

import { useMemberInterrupt } from "@/domains/room/useMemberInterrupt";
import { ApiClientError } from "@/services/api";
import { interruptRoomMember } from "@/services/roomApi";
import type { MemberInterruptResult } from "@/services/roomApi";
import { useToastsStore } from "@/stores/toasts";

import { roomFixture } from "../../fixtures/room";

vi.mock("@/services/roomApi", () => ({ interruptRoomMember: vi.fn() }));

function harness() {
  const room = ref<string | undefined>("room");
  const channel = ref("channel");
  const refresh = vi.fn().mockResolvedValue(undefined);
  const interrupt = useMemberInterrupt(
    () => room.value,
    () => channel.value,
    refresh,
  );
  return { room, channel, refresh, ...interrupt, toasts: useToastsStore() };
}

describe("member interruption", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(interruptRoomMember)
      .mockReset()
      .mockResolvedValue({ status: "interrupted", turnId: "turn" });
  });

  it.each([
    ["interrupted", "notice.memberInterrupted", "success"],
    ["not_running", "notice.memberNotRunning", "info"],
  ] as const)(
    "reports the synchronous %s result and refreshes status",
    async (status, key, tone) => {
      vi.mocked(interruptRoomMember).mockResolvedValueOnce({ status, turnId: "turn" });
      const state = harness();
      await state.interruptMember(roomFixture().members[0]);
      expect(interruptRoomMember).toHaveBeenCalledWith("room", "frontend-worker", "channel");
      expect(state.toasts.items[0]).toMatchObject({ message: { key }, tone });
      expect(state.refresh).toHaveBeenCalledWith("room", "channel");
      expect(state.interruptingMemberIds.value).toEqual([]);
    },
  );

  it("blocks repeated submissions for the same member while awaiting the response", async () => {
    let complete!: (result: MemberInterruptResult) => void;
    vi.mocked(interruptRoomMember).mockReturnValueOnce(
      new Promise((resolve) => {
        complete = resolve;
      }),
    );
    const state = harness();
    const member = roomFixture().members[0];
    const request = state.interruptMember(member);
    await state.interruptMember(member);
    expect(interruptRoomMember).toHaveBeenCalledTimes(1);
    expect(state.interruptingMemberIds.value).toEqual([member.id]);
    complete({ status: "interrupted", turnId: "turn" });
    await request;
    expect(state.interruptingMemberIds.value).toEqual([]);
  });

  it("does not display the old channel's result or refresh the new channel", async () => {
    let complete!: (result: MemberInterruptResult) => void;
    vi.mocked(interruptRoomMember).mockReturnValueOnce(
      new Promise((resolve) => {
        complete = resolve;
      }),
    );
    const state = harness();
    const request = state.interruptMember(roomFixture().members[0]);
    state.channel.value = "other";
    expect(state.interruptingMemberIds.value).toEqual([]);
    complete({ status: "interrupted", turnId: "turn" });
    await request;
    expect(state.toasts.items).toEqual([]);
    expect(state.refresh).not.toHaveBeenCalled();
  });

  it("does not retry unknown results and preserves the diagnostic request ID", async () => {
    vi.mocked(interruptRoomMember).mockRejectedValueOnce(
      new ApiClientError("safe", "http_error", {
        code: "session_interrupt_unknown",
        requestId: "req-interrupt",
        status: 503,
      }),
    );
    const state = harness();
    await state.interruptMember(roomFixture().members[0]);
    expect(interruptRoomMember).toHaveBeenCalledTimes(1);
    expect(state.toasts.items[0]).toMatchObject({
      tone: "error",
      message: {
        key: "errors.session_interrupt_unknown",
        requestId: "req-interrupt",
      },
    });
    expect(state.refresh).toHaveBeenCalledTimes(1);
  });

  it("keeps a successful interruption separate from a refresh failure", async () => {
    const state = harness();
    state.refresh.mockRejectedValueOnce(new Error("offline"));
    await state.interruptMember(roomFixture().members[0]);
    expect(state.toasts.items.map((toast) => toast.message.key)).toEqual([
      "notice.memberInterrupted",
      "errors.sessionRefresh",
    ]);
  });

  it("ignores idle and human members", async () => {
    const state = harness();
    await state.interruptMember(roomFixture().members[1]);
    await state.interruptMember({ ...roomFixture().members[0], kind: "human" });
    expect(interruptRoomMember).not.toHaveBeenCalled();
  });
});
