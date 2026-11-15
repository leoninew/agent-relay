import { describe, expect, it } from "vitest";

import type { JSONStorage } from "@/services/storage";
import { createChannelSelectionStorage } from "@/domains/channel/channelSelection";

function memoryStorage(): JSONStorage {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => void values.delete(key),
  };
}

describe("channel selection storage", () => {
  it("restores selections independently per room", () => {
    const storage = memoryStorage();
    const first = createChannelSelectionStorage(storage);
    first.save("room-a", "channel-api");
    first.save("room-b", "channel-design");

    const restored = createChannelSelectionStorage(storage);

    expect(restored.load("room-a")).toBe("channel-api");
    expect(restored.load("room-b")).toBe("channel-design");
    expect(restored.load("room-c")).toBeUndefined();
  });

  it("removes only the selected room's cached channel", () => {
    const storage = memoryStorage();
    const selection = createChannelSelectionStorage(storage);
    selection.save("room-a", "channel-api");
    selection.save("room-b", "channel-design");

    selection.remove("room-a");

    expect(selection.load("room-a")).toBeUndefined();
    expect(selection.load("room-b")).toBe("channel-design");
  });
});
