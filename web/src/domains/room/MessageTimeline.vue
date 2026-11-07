<template>
  <div ref="timeline" class="message-timeline" :aria-busy="loading" aria-label="消息时间线">
    <AppLoading v-if="loading" class="timeline-placeholder">正在加载讨论…</AppLoading>
    <div v-else-if="unavailable" class="timeline-placeholder">暂时无法加载消息，请重试。</div>
    <div v-else-if="messages.length === 0" class="timeline-placeholder">
      <span class="empty-icon"><AppIcon name="chat" /></span>
      <h3>暂无消息</h3>
    </div>
    <template v-else>
      <template v-for="(message, index) in messages" :key="message.id">
        <div v-if="startsNewDay(index)" class="timeline-date">
          <span>{{ formatDate(message.createdAt) }}</span>
        </div>
        <article
          class="message"
          :class="{ 'is-selected': message.id === selectedMessageId }"
          tabindex="0"
          :aria-label="`${message.senderName}的消息`"
          @click="$emit('select', message.id)"
          @keydown.enter.self.prevent="$emit('select', message.id)"
          @keydown.space.self.prevent="$emit('select', message.id)"
        >
          <div class="message-body">
            <div class="message-heading">
              <span class="message-identity">
                <MemberAvatar :member="findMember(message.senderId)" />
                <span class="message-author">{{ message.senderName }}</span>
              </span>
              <div v-if="message.topicIds.length" class="message-topics" aria-label="所属话题">
                <span
                  v-for="topicId in message.topicIds"
                  :key="topicId"
                  class="topic-chip"
                  :data-topic="topicId"
                >
                  # {{ topics.find((topic) => topic.id === topicId)?.name ?? topicId }}
                </span>
              </div>
              <div
                v-if="message.mentionedMemberIds.length"
                class="message-mentions"
                aria-label="@ 成员"
              >
                <span
                  v-for="memberId in message.mentionedMemberIds"
                  :key="memberId"
                  class="mention-chip"
                >
                  @ {{ findMember(memberId)?.name ?? memberId }}
                </span>
              </div>
              <button
                type="button"
                class="message-reply icon-button"
                :aria-label="`引用消息 #${message.seq}`"
                title="引用回复"
                @click.stop="$emit('reply', message)"
              >
                <AppIcon name="reply" />
              </button>
            </div>
            <button
              v-if="message.replyToMessageId"
              type="button"
              class="message-reference"
              @click.stop="$emit('reference', message.replyToMessageId)"
            >
              <AppIcon name="reply" />
              <span>引用 {{ referenceLabel(message.replyToMessageId) }}</span>
            </button>
            <p class="message-content">
              {{ message.content }}
              <time class="message-time" :datetime="message.createdAt">
                {{ formatTime(message.createdAt) }}
              </time>
            </p>
            <div
              v-if="message.deliveries.length || message.id === selectedMessageId"
              class="message-dispatch-footer"
            >
              <span v-if="message.deliveries.length" class="message-delivery-summary">
                {{ deliverySummary(message) }}
              </span>
              <button
                type="button"
                class="message-details-link"
                :aria-label="`查看消息 #${message.seq} 详情`"
                :aria-expanded="message.id === selectedMessageId && detailsOpen"
                @click.stop="showDetails(message.id)"
              >
                查看详情<AppIcon name="arrow" />
              </button>
            </div>
          </div>
        </article>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { ref } from "vue";

  import AppIcon from "@/components/AppIcon.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import MemberAvatar from "@/domains/room/MemberAvatar.vue";
  import type { Member, RoomMessage, Topic } from "@/services/roomApi";
  import { formatDate, formatTime } from "@/utils/time";

  const props = defineProps<{
    messages: RoomMessage[];
    members: Member[];
    topics: Topic[];
    selectedMessageId?: string;
    detailsOpen: boolean;
    loading: boolean;
    unavailable: boolean;
  }>();
  const emit = defineEmits<{
    reply: [message: RoomMessage];
    reference: [messageId: string];
    select: [messageId: string];
    showDetails: [];
  }>();

  const timeline = ref<HTMLElement>();

  function findMember(memberId: string | null): Member | undefined {
    return props.members.find((member) => member.id === memberId);
  }

  function showDetails(messageId: string): void {
    emit("select", messageId);
    emit("showDetails");
  }

  function deliverySummary(message: RoomMessage): string {
    const enqueued = message.deliveries.filter(
      (delivery) => delivery.status === "delivered",
    ).length;
    const queued = message.deliveries.filter((delivery) => delivery.status === "queued").length;
    const pending = message.deliveries.filter((delivery) => delivery.status === "pending").length;
    return [
      pending ? `${pending} 待提交` : "",
      enqueued ? `${enqueued} 已入队` : "",
      queued ? `${queued} 排队中` : "",
    ]
      .filter(Boolean)
      .join(" · ");
  }

  function startsNewDay(index: number): boolean {
    return (
      index === 0 ||
      formatDate(props.messages[index - 1].createdAt) !==
        formatDate(props.messages[index].createdAt)
    );
  }

  function referenceLabel(messageId: string): string {
    const message = props.messages.find((item) => item.id === messageId);
    return message ? `#${message.seq} · ${message.senderName}` : messageId;
  }

  function scrollToEnd(): void {
    if (timeline.value) {
      timeline.value.scrollTop = timeline.value.scrollHeight;
    }
  }

  function scrollToMessage(messageId: string): void {
    const index = props.messages.findIndex((message) => message.id === messageId);
    const article = timeline.value?.querySelectorAll<HTMLElement>("article")[index];
    article?.scrollIntoView({ behavior: "smooth", block: "center" });
    article?.focus({ preventScroll: true });
  }

  defineExpose({ scrollToEnd, scrollToMessage });
</script>
