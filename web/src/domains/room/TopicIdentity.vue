<template>
  <span class="topic-identity">
    <AppIcon name="hash" class="sidebar-item-icon" :data-topic="topic.id" />
    <span class="sidebar-node-name">{{ topic.name }}</span>
  </span>
</template>

<script setup lang="ts">
  import AppIcon from "@/components/AppIcon.vue";
  import type { Topic } from "@/services/roomApi";

  defineProps<{ topic: Pick<Topic, "id" | "name"> }>();
</script>
