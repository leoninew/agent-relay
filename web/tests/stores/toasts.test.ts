import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { useToastsStore } from "@/stores/toasts";

describe("toast state", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("retains the latest three notifications with their tones and distinct identities", () => {
    const toasts = useToastsStore();
    toasts.info({ key: "notice.roomCreated" });
    const first = toasts.success({ key: "notice.memberSaved" });
    const second = toasts.error({ key: "errors.save" });
    const third = toasts.success({ key: "notice.memberSaved" });

    expect(toasts.items).toEqual([
      { id: first, message: { key: "notice.memberSaved" }, tone: "success" },
      { id: second, message: { key: "errors.save" }, tone: "error" },
      { id: third, message: { key: "notice.memberSaved" }, tone: "success" },
    ]);
    expect(new Set(toasts.items.map((toast) => toast.id)).size).toBe(3);
  });

  it("dismisses only the requested notification and permits showing it again", () => {
    const toasts = useToastsStore();
    const first = toasts.success({ key: "notice.memberSaved" });
    const retained = toasts.error({ key: "errors.save" });

    toasts.dismiss(first);
    const repeated = toasts.success({ key: "notice.memberSaved" });

    expect(toasts.items.map((toast) => toast.id)).toEqual([retained, repeated]);
    expect(repeated).not.toBe(first);
  });
});
