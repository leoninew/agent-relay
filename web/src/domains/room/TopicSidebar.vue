<template>
  <aside class="topic-sidebar" aria-label="话题导航">
    <header class="room-panel-heading sidebar-section-heading">
      <h2 class="room-panel-title">话题</h2>
      <button
        type="button"
        class="icon-button"
        aria-label="新建话题"
        title="新建话题"
        :disabled="busy"
        @click="$emit('createTopic')"
      >
        <AppIcon name="plus" />
      </button>
    </header>
    <nav class="topic-list" aria-label="筛选话题">
      <button
        type="button"
        class="topic-nav-item"
        :class="{ 'is-active': !selectedTopicId && !selectedMemberId }"
        :aria-pressed="!selectedTopicId && !selectedMemberId"
        @click="$emit('select', undefined)"
      >
        <AppIcon name="chat" />
        <span>全部消息</span>
        <span class="topic-count">{{ snapshot.summary.totalMessages }}</span>
      </button>
      <VueDraggable
        v-model="topics"
        class="topic-sortable-list"
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
            :aria-label="`调整话题顺序：${topic.name}`"
            title="拖动排序，也可使用上下方向键"
            :disabled="busy || topics.length < 2"
            @keydown.up.prevent="moveTopic(topic.id, -1)"
            @keydown.down.prevent="moveTopic(topic.id, 1)"
          >
            <AppIcon name="grip" />
          </button>
          <button
            type="button"
            class="topic-nav-item"
            :class="{ 'is-active': selectedTopicId === topic.id }"
            :aria-pressed="selectedTopicId === topic.id"
            :aria-label="`筛选话题：${topic.name}`"
            :title="topic.description"
            @click="$emit('select', topic.id)"
          >
            <AppIcon name="hash" :data-topic="topic.id" />
            <span class="sidebar-node-name">{{ topic.name }}</span>
            <span class="topic-count">{{ topic.messageCount }}</span>
          </button>
          <div class="sidebar-node-actions">
            <button
              type="button"
              :aria-label="`编辑话题：${topic.name}`"
              :disabled="busy"
              @click="$emit('editTopic', topic)"
            >
              编辑
            </button>
            <button
              type="button"
              :aria-label="`删除话题：${topic.name}`"
              :disabled="busy"
              @click="$emit('deleteTopic', topic)"
            >
              删除
            </button>
          </div>
        </div>
      </VueDraggable>
    </nav>

    <slot />
  </aside>
</template>

<script setup lang="ts">
  import { VueDraggable } from "vue-draggable-plus";

  import AppIcon from "@/components/AppIcon.vue";
  import { useSidebarOrder } from "@/domains/room/useSidebarOrder";
  import type { RoomSnapshot, Topic } from "@/services/roomApi";

  const props = defineProps<{
    snapshot: RoomSnapshot;
    busy: boolean;
    selectedTopicId?: string;
    selectedMemberId?: string;
  }>();
  defineEmits<{
    select: [topicId: string | undefined];
    createTopic: [];
    editTopic: [topic: Topic];
    deleteTopic: [topic: Topic];
  }>();
  const { orderedItems: topics, moveItem: moveTopic } = useSidebarOrder(
    () => props.snapshot.room.id,
    "topics",
    () => props.snapshot.topics.filter((topic) => !topic.deletedAt),
  );
</script>
