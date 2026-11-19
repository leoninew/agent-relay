import { describe, expect, it } from "vitest";
import { formatSkillReference, referencedCapabilities } from "@/domains/room/inlineSkills";
import { skillEditorParts } from "@/domains/room/skillEditorModel";
import { readMessageClipboard, writeMessageClipboard } from "@/domains/room/messageClipboard";
import {
  decodeMessage,
  documentMemberMentions,
  imageReferences,
  messageSlice,
} from "@/domains/room/messageEditorCodec";
import { Schema } from "@tiptap/pm/model";
import { NodeSelection } from "@tiptap/pm/state";
import type { SkillReference } from "@/services/roomApi";
import { roomResourcePath } from "@/domains/channel/channelRoutes";

describe("managed channel images", () => {
  it("decodes and displays a pasted image marker under the actual room and channel IDs", () => {
    const roomId = "0000000000122";
    const channelId = "0000000000123";
    const id = "img-0123456789abcdef0123456789abcdef";
    const url = roomResourcePath(roomId, channelId, `/image/${id}`);
    const marker = `![图\\[1\\]](${url})`;
    const expected = { type: "imageReference", attrs: { id, url, alt: "图[1]", marker } };

    expect(imageReferences(marker, roomId, channelId)[0].node).toEqual(expected);
    expect(decodeMessage(marker, [], roomId, channelId).content?.[0].content).toEqual([expected]);
  });

  it("does not decode managed images from a different channel or a legacy path", () => {
    const id = "img-0123456789abcdef0123456789abcdef";
    const path = `/api/room/0000000000122/channel/0000000000123/image/${id}`;
    const legacy = `/api/room/room-old/channel/channel-default/image/${id}`;
    expect(imageReferences(`![img](${path})`, "0000000000122", "0000000000223")).toEqual([]);
    expect(imageReferences(`![img](${legacy})`, "room-old", "channel-default")).toEqual([]);
  });
});

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

const schema = new Schema({
  nodes: {
    doc: { content: "messageBody" },
    messageBody: { content: "inline*" },
    text: { group: "inline" },
    mention: { group: "inline", inline: true, attrs: { id: {}, label: {}, marker: {} } },
    memberMention: { group: "inline", inline: true, attrs: { id: {}, label: {} } },
    hardBreak: { group: "inline", inline: true, attrs: { raw: {} } },
  },
});
const copy = (content: string, skills: SkillReference[]) =>
  writeMessageClipboard(
    schema.nodeFromJSON(decodeMessage(content, skills, "room", "channel")).content,
  );
describe("Message editor clipboard identity", () => {
  it("copies readable external text and internally restores exact markers and repeated identities", () => {
    const content = `前 ${marker}\n${marker} 后`;
    const copied = copy(content, [check]);
    expect(copied.text).toBe(`前 $${check.name}\n$${check.name} 后`);
    expect(readMessageClipboard(copied.data, [check], [])).toEqual({
      content,
      skills: [check],
      memberMentions: [],
    });
  });

  it("resolves by ID using the current room identity, never a copied name", () => {
    const copied = copy(marker, [check]);
    const renamed = { ...check, name: "current:name" };
    expect(readMessageClipboard(copied.data, [renamed], [])).toEqual({
      content: marker,
      skills: [renamed],
      memberMentions: [],
    });
    expect(readMessageClipboard(copied.data, [{ ...check, id: "another-id" }], [])).toEqual({
      content: `$${check.name}`,
      skills: [],
      memberMentions: [],
    });
  });

  it("downgrades an unavailable copied tag to readable text and preserves available tags", () => {
    const copied = copy(`${marker} ${formatSkillReference(fix)}`, [check, fix]);
    expect(readMessageClipboard(copied.data, [fix], [])).toEqual({
      content: `$${check.name} ${formatSkillReference(fix)}`,
      skills: [fix],
      memberMentions: [],
    });
  });

  it("keeps code examples readable as their original source", () => {
    const content = `\`${marker}\``;
    const copied = copy(content, [check]);
    expect(copied.text).toBe(content);
    expect(readMessageClipboard(copied.data, [check], [])).toEqual({
      content,
      skills: [],
      memberMentions: [],
    });
  });

  it("keeps only selected member nodes atomic and resolves against the destination roster", () => {
    const member = { id: "architect", name: "Worker" };
    const prefix = `${marker}\n@Worker `;
    const doc = schema.nodeFromJSON(
      decodeMessage(`${prefix}@Worker`, [check], "room", "channel", [
        { ...member, start: prefix.length, end: prefix.length + 7 },
      ]),
    );
    const copied = writeMessageClipboard(doc.content);
    const current = { ...member, name: "New name" };
    const paste = readMessageClipboard(copied.data, [], [current])!;
    const text = `$${check.name}\n@Worker `;
    expect(paste.content).toBe(`${text}@New name`);
    const fragment = messageSlice(
      schema,
      paste.content,
      paste.skills,
      "room",
      "channel",
      paste.memberMentions,
    );
    const restored = schema.topNodeType.create(
      null,
      schema.nodes.messageBody.create(null, fragment),
    );
    expect(documentMemberMentions(restored)).toEqual([
      { ...current, start: text.length, end: paste.content.length },
    ]);
    const selected = NodeSelection.create(doc, doc.content.size - 2);
    const justMember = writeMessageClipboard(selected.content().content);
    expect(justMember.text).toBe("@Worker");
    expect(readMessageClipboard(justMember.data, [], [{ ...member, id: "other" }])).toEqual({
      content: "@Worker",
      skills: [],
      memberMentions: [],
    });
  });

  it.each([
    "not JSON",
    "null",
    "{}",
    '{"version":2,"parts":["x"]}',
    '{"version":1,"parts":[{"type":"skill","id":4}]}',
  ])("ignores invalid private clipboard payload %s", (value) => {
    expect(readMessageClipboard(value, [check], [])).toBeUndefined();
  });
});
