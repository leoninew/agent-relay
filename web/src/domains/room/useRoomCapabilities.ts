import { computed, onScopeDispose, ref, watch } from "vue";
import type { MessageDescriptor } from "@/i18n";
import en from "@/i18n/en";

import { describeApiError } from "@/services/api";
import { fetchRoomSkills } from "@/services/roomApi";
import type { Room, SkillCatalog } from "@/services/roomApi";

export type ComposerCatalog = {
  skills: SkillCatalog["skills"];
  skillsLoading: boolean;
  issues: MessageDescriptor[];
};

type Cached<Result> = { expires: number; promise: Promise<Result> };

function cached<Result>(
  cache: Map<string, Cached<Result>>,
  key: string,
  load: () => Promise<Result>,
  force: boolean,
): Promise<Result> {
  const existing = cache.get(key);
  if (!force && existing && existing.expires > Date.now()) return existing.promise;
  const entry = { expires: Date.now() + 60_000, promise: load() };
  cache.set(key, entry);
  void entry.promise.catch(() => {
    if (cache.get(key) === entry) cache.delete(key);
  });
  return entry.promise;
}

export function useRoomCapabilities(room: () => Room | undefined) {
  const skillCache = new Map<string, Cached<SkillCatalog>>();
  const controllers = new Set<AbortController>();
  const skills = ref<SkillCatalog>({ skills: [], errors: [] });
  const skillsLoading = ref(false);
  const skillError = ref<MessageDescriptor>();
  let skillVersion = 0;
  let active = true;

  function request<Result>(load: (signal: AbortSignal) => Promise<Result>): Promise<Result> {
    const controller = new AbortController();
    controllers.add(controller);
    return load(controller.signal).finally(() => controllers.delete(controller));
  }

  async function loadSkills(force = false): Promise<void> {
    if (!active) return;
    const version = ++skillVersion;
    const current = room();
    skills.value = { skills: [], errors: [] };
    skillError.value = undefined;
    skillsLoading.value = Boolean(current);
    if (!current) return;
    try {
      const result = await cached(
        skillCache,
        current.projectPath,
        () => request((signal) => fetchRoomSkills(current.id, force, signal)),
        force,
      );
      if (version === skillVersion) skills.value = result;
    } catch (caught) {
      if (version === skillVersion) skillError.value = describeApiError(caught, "errors.skills");
    } finally {
      if (version === skillVersion) skillsLoading.value = false;
    }
  }

  watch(
    () => JSON.stringify([room()?.id, room()?.projectPath]),
    () => void loadSkills(),
    { immediate: true },
  );
  function pause(): void {
    active = false;
    skillVersion++;
    controllers.forEach((controller) => controller.abort());
    skillCache.clear();
    skillsLoading.value = false;
  }
  function resume(): void {
    active = true;
    void loadSkills();
  }
  onScopeDispose(pause);

  const catalog = computed<ComposerCatalog>(() => ({
    skills: skills.value.skills,
    skillsLoading: skillsLoading.value,
    issues: [
      ...(skillError.value ? [skillError.value] : []),
      ...skills.value.errors.map((issue) => ({
        key: Object.hasOwn(en.errors, issue.code) ? `errors.${issue.code}` : "errors.skills",
      })),
    ],
  }));

  function refresh(): void {
    void loadSkills(true);
  }

  return { catalog, refresh, pause, resume };
}
