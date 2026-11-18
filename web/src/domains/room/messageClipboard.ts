import type { Fragment } from "@tiptap/pm/model";
import {
  memberMentionNodeName,
  type MemberMentionRange,
} from "@/domains/room/composerMemberMention";
import { skillAt } from "@/domains/room/inlineSkills";
import { nodeSource } from "@/domains/room/messageEditorCodec";
import { messageMaxLength } from "@/domains/room/skillEditorModel";
import type { Member, SkillReference } from "@/services/roomApi";

type ClipboardPart =
  string | { type: "member"; id: string; name: string } | (SkillReference & { marker: string });
export const messageClipboardType = "application/x-conflua-message+json";

function readable(part: ClipboardPart): string {
  return typeof part === "string" ? part : `${part.type === "skill" ? "$" : "@"}${part.name}`;
}

export function writeMessageClipboard(fragment: Fragment) {
  const parts: ClipboardPart[] = [];
  fragment.descendants((node) => {
    if (!node.isInline) return;
    const { id, label: name, marker } = node.attrs;
    if (node.type.name === memberMentionNodeName) parts.push({ type: "member", id, name });
    else if (node.type.name === "mention") parts.push({ type: "skill", id, name, marker });
    else parts.push(nodeSource(node));
    return false;
  });
  return { text: parts.map(readable).join(""), data: JSON.stringify({ version: 1, parts }) };
}

export function readMessageClipboard(
  data: string,
  skills: readonly SkillReference[],
  members: readonly Pick<Member, "id" | "name">[],
) {
  if (!data || data.length > 100_000) return;
  let payload;
  try {
    payload = JSON.parse(data);
  } catch {
    return;
  }
  if (payload?.version !== 1 || !Array.isArray(payload.parts)) return;
  const availableSkills = new Map(skills.map((skill) => [skill.id, skill]));
  const availableMembers = new Map(members.map((member) => [member.id, member]));
  const resolved = new Map<string, SkillReference>();
  const memberMentions: MemberMentionRange[] = [];
  let content = "";
  for (const part of payload.parts) {
    if (typeof part === "string") content += part;
    else {
      if (!part || typeof part.id !== "string" || typeof part.name !== "string") return;
      if (part.type === "member") {
        const member = availableMembers.get(part.id);
        const start = content.length;
        content += `@${member?.name ?? part.name}`;
        if (member)
          memberMentions.push({ id: member.id, name: member.name, start, end: content.length });
      } else if (part.type === "skill" && typeof part.marker === "string") {
        const marker = skillAt(part.marker, 0);
        if (!marker || marker.id !== part.id || marker.end !== part.marker.length) return;
        const skill = availableSkills.get(part.id);
        content += skill ? part.marker : `$${part.name}`;
        if (skill) resolved.set(skill.id, skill);
      } else return;
    }
    if (content.length > messageMaxLength) return;
  }
  return { content, skills: [...resolved.values()], memberMentions };
}
