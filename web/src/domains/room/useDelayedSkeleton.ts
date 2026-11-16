import { readonly, ref, watch } from "vue";

export function useDelayedSkeleton(pending: () => boolean, queryKey: () => string) {
  const visible = ref(false);

  watch(
    [pending, queryKey],
    ([loading], _previous, onCleanup) => {
      visible.value = false;
      if (!loading) return;
      const timer = setTimeout(() => {
        visible.value = true;
      }, 150);
      onCleanup(() => clearTimeout(timer));
    },
    { immediate: true, flush: "sync" },
  );

  return readonly(visible);
}
