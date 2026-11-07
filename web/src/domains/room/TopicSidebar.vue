<template>
  <aside class="topic-sidebar" aria-label="主题导航">
    <div class="sidebar-section-heading">
      <span class="eyebrow">讨论主题</span>
      <button
        type="button"
        class="icon-button"
        aria-label="新建主题"
        title="新建主题"
        :disabled="busy"
        @click="$emit('createTopic')"
      >
        <AppIcon name="plus" />
      </button>
    </div>
    <nav class="topic-list" aria-label="筛选讨论主题">
      <button
        type="button"
        class="topic-nav-item"
        :class="{ 'is-active': !selectedTopicId }"
        :aria-pressed="!selectedTopicId"
        @click="$emit('select', undefined)"
      >
        <AppIcon name="chat" />
        <span>全部消息</span>
        <span class="topic-count">{{ snapshot.summary.totalMessages }}</span>
      </button>
      <button
        v-for="topic in snapshot.topics"
        :key="topic.id"
        type="button"
        class="topic-nav-item"
        :class="{ 'is-active': selectedTopicId === topic.id }"
        :aria-pressed="selectedTopicId === topic.id"
        :title="topic.description"
        @click="$emit('select', topic.id)"
      >
        <AppIcon name="hash" :data-topic="topic.id" />
        <span>{{ topic.name }}</span>
        <span class="topic-count">{{ topic.messageCount }}</span>
      </button>
    </nav>

    <slot />
  </aside>
</template>

<script setup lang="ts">
  import AppIcon from "@/components/AppIcon.vue";
  import type { RoomSnapshot } from "@/services/roomApi";

  defineProps<{ snapshot: RoomSnapshot; busy: boolean; selectedTopicId?: string }>();
  defineEmits<{ select: [topicId: string | undefined]; createTopic: [] }>();
</script>
