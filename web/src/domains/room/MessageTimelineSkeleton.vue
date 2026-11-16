<template>
  <div class="message-timeline-skeleton" :class="{ 'is-pending': !visible }" aria-hidden="true">
    <div
      v-for="(message, index) in messages"
      :key="index"
      class="message skeleton-message"
      :class="{ 'is-user': index === 1 }"
      :style="{ width: message.width }"
    >
      <div class="message-main">
        <div class="skeleton-message-heading">
          <AppSkeleton class="skeleton-message-marker" />
          <AppSkeleton class="skeleton-message-author" />
          <AppSkeleton class="skeleton-message-topic" />
        </div>
        <div class="skeleton-message-lines">
          <AppSkeleton
            v-for="(width, line) in message.lines"
            :key="line"
            :style="{ width: `${width}%` }"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import AppSkeleton from "@/components/AppSkeleton.vue";

  withDefaults(defineProps<{ visible?: boolean }>(), { visible: true });

  const messages = [
    { width: "82%", lines: [100, 92, 64] },
    { width: "62%", lines: [100, 76] },
    { width: "90%", lines: [96, 100, 88, 56] },
    { width: "70%", lines: [100, 68] },
  ];
</script>

<style scoped>
  .is-pending {
    visibility: hidden;
  }
  .message-timeline-skeleton {
    overflow: hidden;
    pointer-events: none;
  }
  .skeleton-message-heading {
    display: flex;
    align-items: center;
    min-width: 0;
    gap: 10px;
  }
  .skeleton-message-heading > .app-skeleton {
    flex-shrink: 1;
    min-width: 0;
  }
  .skeleton-message-marker {
    width: 16px;
    height: 16px;
    border-radius: 50%;
  }
  .skeleton-message-author {
    width: 96px;
  }
  .skeleton-message-topic {
    width: 56px;
  }
  .skeleton-message-lines {
    display: grid;
    gap: 10px;
    margin-top: 12px;
  }
  @container conversation (max-width: 440px) {
    .skeleton-message {
      min-width: 90%;
    }
  }
</style>
