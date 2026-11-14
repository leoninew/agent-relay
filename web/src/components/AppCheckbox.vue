<template>
  <CheckboxRoot
    :model-value="model"
    class="app-checkbox"
    :value="value"
    :disabled="disabled"
    @update:model-value="model = $event === true"
  >
    <span class="app-checkbox-mark">
      <CheckboxIndicator><AppIcon name="check" /></CheckboxIndicator>
    </span>
    <slot />
  </CheckboxRoot>
</template>

<script setup lang="ts">
  import { CheckboxIndicator, CheckboxRoot } from "reka-ui";

  import AppIcon from "@/components/AppIcon.vue";

  defineProps<{ value?: string; disabled?: boolean }>();
  const model = defineModel<boolean>();
</script>
