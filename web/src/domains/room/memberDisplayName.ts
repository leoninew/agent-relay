import type { Member } from "@/services/roomApi";

export function memberDisplayName(
  member: (Pick<Member, "name"> & Partial<Pick<Member, "kind">>) | undefined,
  fallback: string,
  humanLabel: string,
): string {
  return member?.kind === "human" ? humanLabel : (member?.name ?? fallback);
}
