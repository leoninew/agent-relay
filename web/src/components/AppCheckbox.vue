<template>
  <CheckboxRoot class="app-checkbox" :value="value" :disabled="disabled">
    <span class="app-checkbox-mark">
      <CheckboxIndicator><AppIcon name="check" /></CheckboxIndicator>
    </span>
    <slot />
  </CheckboxRoot>
</template>

<script setup lang="ts">
  import { CheckboxIndicator, CheckboxRoot } from "reka-ui";

  import AppIcon from "@/components/AppIcon.vue";

  defineProps<{ value: string; disabled?: boolean }>();
</script>
