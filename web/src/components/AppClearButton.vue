<template>
  <Primitive
    as="button"
    type="button"
    class="app-clear-button"
    :aria-label="label"
    :title="label"
    :disabled="disabled"
    @mousedown.prevent
    @click="$emit('clear')"
  >
    <AppIcon name="close" />
  </Primitive>
</template>

<script setup lang="ts">
  import { Primitive } from "reka-ui";

  import AppIcon from "@/components/AppIcon.vue";

  defineProps<{ label: string; disabled?: boolean }>();
  defineEmits<{ clear: [] }>();
</script>
