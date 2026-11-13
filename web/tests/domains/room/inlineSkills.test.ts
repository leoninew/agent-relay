import { describe, expect, it } from "vitest";
import {
  formatSkillReference,
  inlineSkills,
  messageText,
  referencedCapabilities,
  removeInlineSkill,
  skillQueryAt,
  withoutInlineSkills,
} from "@/domains/room/inlineSkills";
import { renderMessage } from "@/domains/room/messageMarkdown";
import type { SkillReference } from "@/services/roomApi";
import cases from "../../../../tests/fixtures/inline_skills.json";

const check: SkillReference = { type: "skill", id: "skill-check", name: "dev-check" };
const fix: SkillReference = { type: "skill", id: "skill-fix", name: "dev-fix" };

describe("skill picker query", () => {
  it.each([
    { content: "$", before: "", text: "" },
    { content: "请检查消息($", before: "请检查消息(", text: "" },
    { content: "message！$dev-check", before: "message！", text: "dev-check" },
    { content: "🙂$", before: "🙂", text: "" },
    { content: "第一行\n第二行 $dev", before: "第一行\n第二行 ", text: "dev" },
  ])("opens at a valid boundary and preserves it: $content", ({ content, before, text }) => {
    const query = skillQueryAt(content, content.length);
    expect(query).toEqual({ start: before.length, end: content.length, text });
    const replacement =
      content.slice(0, query!.start) + formatSkillReference(check) + content.slice(query!.end);
    expect(replacement).toBe(before + formatSkillReference(check));
  });

  it("replaces the whole query when the caret is inside its name", () => {
    const content = "正文：$dev-check 后面的消息";
    const query = skillQueryAt(content, "正文：$dev".length);
    expect(query).toEqual({ start: 3, end: "正文：$dev-check".length, text: "dev" });
    expect(content.slice(0, query!.start) + content.slice(query!.end)).toBe("正文： 后面的消息");
  });

  it("does not open without a dollar query at the caret", () => {
    expect(skillQueryAt("正常正文", 4)).toBeUndefined();
    expect(skillQueryAt("正文$dev", "正文$dev".length)).toBeUndefined();
  });
});

describe("inline skill format", () => {
  it.each(cases)("keeps positions and literal Markdown: $content", ({ content, ids, text }) => {
    const references = inlineSkills(content);
    expect(references.map((reference) => reference.id)).toEqual(ids);
    for (const reference of references)
      expect(content.slice(reference.start, reference.end)).toContain(`](skill:${reference.id})`);
    expect(messageText(content, [check, fix])).toBe(text);
  });

  it("records a position in text that survives earlier edits and Unicode", () => {
    const marker = formatSkillReference(check);
    const content = `新增内容🙂\n在这里 ${marker} 检查`;
    expect(inlineSkills(content)).toEqual([
      {
        id: check.id,
        start: content.indexOf(marker),
        end: content.indexOf(marker) + marker.length,
      },
    ]);
    expect(messageText(content, [check])).toBe("新增内容🙂\n在这里 $dev-check 检查");
  });

  it("escapes names while keeping identity independent of the editable label", () => {
    const marker = formatSkillReference({ ...check, name: "a[b]\\c" });
    expect(inlineSkills(marker).map((reference) => reference.id)).toEqual([check.id]);
    expect(messageText(marker, [check])).toBe("$dev-check");
  });

  it("removes all occurrences of a skill while preserving literal examples and other skills", () => {
    const content = `${formatSkillReference(check)} 文本 ${formatSkillReference(fix)} ${formatSkillReference(check)} \`${formatSkillReference(check)}\``;
    expect(removeInlineSkill(content, check.id)).toBe(
      ` 文本 ${formatSkillReference(fix)}  \`${formatSkillReference(check)}\``,
    );
    expect(referencedCapabilities(content, [check, fix, check])).toEqual([check, fix]);
    expect(referencedCapabilities(removeInlineSkill(content, check.id), [check, fix])).toEqual([
      fix,
    ]);
    // A restored marker can reuse its selected identity after native textarea undo.
    expect(referencedCapabilities(content, [check, fix])).toEqual([check, fix]);
    expect(
      referencedCapabilities(`${formatSkillReference(fix)} ${formatSkillReference(check)}`, [
        check,
        fix,
        { type: "mcp_server", id: "mcp-example", name: "Example" },
      ]),
    ).toEqual([fix, check, { type: "mcp_server", id: "mcp-example", name: "Example" }]);
  });

  it("treats only skill markers as an empty body and preserves ordinary content", () => {
    expect(withoutInlineSkills(` ${formatSkillReference(check)}\n`)).toBe(" \n");
    expect(withoutInlineSkills(`检查 ${formatSkillReference(check)}`)).toBe("检查 ");
  });
});

describe("message skill rendering", () => {
  it("renders repeated skill chips in place and avoids a duplicate list above the body", () => {
    const rendered = renderMessage(
      `前 ${formatSkillReference(check)} 中 ${formatSkillReference(check)} 后`,
      [check, fix],
    );
    expect(rendered.html.match(/class="message-skill-chip"/g)).toHaveLength(2);
    expect(rendered.html).toMatch(/前 <span class="message-skill-chip"/);
    expect(rendered.html).toContain("</span></span> 中 <span");
    expect(rendered.html).toContain("</span></span> 后");
    expect(rendered.remainingCapabilities).toEqual([fix]);
  });

  it("leaves code, escaped examples, images, and unknown references literal", () => {
    const marker = formatSkillReference(check);
    for (const content of [
      `\`${marker}\``,
      `\`\`\`\n${marker}\n\`\`\``,
      `\\${marker}`,
      `!${marker}`,
    ]) {
      expect(renderMessage(content, [check]).html).not.toContain('class="message-skill-chip"');
    }
    expect(renderMessage(marker).html).not.toContain('class="message-skill-chip"');
  });

  it("escapes untrusted names and keeps ordinary Markdown rendering", () => {
    const rendered = renderMessage(`**加粗** ${formatSkillReference(check)}`, [
      { ...check, name: '\"><img src=x onerror="alert(1)">' },
    ]);
    expect(rendered.html).toContain("<strong>加粗</strong>");
    expect(rendered.html).toContain("&lt;img");
    expect(rendered.html).not.toContain("<img");
  });
});
