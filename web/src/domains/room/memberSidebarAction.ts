import type { Member } from "@/services/roomApi";

export type MemberSidebarAction = "interrupt" | "delete" | undefined;

export function memberSidebarAction(member: Member): MemberSidebarAction {
  if (member.kind !== "agent" || member.deletedAt) {
    return undefined;
  }
  if (member.presence === "busy" && member.sessionId) {
    return "interrupt";
  }
  if (member.presence === "offline" || member.presence === "unknown" || !member.sessionId) {
    return "delete";
  }
  return undefined;
}
