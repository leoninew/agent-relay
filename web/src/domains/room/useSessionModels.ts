import { computed, onScopeDispose, ref, watch } from "vue";

import { ApiClientError, describeApiError } from "@/services/api";
import { fetchMemberModels, updateMemberModel } from "@/services/roomApi";
import type { Member, SessionModelCatalog } from "@/services/roomApi";
import { useToastsStore } from "@/stores/toasts";

export function modelTarget(members: Member[], selectedIds: string[]): Member | undefined {
  if (selectedIds.length !== 1) {
    return undefined;
  }
  return members.find(
    (member) =>
      member.id === selectedIds[0] &&
      member.kind === "agent" &&
      !member.deletedAt &&
      Boolean(member.sessionId) &&
      (member.presence === "available" || member.presence === "busy"),
  );
}

export function modelPreview(models: SessionModelCatalog["models"] | undefined) {
  return models?.slice(0, 4) ?? [];
}

export function selectionIsInMore(catalog: SessionModelCatalog | undefined): boolean {
  return Boolean(catalog?.models.slice(4).some((option) => option.model === catalog.currentModel));
}

export function useSessionModels(
  roomId: () => string,
  channelId: () => string,
  member: () => Member | undefined,
) {
  const toasts = useToastsStore();
  const catalog = ref<SessionModelCatalog>();
  const loading = ref(false);
  const pending = ref(new Set<string>());
  const scope = computed(() => {
    const target = member();
    return target?.sessionId
      ? JSON.stringify([roomId(), channelId(), target.id, target.sessionId])
      : undefined;
  });
  const updating = computed(() => Boolean(scope.value && pending.value.has(scope.value)));
  let generation = 0;
  let readSequence = 0;
  let disposed = false;

  function validate(result: SessionModelCatalog, sessionId: string): SessionModelCatalog {
    if (result.sessionId !== sessionId) {
      throw new ApiClientError("Session binding changed.", "http_error", {
        status: 409,
        code: "session_binding_changed",
      });
    }
    return result;
  }

  async function refresh(): Promise<void> {
    const target = member();
    if (disposed || !scope.value || !target?.sessionId || updating.value) {
      return;
    }
    const version = generation;
    const sequence = ++readSequence;
    const sessionId = target.sessionId;
    loading.value = true;
    catalog.value = undefined;
    try {
      const result = await fetchMemberModels(roomId(), target.id, channelId());
      if (version !== generation || sequence !== readSequence) {
        return;
      }
      catalog.value = validate(result, sessionId);
    } catch (caught) {
      if (version === generation && sequence === readSequence) {
        toasts.error(describeApiError(caught, "errors.memberModels"));
      }
    } finally {
      if (version === generation && sequence === readSequence) {
        loading.value = false;
      }
    }
  }

  async function select(model: string): Promise<void> {
    const target = member();
    const key = scope.value;
    if (
      disposed ||
      !key ||
      !target?.sessionId ||
      loading.value ||
      updating.value ||
      !catalog.value?.models.some((option) => option.model === model) ||
      catalog.value.currentModel === model
    ) {
      return;
    }
    const version = generation;
    const sessionId = target.sessionId;
    let failed = false;
    pending.value.add(key);
    try {
      const result = await updateMemberModel(roomId(), target.id, channelId(), {
        sessionId,
        model,
      });
      if (version !== generation) {
        return;
      }
      const confirmed = validate(result, sessionId);
      if (confirmed.currentModel !== model) {
        throw new ApiClientError("Unconfirmed model update.", "contract_mismatch");
      }
      catalog.value = confirmed;
    } catch (caught) {
      if (version !== generation) {
        return;
      }
      const rejected =
        caught instanceof ApiClientError &&
        caught.kind === "http_error" &&
        caught.status !== undefined &&
        caught.status < 500;
      toasts.error(
        describeApiError(
          caught,
          rejected ? "errors.memberModelRejected" : "errors.session_model_update_unknown",
        ),
      );
      failed = true;
      catalog.value = undefined;
    } finally {
      pending.value.delete(key);
      if (scope.value === key && (version !== generation || failed)) {
        await refresh();
      }
    }
  }

  watch(
    scope,
    () => {
      generation++;
      readSequence++;
      catalog.value = undefined;
      loading.value = false;
      void refresh();
    },
    { immediate: true, flush: "sync" },
  );
  onScopeDispose(() => {
    disposed = true;
    generation++;
  });

  return { catalog, loading, updating, refresh, select };
}
