import { flushPromises } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, ref } from "vue";

import { useRoomCapabilities } from "@/domains/room/useRoomCapabilities";
import { fetchRoomSkills } from "@/services/roomApi";

import { skillsFixture } from "../../fixtures/capabilities";
import { roomFixture } from "../../fixtures/room";

vi.mock("@/services/roomApi", () => ({ fetchRoomSkills: vi.fn() }));

function harness() {
  const fixture = roomFixture();
  const room = ref(fixture.room);
  let capabilities!: ReturnType<typeof useRoomCapabilities>;
  const scope = effectScope();
  scope.run(() => {
    capabilities = useRoomCapabilities(() => room.value);
  });
  return { scope, room, capabilities };
}

describe("room skill loading", () => {
  const scopes: ReturnType<typeof harness>["scope"][] = [];
  beforeEach(() => {
    vi.mocked(fetchRoomSkills).mockReset().mockResolvedValue(skillsFixture());
  });
  afterEach(() => {
    scopes.forEach((scope) => scope.stop());
    scopes.length = 0;
  });

  function setup() {
    const result = harness();
    scopes.push(result.scope);
    return result;
  }

  it("preloads skills, reuses the project catalog and refreshes explicitly", async () => {
    const { room, capabilities } = setup();
    await flushPromises();
    expect(fetchRoomSkills).toHaveBeenCalledTimes(1);
    room.value = { ...room.value, id: "same-project" };
    await flushPromises();
    expect(fetchRoomSkills).toHaveBeenCalledTimes(1);
    expect(capabilities.catalog.value.skills).toHaveLength(3);
    capabilities.refresh();
    await flushPromises();
    expect(fetchRoomSkills).toHaveBeenCalledTimes(2);
    expect(vi.mocked(fetchRoomSkills).mock.calls[1].slice(0, 2)).toEqual(["same-project", true]);
  });

  it("loads the current project catalog when the room changes", async () => {
    const { room, capabilities } = setup();
    await flushPromises();
    vi.mocked(fetchRoomSkills).mockResolvedValueOnce({ skills: [], errors: [] });
    room.value = { ...room.value, id: "other", projectPath: "D:/other" };
    await flushPromises();
    expect(capabilities.catalog.value.skills).toEqual([]);
    expect(capabilities.catalog.value.skillsLoading).toBe(false);
  });

  it("keeps partial skill results distinct from failure and allows an explicit retry", async () => {
    vi.mocked(fetchRoomSkills).mockResolvedValueOnce({
      ...skillsFixture(),
      errors: [{ code: "skill_load_failed", error: "部分技能加载失败" }],
    });
    const { capabilities } = setup();
    await flushPromises();
    expect(capabilities.catalog.value.skills).toHaveLength(3);
    expect(capabilities.catalog.value.issues).toEqual(["部分技能加载失败"]);
    vi.mocked(fetchRoomSkills).mockRejectedValueOnce(new Error("offline"));
    capabilities.refresh();
    await flushPromises();
    expect(capabilities.catalog.value.skills).toEqual([]);
    expect(capabilities.catalog.value.issues.join()).toContain("Skill 目录加载失败");
    capabilities.refresh();
    await flushPromises();
    expect(capabilities.catalog.value.skills).toHaveLength(3);
    expect(capabilities.catalog.value.issues).toEqual([]);
  });
});
