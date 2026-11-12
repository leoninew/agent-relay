import { computed, ref, watch } from "vue";

import { browserStorage, readJSON, writeJSON } from "@/services/storage";

export function useStoredOrder<Item extends { id: string }>(
  key: () => string,
  items: () => Item[],
) {
  const storageKey = computed(key);
  const savedIds = ref<string[]>([]);

  watch(
    storageKey,
    (key) => {
      const storage = browserStorage();
      const saved = storage ? readJSON<unknown>(storage, key, []) : [];
      savedIds.value =
        Array.isArray(saved) && saved.every((id) => typeof id === "string") ? saved : [];
    },
    { immediate: true, flush: "sync" },
  );

  const orderedItems = computed({
    get: () => {
      const positions = new Map(savedIds.value.map((id, index) => [id, index]));
      return items().toSorted(
        (left, right) =>
          (positions.get(left.id) ?? positions.size) - (positions.get(right.id) ?? positions.size),
      );
    },
    set: (value: Item[]) => {
      savedIds.value = value.map((item) => item.id);
      const storage = browserStorage();
      if (storage) {
        writeJSON(storage, storageKey.value, savedIds.value);
      }
    },
  });

  function moveItem(itemId: string, offset: number): void {
    const reordered = [...orderedItems.value];
    const index = reordered.findIndex((item) => item.id === itemId);
    const target = index + offset;
    if (index < 0 || target < 0 || target >= reordered.length) return;
    const [item] = reordered.splice(index, 1);
    reordered.splice(target, 0, item);
    orderedItems.value = reordered;
  }

  return { orderedItems, moveItem };
}
