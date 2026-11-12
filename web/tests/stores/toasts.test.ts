import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { useToastsStore } from "@/stores/toasts";

describe("toast state", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("retains the latest three notifications with their tones and distinct identities", () => {
    const toasts = useToastsStore();
    toasts.info("旧提示");
    const first = toasts.success("保存完成");
    const second = toasts.error("保存失败");
    const third = toasts.success("保存完成");

    expect(toasts.items).toEqual([
      { id: first, message: "保存完成", tone: "success" },
      { id: second, message: "保存失败", tone: "error" },
      { id: third, message: "保存完成", tone: "success" },
    ]);
    expect(new Set(toasts.items.map((toast) => toast.id)).size).toBe(3);
  });

  it("dismisses only the requested notification and permits showing it again", () => {
    const toasts = useToastsStore();
    const first = toasts.success("成员已保存");
    const retained = toasts.error("请求失败");

    toasts.dismiss(first);
    const repeated = toasts.success("成员已保存");

    expect(toasts.items.map((toast) => toast.id)).toEqual([retained, repeated]);
    expect(repeated).not.toBe(first);
  });
});
