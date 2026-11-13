import { describe, expect, it } from "vitest";
import { formatSkillReference, referencedCapabilities } from "@/domains/room/inlineSkills";
import {
  readSkillClipboard,
  skillEditorParts,
  writeSkillClipboard,
} from "@/domains/room/skillEditorModel";
import type { SkillReference } from "@/services/roomApi";

const check: SkillReference = { type: "skill", id: "skill-check", name: "best:dev-check" };
const fix: SkillReference = { type: "skill", id: "skill-fix", name: "best:fix" };
const marker = formatSkillReference(check);
describe("Skill editor serialization and atomic ranges", () => {
  it("round trips multiline text, HTML-looking text, emoji and duplicate original markers", () => {
    const original = `[alias\\[x\\]](skill:${check.id})`;
    const content = `😀 <img onerror='x'>\n${original}\n${original}\u200b`;
    const parts = skillEditorParts(content, [check]);
    expect(parts.map((part) => part.text).join("")).toBe(content);
    expect(parts.filter((part) => part.skill).map((part) => part.skill)).toEqual([check, check]);
    expect(referencedCapabilities(content, [check])).toEqual([check]);
  });

  it("keeps code, escaped examples, unknown IDs and Tagify JSON as plain parts", () => {
    const content = `\`${marker}\`\n\`\`\`md\n${marker}\n\`\`\`\n\\${marker}\n[unknown](skill:unknown) [[{"value":"x"}]]`;
    expect(skillEditorParts(content, [check])).toEqual([
      { start: 0, end: content.length, text: content },
    ]);
  });
});

describe("Skill editor clipboard identity", () => {
  it("copies readable external text and internally restores exact markers and repeated identities", () => {
    const content = `前 ${marker}\n${marker} 后`;
    const copied = writeSkillClipboard(content, [check]);
    expect(copied.text).toBe(`前 $${check.name}\n$${check.name} 后`);
    expect(readSkillClipboard(copied.data, [check])).toEqual({ content, skills: [check] });
  });

  it("resolves by ID using the current room identity, never a copied name", () => {
    const copied = writeSkillClipboard(marker, [check]);
    const renamed = { ...check, name: "current:name" };
    expect(readSkillClipboard(copied.data, [renamed])).toEqual({
      content: marker,
      skills: [renamed],
    });
    expect(readSkillClipboard(copied.data, [{ ...check, id: "another-id" }])).toEqual({
      content: `$${check.name}`,
      skills: [],
    });
  });

  it("downgrades an unavailable copied tag to readable text and preserves available tags", () => {
    const copied = writeSkillClipboard(`${marker} ${formatSkillReference(fix)}`, [check, fix]);
    expect(readSkillClipboard(copied.data, [fix])).toEqual({
      content: `$${check.name} ${formatSkillReference(fix)}`,
      skills: [fix],
    });
  });

  it("keeps code examples readable as their original source", () => {
    const content = `\`${marker}\``;
    const copied = writeSkillClipboard(content, [check]);
    expect(copied.text).toBe(content);
    expect(readSkillClipboard(copied.data, [check])).toEqual({ content, skills: [] });
  });

  it.each([
    "not JSON",
    "null",
    "{}",
    '{"version":2,"content":"x","skills":[]}',
    '{"version":1,"content":"x","skills":[{"type":"skill","id":4}]}',
  ])("ignores invalid private clipboard payload %s", (value) => {
    expect(readSkillClipboard(value, [check])).toBeUndefined();
  });
});
