<template>
  <button
    :type="type"
    class="app-button"
    :class="variant === 'plain' ? undefined : `${variant}-button`"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
    @click="handleClick"
  >
    <AppSpinner v-if="loading" />
    <slot v-else name="icon" />
    <span v-if="loading && loadingLabel">{{ loadingLabel }}</span>
    <slot v-else />
  </button>
</template>

<script setup lang="ts">
  import AppSpinner from "@/components/AppSpinner.vue";

  const props = withDefaults(
    defineProps<{
      type?: "button" | "submit" | "reset";
      variant?: "primary" | "secondary" | "warning" | "plain";
      loading?: boolean;
      loadingLabel?: string;
      disabled?: boolean;
    }>(),
    { type: "button", variant: "primary", loading: false, disabled: false, loadingLabel: "" },
  );
  const emit = defineEmits<{ click: [event: MouseEvent] }>();

  function handleClick(event: MouseEvent): void {
    if (props.disabled || props.loading) {
      event.preventDefault();
      return;
    }
    emit("click", event);
  }
</script>
