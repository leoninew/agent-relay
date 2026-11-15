import { computed, ref } from "vue";

import { describeApiError } from "@/services/api";
import { interruptRoomMember } from "@/services/roomApi";
import type { Member } from "@/services/roomApi";
import { useToastsStore } from "@/stores/toasts";

export function useMemberInterrupt(
  roomId: () => string | undefined,
  channelId: () => string | undefined,
  refresh: (roomId: string, channelId: string) => Promise<void>,
) {
  const toasts = useToastsStore();
  const pending = ref(new Map<string, { memberId: string; scope: string }>());
  const scope = () => JSON.stringify([roomId(), channelId()]);
  const interruptingMemberIds = computed(() =>
    [...pending.value.values()]
      .filter((request) => request.scope === scope())
      .map((request) => request.memberId),
  );

  async function interruptMember(member: Member): Promise<void> {
    const currentRoom = roomId();
    const currentChannel = channelId();
    if (
      !currentRoom ||
      !currentChannel ||
      member.kind !== "agent" ||
      member.presence !== "busy" ||
      member.deletedAt ||
      !member.sessionId
    )
      return;
    const key = JSON.stringify([currentRoom, currentChannel, member.id]);
    if (pending.value.has(key)) return;
    const currentScope = scope();
    pending.value.set(key, { memberId: member.id, scope: currentScope });
    try {
      const result = await interruptRoomMember(currentRoom, member.id, currentChannel);
      if (scope() !== currentScope) return;
      const message = {
        key: {
          interrupted: "notice.memberInterrupted",
          not_running: "notice.memberNotRunning",
        }[result.status],
        params: { name: member.name },
      };
      if (result.status === "interrupted") toasts.success(message);
      else toasts.info(message);
    } catch (caught) {
      if (scope() !== currentScope) return;
      toasts.error(describeApiError(caught, "errors.memberInterrupt"));
    } finally {
      try {
        if (scope() === currentScope) await refresh(currentRoom, currentChannel);
      } catch (caught) {
        if (scope() === currentScope)
          toasts.error(describeApiError(caught, "errors.sessionRefresh"));
      } finally {
        pending.value.delete(key);
      }
    }
  }

  return { interruptingMemberIds, interruptMember };
}
