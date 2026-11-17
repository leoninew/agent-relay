import { describe, expect, it } from "vitest";

import { memberSessionName } from "@/domains/room/memberSessionName";

import { roomFixture } from "../../fixtures/room";

describe("member session names", () => {
  it("resolves the original session name through the member binding", () => {
    const snapshot = roomFixture();

    expect(memberSessionName({ id: "frontend-worker" }, snapshot.members, snapshot.sessions)).toBe(
      "前端会话",
    );
  });

  it("returns undefined when the bound session is unavailable", () => {
    const snapshot = roomFixture();

    expect(
      memberSessionName({ id: "backend-worker" }, snapshot.members, snapshot.sessions),
    ).toBeUndefined();
  });
});
