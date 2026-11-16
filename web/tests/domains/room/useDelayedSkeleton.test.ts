import { effectScope, ref } from "vue";
import type { EffectScope } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDelayedSkeleton } from "@/domains/room/useDelayedSkeleton";

describe("delayed room skeleton", () => {
  let scope: EffectScope;

  beforeEach(() => {
    vi.useFakeTimers();
    scope = effectScope();
  });

  afterEach(() => {
    scope.stop();
    vi.useRealTimers();
  });

  function loadingState() {
    const pending = ref(true);
    const queryKey = ref("channel-a");
    const visible = scope.run(() =>
      useDelayedSkeleton(
        () => pending.value,
        () => queryKey.value,
      ),
    )!;
    return { pending, queryKey, visible };
  }

  it("shows the skeleton only after loading lasts 150ms", () => {
    const { visible } = loadingState();

    vi.advanceTimersByTime(149);
    expect(visible.value).toBe(false);
    vi.advanceTimersByTime(1);
    expect(visible.value).toBe(true);
  });

  it("keeps the skeleton hidden when a short load completes", () => {
    const { pending, visible } = loadingState();

    vi.advanceTimersByTime(100);
    pending.value = false;
    vi.advanceTimersByTime(150);

    expect(visible.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("hides immediately when content is ready without a minimum display time", () => {
    const { pending, visible } = loadingState();
    vi.advanceTimersByTime(150);

    pending.value = false;

    expect(visible.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("starts a fresh delay when the query changes", () => {
    const { queryKey, visible } = loadingState();
    vi.advanceTimersByTime(100);

    queryKey.value = "channel-b";
    vi.advanceTimersByTime(149);
    expect(visible.value).toBe(false);
    vi.advanceTimersByTime(1);
    expect(visible.value).toBe(true);
  });

  it("clears pending display when its scope is disposed", () => {
    const { visible } = loadingState();

    scope.stop();
    vi.advanceTimersByTime(150);

    expect(visible.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });
});
