<template>
  <section class="sidebar-section">
    <header class="room-panel-heading sidebar-section-heading">
      <h2 class="room-panel-title">{{ title }}</h2>
      <button
        type="button"
        class="icon-button"
        :aria-label="actionLabel"
        :title="actionLabel"
        :disabled="busy"
        @click="$emit('create')"
      >
        <AppIcon name="plus" />
      </button>
    </header>
    <slot />
  </section>
</template>

<script setup lang="ts">
  import AppIcon from "@/components/AppIcon.vue";

  defineProps<{
    title: string;
    actionLabel: string;
    busy: boolean;
  }>();
  defineEmits<{ create: [] }>();
</script>
