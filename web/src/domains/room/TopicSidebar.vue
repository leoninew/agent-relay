<template>
  <RoomSidebarSection
    :title="t('sidebar.topics')"
    :action-label="t('sidebar.newTopic')"
    :busy="busy"
    @create="$emit('createTopic')"
  >
    <nav class="sidebar-list" :aria-label="t('sidebar.filterTopics')">
      <div class="sidebar-node sidebar-node-fixed">
        <button
          type="button"
          class="sidebar-list-item"
          :class="{ 'is-active': selectedTopicId === undefined }"
          :aria-pressed="selectedTopicId === undefined"
          :aria-label="t('sidebar.filterTopic', { name: t('sidebar.allTopics') })"
          @click="$emit('select', undefined)"
        >
          <span class="topic-identity">
            <AppIcon name="hash" class="sidebar-item-icon" />
            <span class="sidebar-node-name">{{ t("sidebar.allTopics") }}</span>
          </span>
        </button>
      </div>
      <VueDraggable
        v-model="topics"
        class="sidebar-sortable-list"
        draggable=".sidebar-node"
        handle=".sidebar-drag-handle"
        ghost-class="sidebar-drag-ghost"
        chosen-class="sidebar-drag-chosen"
        :animation="150"
        :disabled="busy"
      >
        <div v-for="topic in topics" :key="topic.id" class="sidebar-node">
          <button
            type="button"
            class="sidebar-drag-handle"
            :aria-label="t('sidebar.reorderTopic', { name: topic.name })"
            :title="t('sidebar.reorder')"
            :disabled="busy || topics.length < 2"
            @keydown.up.prevent="moveTopic(topic.id, -1)"
            @keydown.down.prevent="moveTopic(topic.id, 1)"
          >
            <AppIcon name="grip" />
          </button>
          <button
            type="button"
            class="sidebar-list-item"
            :class="{ 'is-active': selectedTopicId === topic.id }"
            :aria-pressed="selectedTopicId === topic.id"
            :aria-label="t('sidebar.filterTopic', { name: topic.name })"
            :title="topic.description"
            @click="$emit('select', topic.id)"
          >
            <TopicIdentity :topic="topic" />
          </button>
        </div>
      </VueDraggable>
    </nav>
  </RoomSidebarSection>
</template>

<script setup lang="ts">
  import { VueDraggable } from "vue-draggable-plus";
  import { useI18n } from "vue-i18n";

  import AppIcon from "@/components/AppIcon.vue";
  import RoomSidebarSection from "@/domains/room/RoomSidebarSection.vue";
  import TopicIdentity from "@/domains/room/TopicIdentity.vue";
  import { useSidebarOrder } from "@/domains/room/useSidebarOrder";
  import type { RoomSnapshot } from "@/services/roomApi";

  const { t } = useI18n();
  const props = defineProps<{
    snapshot: RoomSnapshot;
    busy: boolean;
    selectedTopicId?: string;
  }>();
  defineEmits<{
    select: [topicId: string | undefined];
    createTopic: [];
  }>();
  const { orderedItems: topics, moveItem: moveTopic } = useSidebarOrder(
    () => props.snapshot.room.id,
    "topics",
    () => props.snapshot.topics.filter((topic) => !topic.deletedAt),
  );
</script>
