import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fetchChannelMessageHeads, fetchChannels, type Channel } from "@/services/channelApi";
import { fetchRooms } from "@/services/roomApi";
import { useChannelsStore } from "@/stores/channels";
import { useRoomsStore } from "@/stores/rooms";
import { useNavigationActivity } from "@/stores/navigationActivity";
import { roomFixture } from "../fixtures/room";

vi.mock("@/services/channelApi", () => ({
  fetchChannelMessageHeads: vi.fn(),
  fetchChannels: vi.fn(),
}));
vi.mock("@/services/roomApi", () => ({ fetchRooms: vi.fn() }));
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
  useRoomsStore().rooms = [{ ...roomFixture().room, id: "room" }];
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

it("reconciles changed IDs, retries failed loads and leaves unopened rooms lazy", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("document", Object.assign(new EventTarget(), { visibilityState: "visible" }));
  const room = (id: string) => ({ ...roomFixture().room, id });
  const channel = (roomId: string, id: string): Channel => ({
    roomId,
    id,
    name: id,
    description: "",
    workingPath: "",
    isDefault: false,
    status: "active",
    workspaceKind: "existing",
    createdAt: null,
  });
  const rooms = useRoomsStore();
  const channels = useChannelsStore();
  rooms.rooms = [room("kept"), room("gone")];
  vi.mocked(fetchChannels)
    .mockResolvedValueOnce([channel("gone", "default")])
    .mockResolvedValueOnce([channel("kept", "old")]);
  await channels.load("gone");
  await channels.load("kept");
  vi.mocked(fetchChannels)
    .mockClear()
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValue([channel("kept", "new"), { ...channel("kept", "old"), status: "archived" }]);
  vi.mocked(fetchRooms).mockResolvedValue([room("kept"), room("added")]);
  const rows = [head("added", 0), head("kept", 0, "new")];
  vi.mocked(fetchChannelMessageHeads).mockResolvedValue(rows);
  const activity = useNavigationActivity();
  const stop = activity.subscribe();
  await vi.advanceTimersByTimeAsync(0);
  expect(rooms.rooms.map(({ id }) => id)).toEqual(["kept", "added"]);
  expect(activity.unread.size).toBe(0);
  expect(fetchChannels).toHaveBeenCalledOnce();
  await vi.advanceTimersByTimeAsync(5000);
  expect(channels.activeChannels("kept").map(({ id }) => id)).toEqual(["new"]);
  vi.mocked(fetchChannelMessageHeads).mockResolvedValue([head("kept", 3, "new"), head("added", 2)]);
  await vi.advanceTimersByTimeAsync(5000);
  expect(activity.unread.size).toBe(2);
  expect(fetchRooms).toHaveBeenCalledOnce();
  expect(vi.mocked(fetchChannels).mock.calls.map(([roomId]) => roomId)).toEqual(["kept", "kept"]);
  stop();
});
