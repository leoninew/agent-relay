import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fetchChannelMessageHeads } from "@/services/channelApi";
import { useNavigationActivity } from "@/stores/navigationActivity";

vi.mock("@/services/channelApi", () => ({ fetchChannelMessageHeads: vi.fn() }));
const head = (roomId: string, latestSeq: number, channelId = "default") => ({
  roomId,
  channelId,
  latestSeq,
});

beforeEach(() => {
  const data = new Map<string, string>();
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (key: string) => data.get(key) ?? null,
      setItem: (key: string, value: string) => data.set(key, value),
    },
  });
  setActivePinia(createPinia());
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  vi.resetAllMocks();
});

it("baselines history once, then tracks each channel independently across reloads", () => {
  const store = useNavigationActivity();
  store.apply([head("one", 7), head("two", 10)]);
  expect(store.unread.size).toBe(0);
  const incoming = [head("one", 11), head("two", 13), head("one", 12, "new")];
  store.apply(incoming);
  store.presented("one", "default", 11);
  expect(store.unread.get("one")).toEqual(new Set(["default", "new"]));
  store.visible = true;
  store.presented("one", "default", 11);
  expect(store.unread.get("one")).toEqual(new Set(["new"]));
  setActivePinia(createPinia());
  const restored = useNavigationActivity();
  restored.apply(incoming);
  expect(restored.unread).toEqual(store.unread);
  restored.apply([head("one", 11), head("two", 10)]);
  expect(restored.unread.size).toBe(0);
});

it("only polls in the foreground and keeps reminders through a refresh failure", async () => {
  vi.useFakeTimers();
  const doc = Object.assign(new EventTarget(), { visibilityState: "visible" });
  vi.stubGlobal("document", doc);
  const fetch = vi.mocked(fetchChannelMessageHeads);
  fetch
    .mockResolvedValueOnce([head("room", 0)])
    .mockResolvedValueOnce([head("room", 3)])
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValue([head("room", 4)]);
  const store = useNavigationActivity();
  const stop = store.subscribe();
  await vi.advanceTimersByTimeAsync(10000);
  expect(store.unread.has("room")).toBe(true);
  doc.visibilityState = "hidden";
  doc.dispatchEvent(new Event("visibilitychange"));
  await vi.advanceTimersByTimeAsync(15000);
  expect(fetch).toHaveBeenCalledTimes(3);
  doc.visibilityState = "visible";
  doc.dispatchEvent(new Event("visibilitychange"));
  expect(fetch).toHaveBeenCalledTimes(4);
  stop();
});
