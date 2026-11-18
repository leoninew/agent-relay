import { setImmediate } from "node:timers/promises";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, ref } from "vue";
import { createPinia, setActivePinia } from "pinia";

import {
  modelPreview,
  modelTarget,
  selectionIsInMore,
  useSessionModels,
} from "@/domains/room/useSessionModels";
import { ApiClientError } from "@/services/api";
import { fetchMemberModels, updateMemberModel } from "@/services/roomApi";
import type { SessionModelCatalog } from "@/services/roomApi";
import { useToastsStore } from "@/stores/toasts";

import { roomFixture } from "../../fixtures/room";

vi.mock("@/services/roomApi", () => ({
  fetchMemberModels: vi.fn(),
  updateMemberModel: vi.fn(),
}));

function catalog(
  sessionId = "session-frontend",
  currentModel: string | null = "old",
): SessionModelCatalog {
  return {
    sessionId,
    currentModel,
    provider: "provider",
    models: [
      { id: "old-id", model: "old", displayName: "Old", description: "" },
      { id: "new-id", model: "new", displayName: "New", description: "" },
    ],
  };
}

function deferred<Value>() {
  let resolve!: (value: Value) => void;
  const promise = new Promise<Value>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

describe("session model selection", () => {
  const scopes: ReturnType<typeof effectScope>[] = [];

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(fetchMemberModels).mockReset().mockResolvedValue(catalog());
    vi.mocked(updateMemberModel).mockReset().mockResolvedValue(catalog("session-frontend", "new"));
  });
  afterEach(() => {
    scopes.forEach((scope) => scope.stop());
    scopes.length = 0;
  });

  function setup() {
    const room = ref("room");
    const channel = ref("channel");
    const members = ref(roomFixture().members);
    const selected = ref(["frontend-worker"]);
    const scope = effectScope();
    scopes.push(scope);
    let models!: ReturnType<typeof useSessionModels>;
    scope.run(() => {
      models = useSessionModels(
        () => room.value,
        () => channel.value,
        () => modelTarget(members.value, selected.value),
      );
    });
    return { room, channel, members, selected, models, scope, toasts: useToastsStore() };
  }

  it("only targets exactly one directly selected active agent binding", () => {
    const members = roomFixture().members;
    expect(modelTarget(members, ["frontend-worker"])?.sessionId).toBe("session-frontend");
    for (const selected of [[], ["frontend-worker", "backend-worker"], ["absent"], ["user"]]) {
      expect(modelTarget(members, selected)).toBeUndefined();
    }
    expect(
      modelTarget([{ ...members[0], deletedAt: "2026-11-15" }], [members[0].id]),
    ).toBeUndefined();
    expect(modelTarget([{ ...members[0], sessionId: null }], [members[0].id])).toBeUndefined();
  });

  it.each(["offline", "unknown"] as const)("does not load models for a %s session", (presence) => {
    const member = { ...roomFixture().members[0], presence };
    expect(modelTarget([member], [member.id])).toBeUndefined();
  });

  it("previews four model values and identifies a selected overflow item", () => {
    const options = Array.from({ length: 7 }, (_, index) => ({
      id: `option-${index}`,
      model: `model-${index}`,
      displayName: `Tip ${index}`,
      description: "not rendered",
    }));
    const full = catalog();
    full.models = options;
    full.currentModel = "model-6";
    expect(modelPreview(options)).toEqual(options.slice(0, 4));
    expect(selectionIsInMore(full)).toBe(true);
    full.currentModel = "model-2";
    expect(selectionIsInMore(full)).toBe(false);
  });

  it("reads real current model without treating a default or topic recipients as the target", async () => {
    vi.mocked(fetchMemberModels).mockResolvedValueOnce(catalog("session-frontend", "unlisted"));
    const { models, members } = setup();
    await setImmediate();
    expect(models.catalog.value?.currentModel).toBe("unlisted");
    expect(fetchMemberModels).toHaveBeenCalledTimes(1);
    expect(fetchMemberModels).toHaveBeenCalledWith("room", "frontend-worker", "channel");
    members.value[0].topicIds = ["frontend", "backend"];
    await setImmediate();
    expect(fetchMemberModels).toHaveBeenCalledTimes(1);
  });

  it("clears the model state when selection becomes multiple or absent", async () => {
    const { selected, models } = setup();
    await setImmediate();
    selected.value = ["frontend-worker", "backend-worker"];
    expect(models.catalog.value).toBeUndefined();
    await models.select("new");
    selected.value = [];
    await setImmediate();
    expect(updateMemberModel).not.toHaveBeenCalled();
    expect(fetchMemberModels).toHaveBeenCalledTimes(1);
  });

  it.each(["room", "channel", "binding"])(
    "rejects an old read after changing %s",
    async (change) => {
      const old = deferred<SessionModelCatalog>();
      vi.mocked(fetchMemberModels).mockReturnValueOnce(old.promise);
      const { room, channel, members, models } = setup();
      vi.mocked(fetchMemberModels).mockResolvedValue(
        catalog(change === "binding" ? "rebound" : "session-frontend", "new"),
      );
      if (change === "room") {
        room.value = "other-room";
      } else if (change === "channel") {
        channel.value = "other-channel";
      } else {
        members.value[0].sessionId = "rebound";
      }
      await setImmediate();
      old.resolve(catalog());
      await setImmediate();
      expect(models.catalog.value?.currentModel).toBe("new");
      expect(models.loading.value).toBe(false);
    },
  );

  it("ignores an old result even when selection returns to the original member", async () => {
    const old = deferred<SessionModelCatalog>();
    vi.mocked(fetchMemberModels).mockReturnValueOnce(old.promise);
    const { selected, models } = setup();
    selected.value = [];
    selected.value = ["frontend-worker"];
    await setImmediate();
    old.resolve(catalog("session-frontend", "stale"));
    await setImmediate();
    expect(models.catalog.value?.currentModel).toBe("old");
  });

  it("switches the exact binding once and only displays the confirmed model", async () => {
    const pending = deferred<SessionModelCatalog>();
    vi.mocked(updateMemberModel).mockReturnValueOnce(pending.promise);
    const { models } = setup();
    await setImmediate();
    const first = models.select("new");
    await models.select("new");
    expect(models.updating.value).toBe(true);
    expect(models.catalog.value?.currentModel).toBe("old");
    expect(updateMemberModel).toHaveBeenCalledTimes(1);
    expect(updateMemberModel).toHaveBeenCalledWith("room", "frontend-worker", "channel", {
      sessionId: "session-frontend",
      model: "new",
    });
    pending.resolve(catalog("session-frontend", "new"));
    await first;
    expect(models.catalog.value?.currentModel).toBe("new");
    expect(useToastsStore().items).toEqual([]);
  });

  it.each(["rejected", "unknown"])("rereads after %s without resubmitting", async (failure) => {
    vi.mocked(updateMemberModel).mockRejectedValueOnce(
      failure === "rejected"
        ? new ApiClientError("safe", "http_error", {
            status: 409,
            code: "session_model_update_rejected",
            requestId: "req",
          })
        : new ApiClientError("private", "network_error"),
    );
    const { models } = setup();
    await setImmediate();
    vi.mocked(fetchMemberModels).mockResolvedValueOnce(catalog("session-frontend", "new"));
    await models.select("new");
    expect(models.catalog.value?.currentModel).toBe("new");
    expect(useToastsStore().items[0].message.key).toBe(
      failure === "rejected"
        ? "errors.session_model_update_rejected"
        : "errors.session_model_update_unknown",
    );
    expect(useToastsStore().items[0].tone).toBe("error");
    if (failure === "rejected") {
      expect(useToastsStore().items[0].message.requestId).toBe("req");
    }
    expect(updateMemberModel).toHaveBeenCalledTimes(1);
    expect(fetchMemberModels).toHaveBeenCalledTimes(2);
  });

  it("does not apply an update result to a different member", async () => {
    const pending = deferred<SessionModelCatalog>();
    vi.mocked(updateMemberModel).mockReturnValueOnce(pending.promise);
    const { models, selected } = setup();
    await setImmediate();
    const update = models.select("new");
    vi.mocked(fetchMemberModels).mockResolvedValueOnce(catalog("session-backend", "other"));
    selected.value = ["backend-worker"];
    await setImmediate();
    pending.resolve(catalog("session-frontend", "new"));
    await update;
    expect(models.catalog.value?.currentModel).toBe("other");
    expect(useToastsStore().items).toEqual([]);
    expect(models.updating.value).toBe(false);
  });

  it("keeps failed reads and changed bindings unavailable until refreshed", async () => {
    vi.mocked(fetchMemberModels).mockResolvedValueOnce(catalog("wrong-session"));
    const { models } = setup();
    await setImmediate();
    expect(models.catalog.value).toBeUndefined();
    expect(useToastsStore().items[0]).toMatchObject({
      tone: "error",
      message: { key: "errors.session_binding_changed" },
    });
    await models.select("new");
    expect(updateMemberModel).not.toHaveBeenCalled();
    await models.refresh();
    expect(models.catalog.value?.sessionId).toBe("session-frontend");
  });

  it("does not start follow-up reads after disposal", async () => {
    const pending = deferred<SessionModelCatalog>();
    vi.mocked(updateMemberModel).mockReturnValueOnce(pending.promise);
    const { models, scope } = setup();
    await setImmediate();
    const update = models.select("new");
    scope.stop();
    pending.resolve(catalog("session-frontend", "new"));
    await update;
    expect(fetchMemberModels).toHaveBeenCalledTimes(1);
    expect(useToastsStore().items).toEqual([]);
  });
});
