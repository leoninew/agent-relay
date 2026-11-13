import { inlineSkills, messageText, referencedCapabilities } from "@/domains/room/inlineSkills";
import type { SkillReference } from "@/services/roomApi";

export type SkillEditorPart = {
  start: number;
  end: number;
  text: string;
  skill?: SkillReference;
};

export const skillClipboardType = "application/x-agent-relay-skills+json";
export const messageMaxLength = 6000;
export function writeSkillClipboard(content: string, skills: readonly SkillReference[]) {
  const references = referencedCapabilities(content, skills);
  return {
    text: messageText(content, references),
    data: JSON.stringify({ version: 1, content, skills: references }),
  };
}

export function readSkillClipboard(
  data: string,
  candidates: readonly SkillReference[],
): { content: string; skills: SkillReference[] } | undefined {
  if (!data || data.length > 100_000) return;
  let payload: { version?: unknown; content?: unknown; skills?: unknown };
  try {
    payload = JSON.parse(data);
  } catch {
    return;
  }
  if (
    !payload ||
    payload.version !== 1 ||
    typeof payload.content !== "string" ||
    payload.content.length > messageMaxLength ||
    !Array.isArray(payload.skills)
  )
    return;
  const available = new Map(candidates.map((skill) => [skill.id, skill]));
  const copied: SkillReference[] = [];
  const resolved: SkillReference[] = [];
  for (const item of payload.skills) {
    if (
      !item ||
      item.type !== "skill" ||
      typeof item.id !== "string" ||
      typeof item.name !== "string" ||
      item.name.length > 1000
    )
      return;
    copied.push({ type: "skill", id: item.id, name: item.name });
    const identity = available.get(item.id);
    if (identity) resolved.push(identity);
  }
  const resolvedIds = new Set(resolved.map((skill) => skill.id));
  // Unknown identities become readable text; a copied name never grants a capability.
  const unresolved = copied.filter((skill) => !resolvedIds.has(skill.id));
  return { content: messageText(payload.content, unresolved), skills: resolved };
}

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
