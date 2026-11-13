import type { CapabilityReference, SkillReference } from "@/services/roomApi";

export type InlineSkill = { start: number; end: number; id: string };
export type SkillQuery = { start: number; end: number; text: string };

export function isSkillTriggerPrefix(content: string, start: number): boolean {
  return start === 0 || /[\s\p{P}\p{S}]$/u.test(content.slice(0, start));
}

export function skillQueryAt(content: string, position: number): SkillQuery | undefined {
  const prefix = content.slice(0, position).match(/\$([\p{L}\p{N}_:./@-]*)$/u);
  if (!prefix) return undefined;
  const start = position - prefix[1].length - 1;
  if (!isSkillTriggerPrefix(content, start) || !isSourcePosition(content, start)) return undefined;
  const suffix = content.slice(position).match(/^[\p{L}\p{N}_:./@-]*/u)?.[0] ?? "";
  return {
    start,
    end: position + suffix.length,
    text: prefix[1],
  };
}

// Labels escape Markdown brackets and backslashes; identity always comes from the ID.
const skillLink = /^\[((?:\\[^\r\n]|[^\]\\\r\n])*)\]\(skill:([A-Za-z0-9_][A-Za-z0-9_.@-]{0,255})\)/;

export function skillAt(content: string, start: number): InlineSkill | undefined {
  const match = skillLink.exec(content.slice(start));
  return match ? { start, end: start + match[0].length, id: match[2] } : undefined;
}

export function formatSkillReference(reference: SkillReference): string {
  const label = reference.name.replace(/[\r\n]/g, " ").replace(/[\\[\]]/g, "\\$&");
  return `[${label}](skill:${reference.id})`;
}

export function scanInlineSource<T extends { end: number }>(
  content: string,
  match: (start: number) => T | undefined,
): T[] {
  const references: T[] = [];
  let fence: { character: string; length: number } | undefined;
  let index = 0;
  while (index < content.length) {
    if (index === 0 || content[index - 1] === "\n") {
      const end = content.indexOf("\n", index);
      const lineEnd = end < 0 ? content.length : end + 1;
      const line = content.slice(index, lineEnd);
      const marker = /^ {0,3}(?:> ?)*(`{3,}|~{3,})([^\r\n]*)/.exec(line);
      if (fence) {
        if (
          marker &&
          marker[1][0] === fence.character &&
          marker[1].length >= fence.length &&
          !marker[2].trim()
        )
          fence = undefined;
        index = lineEnd;
        continue;
      }
      if (marker && (marker[1][0] !== "`" || !marker[2].includes("`"))) {
        fence = { character: marker[1][0], length: marker[1].length };
        index = lineEnd;
        continue;
      }
      if (/^(?: {4}|\t)/.test(line)) {
        index = lineEnd;
        continue;
      }
    }
    if (content[index] === "\\") {
      index += 2;
      continue;
    }
    if (content[index] === "`") {
      let runEnd = index + 1;
      while (content[runEnd] === "`") runEnd++;
      const run = content.slice(index, runEnd);
      let close = content.indexOf(run, runEnd);
      while (close >= 0 && (content[close - 1] === "`" || content[close + run.length] === "`"))
        close = content.indexOf(run, close + run.length);
      index = close < 0 ? runEnd : close + run.length;
      continue;
    }
    const reference = match(index);
    if (reference) {
      references.push(reference);
      index = reference.end;
    } else index++;
  }
  return references;
}

export function inlineSkills(content: string): InlineSkill[] {
  return scanInlineSource(content, (index) =>
    content[index] === "[" && content[index - 1] !== "!" ? skillAt(content, index) : undefined,
  );
}

export function isSourcePosition(content: string, position: number): boolean {
  return (
    scanInlineSource(content, (index) => (index === position ? { end: index + 1 } : undefined))
      .length > 0
  );
}

function replaceSkills(content: string, replace: (reference: InlineSkill) => string): string {
  let result = "";
  let start = 0;
  for (const reference of inlineSkills(content)) {
    result += content.slice(start, reference.start) + replace(reference);
    start = reference.end;
  }
  return result + content.slice(start);
}

export function withoutInlineSkills(content: string): string {
  return replaceSkills(content, () => "");
}

export function removeInlineSkill(content: string, id: string): string {
  return replaceSkills(content, (reference) =>
    reference.id === id ? "" : content.slice(reference.start, reference.end),
  );
}

export function messageText(
  content: string,
  capabilities: readonly CapabilityReference[] = [],
): string {
  const skills = new Map(
    capabilities.filter((reference) => reference.type === "skill").map((item) => [item.id, item]),
  );
  return replaceSkills(content, (reference) => {
    const skill = skills.get(reference.id);
    return skill ? `$${skill.name}` : content.slice(reference.start, reference.end);
  });
}

export function referencedCapabilities(
  content: string,
  candidates: readonly CapabilityReference[],
): CapabilityReference[] {
  const skills = new Map(
    candidates.filter((reference) => reference.type === "skill").map((item) => [item.id, item]),
  );
  const seen = new Set<string>();
  const references: CapabilityReference[] = [];
  for (const reference of inlineSkills(content)) {
    const skill = skills.get(reference.id);
    if (!skill || seen.has(skill.id)) continue;
    seen.add(skill.id);
    references.push(skill);
  }
  for (const reference of candidates) {
    const key = `mcp:${reference.id}`;
    if (reference.type === "skill" || seen.has(key)) continue;
    seen.add(key);
    references.push(reference);
  }
  return references;
}
