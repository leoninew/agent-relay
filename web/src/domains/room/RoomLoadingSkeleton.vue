<template>
  <span class="sr-only" role="status">{{ t("room.loading") }}</span>
  <div class="room-loading-state" role="region" :aria-label="t('room.title')" aria-busy="true">
    <RoomWorkbench
      :details-open="false"
      :class="{ 'room-skeleton-pending': !visible }"
      aria-hidden="true"
      inert
    >
      <template #sidebar>
        <aside class="room-sidebar">
          <section v-for="section in sections" :key="section.name" class="sidebar-section">
            <div class="room-panel-heading sidebar-section-heading">
              <AppSkeleton class="room-skeleton-title" />
              <AppSkeleton class="room-skeleton-icon" />
            </div>
            <div class="sidebar-list">
              <div
                v-for="row in section.rows"
                :key="row"
                class="room-skeleton-row room-skeleton-sidebar-row"
              >
                <AppSkeleton class="room-skeleton-icon" />
                <AppSkeleton class="room-skeleton-name" />
              </div>
            </div>
          </section>
        </aside>
      </template>

      <section class="conversation-panel">
        <div class="conversation-messages">
          <div class="room-panel-heading conversation-heading">
            <div class="conversation-title">
              <AppSkeleton class="room-skeleton-title" />
            </div>
            <div class="conversation-actions">
              <div class="conversation-search">
                <AppSkeleton class="room-skeleton-search" />
                <AppSkeleton class="room-skeleton-button" />
              </div>
              <AppSkeleton class="room-skeleton-button" />
            </div>
          </div>
          <div class="message-timeline room-skeleton-timeline">
            <MessageTimelineSkeleton />
          </div>
        </div>
        <div class="room-composer">
          <div class="composer-fields">
            <div class="room-skeleton-row room-skeleton-routing">
              <AppSkeleton class="room-skeleton-title" />
              <AppSkeleton class="room-skeleton-tag" />
              <AppSkeleton class="room-skeleton-name" />
            </div>
            <div class="composer-editor">
              <div class="room-skeleton-editor">
                <AppSkeleton />
                <AppSkeleton />
              </div>
              <AppSkeleton class="room-skeleton-send" />
            </div>
          </div>
        </div>
      </section>

      <template #details>
        <aside class="message-details">
          <div class="room-panel-heading message-details-heading">
            <AppSkeleton class="room-skeleton-title" />
          </div>
          <div class="message-details-content">
            <div v-for="field in 3" :key="field" class="room-skeleton-detail">
              <AppSkeleton class="room-skeleton-title" />
              <AppSkeleton />
            </div>
            <section class="message-detail-section room-skeleton-detail">
              <AppSkeleton class="room-skeleton-title" />
              <div v-for="row in 3" :key="row" class="room-skeleton-row">
                <AppSkeleton />
                <AppSkeleton class="room-skeleton-tag" />
              </div>
            </section>
          </div>
        </aside>
      </template>
    </RoomWorkbench>
  </div>
</template>

<script setup lang="ts">
  import { useI18n } from "vue-i18n";

  import AppSkeleton from "@/components/AppSkeleton.vue";
  import MessageTimelineSkeleton from "@/domains/room/MessageTimelineSkeleton.vue";
  import RoomWorkbench from "@/domains/room/RoomWorkbench.vue";

  defineProps<{ visible: boolean }>();

  const { t } = useI18n();
  const sections = [
    { name: "channels", rows: 2 },
    { name: "topics", rows: 4 },
    { name: "members", rows: 5 },
  ];
</script>

<style scoped>
  .room-loading-state {
    height: 100%;
    min-height: 0;
  }
  .room-skeleton-pending {
    visibility: hidden;
  }
  .room-skeleton-row {
    display: flex;
    align-items: center;
    min-width: 0;
    gap: 10px;
  }
  .room-skeleton-row > .app-skeleton {
    flex-shrink: 1;
    min-width: 0;
  }
  .room-skeleton-sidebar-row {
    min-height: 32px;
    padding-inline: 12px;
  }
  .room-skeleton-title {
    width: 72px;
  }
  .room-skeleton-icon {
    width: 16px;
    height: 16px;
  }
  .room-skeleton-name {
    width: 96px;
  }
  .room-skeleton-sidebar-row:nth-child(3n + 2) .room-skeleton-name {
    width: 72px;
  }
  .room-skeleton-sidebar-row:nth-child(3n) .room-skeleton-name {
    width: 120px;
  }
  .room-skeleton-tag {
    width: 56px;
  }
  .room-skeleton-search {
    flex: 1;
    min-width: 0;
    height: 36px;
  }
  .room-skeleton-button {
    width: 64px;
    height: 36px;
  }
  .room-skeleton-timeline {
    overflow: hidden;
  }
  .room-skeleton-routing {
    min-height: 36px;
    padding-bottom: 8px;
  }
  .room-skeleton-editor {
    display: grid;
    align-content: space-between;
    min-width: 0;
    height: 2lh;
    padding-block: 4px;
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
  }
  .room-skeleton-editor > :first-child {
    width: 75%;
  }
  .room-skeleton-editor > :last-child {
    width: 45%;
  }
  .room-skeleton-send {
    width: 88px;
    height: 32px;
  }
  .room-skeleton-detail {
    display: grid;
    gap: 12px;
    margin-bottom: 24px;
  }
  @container conversation (max-width: 440px) {
    .room-skeleton-send {
      width: 36px;
      height: 36px;
    }
  }
</style>
