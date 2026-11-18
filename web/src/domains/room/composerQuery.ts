import { isInlineTriggerPrefix, isSourcePosition, skillQueryAt } from "@/domains/room/inlineSkills";

export type ComposerQuery = { kind: "skill" | "member"; text: string };

export function composerQueryAt(
  content: string,
  position: number,
): (ComposerQuery & { start: number; end: number }) | undefined {
  const skill = skillQueryAt(content, position);
  if (skill) {
    return { kind: "skill", ...skill };
  }

  const match = /@([\p{L}\p{M}\p{N}_-]*)$/u.exec(content.slice(0, position));
  if (!match || !isInlineTriggerPrefix(content, match.index)) {
    return undefined;
  }
  if (!isSourcePosition(content, match.index)) {
    return undefined;
  }
  const suffix = /^[\p{L}\p{M}\p{N}_-]*/u.exec(content.slice(position))?.[0] ?? "";
  return { kind: "member", text: match[1], start: match.index, end: position + suffix.length };
}
