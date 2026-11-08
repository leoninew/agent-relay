<template>
  <section class="member-topic-positions" :aria-label="`${member.name}的查阅位置`">
    <h3>查阅位置</h3>
    <p class="member-position-note">服务提供过的最大消息序号，允许跳读。</p>
    <dl v-if="positions.length">
      <div v-for="position in positions" :key="position.topicId" class="member-position-row">
        <dt>
          # {{ topics.find((topic) => topic.id === position.topicId)?.name ?? position.topicId }}
        </dt>
        <dd>
          <span>{{ position.seq ? `位置 #${position.seq}` : "尚无查阅位置" }}</span>
          <span>位置后新增 {{ position.laterCount }} 条</span>
          <time v-if="position.updatedAt" :datetime="position.updatedAt">{{
            formatDateTime(position.updatedAt)
          }}</time>
        </dd>
      </div>
    </dl>
    <p v-else class="member-position-note">暂无订阅话题</p>
  </section>
</template>

<script setup lang="ts">
  import type { Member, Topic, TopicPosition } from "@/services/roomApi";
  import { formatDateTime } from "@/utils/time";

  defineProps<{ member: Member; topics: Topic[]; positions: TopicPosition[] }>();
</script>
