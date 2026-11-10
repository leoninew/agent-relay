import type { Member, Session } from "@/services/roomApi";

export function memberSessionName(
  member: Pick<Member, "id">,
  members: Member[],
  sessions: Session[],
): string | undefined {
  const sessionId = members.find((candidate) => candidate.id === member.id)?.sessionId;
  return sessions.find((session) => session.id === sessionId)?.name;
}
