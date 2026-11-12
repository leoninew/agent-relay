import { effectScope, ref } from "vue";
import type { EffectScope } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useStoredOrder } from "@/composables/useStoredOrder";
import type * as storage from "@/services/storage";

const saved = vi.hoisted(() => new Map<string, string>());
vi.mock("@/services/storage", async (importOriginal) => ({
  ...(await importOriginal<typeof storage>()),
  browserStorage: () => ({
    getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => saved.set(key, value),
    removeItem: (key: string) => saved.delete(key),
  }),
}));

describe("useStoredOrder", () => {
  let scope: EffectScope;

  beforeEach(() => {
    saved.clear();
    scope = effectScope();
  });
  afterEach(() => scope.stop());

  it("keeps the chosen order while refreshed items, additions and removals take effect", () => {
    const items = ref([
      { id: "first", name: "First" },
      { id: "second", name: "Second" },
    ]);
    const { orderedItems, moveItem } = scope.run(() =>
      useStoredOrder(
        () => "room-a",
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

  it("isolates storage keys and restores saved order when the key changes or reopens", () => {
    const storageKey = ref("first");
    const items = [{ id: "first" }, { id: "second" }];
    const { orderedItems } = scope.run(() =>
      useStoredOrder(
        () => storageKey.value,
        () => items,
      ),
    )!;

    orderedItems.value = items.toReversed();
    storageKey.value = "second";
    expect(orderedItems.value).toEqual(items);
    storageKey.value = "first";
    expect(orderedItems.value).toEqual(items.toReversed());

    const reopened = scope.run(() =>
      useStoredOrder(
        () => "first",
        () => items,
      ),
    )!;
    expect(reopened.orderedItems.value).toEqual(items.toReversed());
  });

  it("uses the default order when a stored preference has an invalid shape", () => {
    saved.set("room-a", '{"order":"invalid"}');
    const items = [{ id: "first" }, { id: "second" }];
    const { orderedItems } = scope.run(() =>
      useStoredOrder(
        () => "room-a",
        () => items,
      ),
    )!;
    expect(orderedItems.value).toEqual(items);
  });
});
