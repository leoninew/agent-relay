import { describe, expect, it } from "vitest";

import { memberSidebarAction } from "@/domains/room/memberSidebarAction";

import { roomFixture } from "../../fixtures/room";

describe("member sidebar actions", () => {
  it.each([
    ["busy", "interrupt"],
    ["available", undefined],
    ["offline", "delete"],
    ["unknown", "delete"],
  ] as const)("maps %s presence to %s", (presence, expected) => {
    const member = { ...roomFixture().members[0], presence };
    expect(memberSidebarAction(member)).toBe(expected);
  });

  it("does not offer actions for human or deleted members", () => {
    const members = roomFixture().members;
    expect(memberSidebarAction(members[3])).toBeUndefined();
    expect(
      memberSidebarAction({ ...members[0], deletedAt: "2026-11-16T00:00:00Z" }),
    ).toBeUndefined();
  });
});
