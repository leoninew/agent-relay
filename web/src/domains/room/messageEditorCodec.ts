import type { JSONContent } from "@tiptap/core";
import type { Node as EditorNode, Schema } from "@tiptap/pm/model";
import type { Transaction } from "@tiptap/pm/state";
import MarkdownIt from "markdown-it";
import { scanInlineSource } from "@/domains/room/inlineSkills";
import { skillEditorParts } from "@/domains/room/skillEditorModel";
import type { SkillReference } from "@/services/roomApi";

export type ImageReference = { id: string; url: string; alt: string; marker: string };
type Reference = { start: number; end: number; node: JSONContent };
const markdown = new MarkdownIt();

export function imageReferences(content: string, roomId: string): Reference[] {
  return scanInlineSource(content, (start) => {
    if (content.slice(start, start + 2) !== "![") return;
    const match =
      /^!\[((?:\\[^\r\n]|[^\]\\\r\n])*)\]\((\/api\/room\/[A-Za-z0-9_-]+\/image\/(img-[a-f0-9]{32}))\)/.exec(
        content.slice(start),
      );
    if (!match || match[2] !== `/api/room/${encodeURIComponent(roomId)}/image/${match[3]}`) return;
    const image: ImageReference = {
      id: match[3],
      url: match[2],
      alt: markdown.utils.unescapeAll(match[1]),
      marker: match[0],
    };
    return { start, end: start + match[0].length, node: { type: "imageReference", attrs: image } };
  });
}

function references(
  content: string,
  skills: readonly SkillReference[],
  roomId: string,
): Reference[] {
  return [
    ...skillEditorParts(content, skills)
      .filter((part) => part.skill)
      .map((part) => ({
        start: part.start,
        end: part.end,
        node: {
          type: "mention",
          attrs: { id: part.skill!.id, label: part.skill!.name, marker: part.text },
        },
      })),
    ...imageReferences(content, roomId),
  ].sort((a, b) => a.start - b.start);
}

export function textNodes(text: string): JSONContent[] {
  return text
    .split(/(\r\n|\r|\n)/)
    .filter(Boolean)
    .map((part) =>
      /^[\r\n]+$/.test(part)
        ? { type: "hardBreak", attrs: { raw: part } }
        : { type: "text", text: part },
    );
}

export function decodeMessage(
  content: string,
  skills: readonly SkillReference[],
  roomId: string,
): JSONContent {
  const nodes: JSONContent[] = [];
  let from = 0;
  for (const reference of references(content, skills, roomId)) {
    if (reference.start < from) continue;
    nodes.push(...textNodes(content.slice(from, reference.start)), reference.node);
    from = reference.end;
  }
  nodes.push(...textNodes(content.slice(from)));
  return { type: "doc", content: [{ type: "messageBody", content: nodes }] };
}

export function nodeSource(node: EditorNode): string {
  if (node.isText) return node.text ?? "";
  if (node.type.name === "hardBreak") return node.attrs.raw as string;
  if (node.type.name === "mention" || node.type.name === "imageReference")
    return node.attrs.marker as string;
  let result = "";
  node.forEach((child) => {
    result += nodeSource(child);
  });
  return result;
}

export function documentSkills(doc: EditorNode): SkillReference[] {
  const skills = new Map<string, SkillReference>();
  doc.descendants((node) => {
    if (node.type.name === "mention" && !skills.has(node.attrs.id as string))
      skills.set(node.attrs.id as string, {
        type: "skill",
        id: node.attrs.id as string,
        name: node.attrs.label as string,
      });
  });
  return [...skills.values()];
}

function units(doc: EditorNode) {
  let offset = 0;
  const result: { node: EditorNode; pos: number; start: number; end: number }[] = [];
  doc.firstChild?.forEach((node, pos) => {
    const text = nodeSource(node);
    result.push({ node, pos: pos + 1, start: offset, end: offset + text.length });
    offset += text.length;
  });
  return result;
}

export function sourceOffset(doc: EditorNode, position: number): number {
  for (const unit of units(doc)) {
    if (position <= unit.pos) return unit.start;
    if (position < unit.pos + unit.node.nodeSize)
      return unit.node.isText ? unit.start + position - unit.pos : unit.end;
  }
  return nodeSource(doc).length;
}

function documentPosition(doc: EditorNode, offset: number): number {
  for (const unit of units(doc)) {
    if (offset <= unit.start) return unit.pos;
    if (offset < unit.end) return unit.node.isText ? unit.pos + offset - unit.start : unit.pos;
  }
  return doc.content.size - 1;
}

// Only replace changed reference spans. ProseMirror maps the selection/history through these steps.
export function reconcileReferences(
  tr: Transaction,
  skills: readonly SkillReference[],
  roomId: string,
): Transaction {
  const desired = references(nodeSource(tr.doc), skills, roomId);
  for (const unit of units(tr.doc).reverse()) {
    if (!["mention", "imageReference"].includes(unit.node.type.name)) continue;
    const match = desired.find(
      (ref) =>
        ref.start === unit.start && ref.end === unit.end && ref.node.type === unit.node.type.name,
    );
    if (!match)
      tr.replaceWith(
        unit.pos,
        unit.pos + unit.node.nodeSize,
        tr.doc.type.schema.text(nodeSource(unit.node)),
      );
  }
  for (const ref of desired.reverse()) {
    const from = documentPosition(tr.doc, ref.start);
    const to = documentPosition(tr.doc, ref.end);
    const node = tr.doc.type.schema.nodeFromJSON(ref.node);
    if (to === from + 1 && tr.doc.nodeAt(from)?.eq(node)) continue;
    tr.replaceWith(from, to, node);
  }
  return tr;
}

export function messageSlice(
  schema: Schema,
  content: string,
  skills: readonly SkillReference[],
  roomId: string,
) {
  return schema.nodeFromJSON(decodeMessage(content, skills, roomId)).firstChild!.content;
}
