import { effectScope, ref } from "vue";
import type { EffectScope } from "vue";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useSidebarOrder } from "@/domains/room/useSidebarOrder";

describe("useSidebarOrder", () => {
  let scope: EffectScope;

  beforeEach(() => {
    localStorage.clear();
    scope = effectScope();
  });
  afterEach(() => scope.stop());

  it("keeps the chosen order while refreshed items, additions and removals take effect", () => {
    const items = ref([
      { id: "first", name: "First" },
      { id: "second", name: "Second" },
    ]);
    const { orderedItems, moveItem } = scope.run(() =>
      useSidebarOrder(
        () => "room-a",
        "topics",
        () => items.value,
      ),
    )!;

    moveItem("second", -1);
    expect(items.value.map((item) => item.id)).toEqual(["first", "second"]);
    items.value = [
      { id: "first", name: "First updated" },
      { id: "second", name: "Second updated" },
      { id: "third", name: "New topic" },
    ];
    expect(orderedItems.value.map((item) => item.name)).toEqual([
      "Second updated",
      "First updated",
      "New topic",
    ]);

    items.value = items.value.filter((item) => item.id !== "second");
    expect(orderedItems.value.map((item) => item.id)).toEqual(["first", "third"]);
  });

  it("stores topics and members separately for each room and restores their orders", () => {
    const roomId = ref("room-a");
    const items = [{ id: "first" }, { id: "second" }];
    const { orderedItems: topics } = scope.run(() =>
      useSidebarOrder(
        () => roomId.value,
        "topics",
        () => items,
      ),
    )!;
    const { orderedItems: members } = scope.run(() =>
      useSidebarOrder(
        () => roomId.value,
        "members",
        () => items,
      ),
    )!;

    topics.value = items.toReversed();
    expect(members.value).toEqual(items);
    roomId.value = "room-b";
    expect(topics.value).toEqual(items);
    members.value = items.toReversed();
    roomId.value = "room-a";
    expect(topics.value).toEqual(items.toReversed());
    expect(members.value).toEqual(items);

    const reopened = scope.run(() =>
      useSidebarOrder(
        () => "room-b",
        "members",
        () => items,
      ),
    )!;
    expect(reopened.orderedItems.value).toEqual(items.toReversed());
  });

  it("uses the default order when a stored preference has an invalid shape", () => {
    localStorage.setItem("relay-sidebar-order:room-a:topics", '{"order":"invalid"}');
    const items = [{ id: "first" }, { id: "second" }];
    const { orderedItems } = scope.run(() =>
      useSidebarOrder(
        () => "room-a",
        "topics",
        () => items,
      ),
    )!;
    expect(orderedItems.value).toEqual(items);
  });
});
