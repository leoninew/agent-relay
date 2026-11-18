import { describe, expect, it } from "vitest";
import { composerQueryAt } from "@/domains/room/composerQuery";

describe("composer suggestions", () => {
  it("opens an unfiltered member query at a bare @", () => {
    expect(composerQueryAt("@", 1)).toEqual({ kind: "member", text: "", start: 0, end: 1 });
  });

  it("matches Unicode member names and includes the remaining token for replacement", () => {
    const prefix = "你好，@开发";
    expect(composerQueryAt(`${prefix}者 请查看`, prefix.length)).toEqual({
      kind: "member",
      text: "开发",
      start: 3,
      end: 7,
    });
  });

  it("keeps @ inside a skill query", () => {
    const content = "$plugin@market";
    expect(composerQueryAt(content, content.length)).toEqual({
      kind: "skill",
      text: "plugin@market",
      start: 0,
      end: content.length,
    });
  });

  it("does not activate inside inline code", () => {
    expect(composerQueryAt("`@member`", "`@member".length)).toBeUndefined();
  });

  it.each(["name@example", "\\@member", "```\n@member", "#topic"])(
    "does not open a query for %s",
    (content) => expect(composerQueryAt(content, content.length)).toBeUndefined(),
  );
});
