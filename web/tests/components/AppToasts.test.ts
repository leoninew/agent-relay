import { cleanup, fireEvent, render, screen, within } from "@testing-library/vue";
import { createPinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import AppToasts from "@/components/AppToasts.vue";
import { useToastsStore } from "@/stores/toasts";

describe("AppToasts", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  function renderToasts() {
    const pinia = createPinia();
    render(AppToasts, { global: { plugins: [pinia] } });
    return useToastsStore(pinia);
  }

  it("dismisses a notification through Reka UI and can show the same result again", async () => {
    const toasts = renderToasts();
    toasts.success("成员已保存");
    await nextTick();
    expect(screen.getByText("成员已保存")).toBeTruthy();

    await fireEvent.click(screen.getByRole("button", { name: "关闭提示" }));
    expect(toasts.items).toHaveLength(0);
    expect(screen.queryByText("成员已保存")).toBeNull();

    toasts.success("成员已保存");
    await nextTick();
    expect(screen.getByText("成员已保存")).toBeTruthy();
  });

  it("expires success notifications earlier and retains errors long enough to read", async () => {
    const toasts = renderToasts();
    toasts.success("消息已发送");
    toasts.error("发送失败，草稿已保留。请求 ID：req_send");
    await nextTick();
    const messages = within(screen.getByRole("list"));

    await vi.advanceTimersByTimeAsync(4100);
    expect(messages.queryByText("消息已发送")).toBeNull();
    expect(messages.getByText(/草稿已保留/)).toBeTruthy();
    expect(toasts.items).toHaveLength(1);

    await vi.advanceTimersByTimeAsync(4000);
    expect(messages.queryByText(/草稿已保留/)).toBeNull();
    expect(toasts.items).toHaveLength(0);
  });
});
