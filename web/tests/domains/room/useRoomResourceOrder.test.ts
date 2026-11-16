import { effectScope, ref } from "vue";
import type { EffectScope } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { orderResourceIds } from "@/domains/room/orderResourceIds";
import { useRoomResourceOrder } from "@/domains/room/useRoomResourceOrder";
import type * as storage from "@/services/storage";
import { roomFixture } from "../../fixtures/room";

const saved = vi.hoisted(() => new Map<string, string>());
vi.mock("@/services/storage", async (importOriginal) => ({
  ...(await importOriginal<typeof storage>()),
  browserStorage: () => ({
    getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => saved.set(key, value),
    removeItem: (key: string) => saved.delete(key),
  }),
}));

describe("room resource order", () => {
  let scope: EffectScope;
  beforeEach(() => {
    saved.clear();
    scope = effectScope();
  });
  afterEach(() => scope.stop());

  it("shares drag and keyboard order with composer and detail lists, retaining history", () => {
    const snapshot = ref(roomFixture());
    snapshot.value.topics[1].deletedAt = "2026-11-15T00:00:00Z";
    snapshot.value.members[1].deletedAt = "2026-11-15T00:00:00Z";
    const order = scope.run(() =>
      useRoomResourceOrder(
        () => snapshot.value,
        () => "default",
      ),
    )!;

    order.moveTopic("backend", -1);
    order.moveMember("test-worker", -1);
    expect(order.activeTopics.value.map((topic) => topic.id)).toEqual(["backend", "summary"]);
    expect(order.topics.value.map((topic) => topic.id)).toEqual(["backend", "summary", "frontend"]);
    expect(order.activeAgents.value.map((member) => member.id)).toEqual([
      "test-worker",
      "frontend-worker",
    ]);
    expect(order.members.value.map((member) => member.id)).toEqual([
      "user",
      "test-worker",
      "frontend-worker",
      "backend-worker",
    ]);

    order.activeTopics.value = order.activeTopics.value.toReversed();
    order.activeAgents.value = order.activeAgents.value.toReversed();
    expect(order.topics.value[0].id).toBe("summary");
    expect(order.members.value[1].id).toBe("frontend-worker");
    expect(snapshot.value.topics[0].id).toBe("summary");
    expect(snapshot.value.members[0].id).toBe("frontend-worker");
  });

  it("restores saved room and channel orders without leaking changes between channels", () => {
    saved.set("conflua-sidebar-order:conflua:channel-a:topics", '["backend","summary","frontend"]');
    const channel = ref("channel-a");
    const snapshot = roomFixture();
    const order = scope.run(() =>
      useRoomResourceOrder(
        () => snapshot,
        () => channel.value,
      ),
    )!;
    expect(order.activeTopics.value[0].id).toBe("backend");
    channel.value = "channel-b";
    expect(order.activeTopics.value[0].id).toBe("summary");
    channel.value = "channel-a";
    expect(order.activeTopics.value[0].id).toBe("backend");
  });

  it("orders referenced subsets by panel order and retains unknown historical IDs at the end", () => {
    const ids = ["missing-a", "first", "second", "missing-b"];
    expect(orderResourceIds(ids, [{ id: "second" }, { id: "first" }])).toEqual([
      "second",
      "first",
      "missing-a",
      "missing-b",
    ]);
    expect(ids).toEqual(["missing-a", "first", "second", "missing-b"]);
  });
});
