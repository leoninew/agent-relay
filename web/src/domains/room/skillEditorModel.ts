import { inlineSkills } from "@/domains/room/inlineSkills";
import type { SkillReference } from "@/services/roomApi";

export type SkillEditorPart = {
  start: number;
  end: number;
  text: string;
  skill?: SkillReference;
};

export const messageMaxLength = 6000;

export function skillEditorParts(
  content: string,
  skills: readonly SkillReference[],
): SkillEditorPart[] {
  const identities = new Map(skills.map((skill) => [skill.id, skill]));
  const parts: SkillEditorPart[] = [];
  let start = 0;
  for (const reference of inlineSkills(content)) {
    const skill = identities.get(reference.id);
    if (!skill) continue;
    if (reference.start > start)
      parts.push({ start, end: reference.start, text: content.slice(start, reference.start) });
    parts.push({
      start: reference.start,
      end: reference.end,
      text: content.slice(reference.start, reference.end),
      skill,
    });
    start = reference.end;
  }
  if (start < content.length)
    parts.push({ start, end: content.length, text: content.slice(start) });
  return parts;
}
