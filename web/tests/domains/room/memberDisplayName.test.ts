import { describe, expect, it } from "vitest";

import { memberDisplayName } from "@/domains/room/memberDisplayName";

describe("channel member display names", () => {
  it("uses the member kind for the human label in authors and replies", () => {
    expect(memberDisplayName({ kind: "human", name: "本频道用户" }, "0000000000124", "你")).toBe(
      "你",
    );
    expect(memberDisplayName({ kind: "agent", name: "user" }, "0000000000125", "你")).toBe("user");
    expect(memberDisplayName(undefined, "0000000000126", "你")).toBe("0000000000126");
  });
});
