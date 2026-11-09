<template>
  <div ref="timeline" class="message-timeline" :aria-busy="loading" aria-label="消息时间线">
    <AppLoading v-if="loading" class="timeline-placeholder">正在加载讨论…</AppLoading>
    <div v-else-if="unavailable" class="timeline-placeholder">暂时无法加载消息，请重试。</div>
    <div v-else-if="messages.length === 0" class="timeline-placeholder">
      <span class="empty-icon"><AppIcon name="chat" /></span>
      <h3>暂无消息</h3>
    </div>
    <template v-else>
      <div v-if="hasMore" class="timeline-page-actions">
        <AppButton
          variant="plain"
          :loading="loadingOlder"
          loading-label="加载中…"
          @click="$emit('loadOlder')"
        >
          加载更早消息
        </AppButton>
      </div>
      <template v-for="(message, index) in messages" :key="message.id">
        <div v-if="startsNewDay(index)" class="timeline-date">
          <span>{{ formatDate(message.createdAt) }}</span>
        </div>
        <article
          class="message"
          :class="{ 'is-selected': message.id === selectedMessageId }"
          tabindex="0"
          :aria-label="`${memberName(message.senderId)}的消息`"
          @click="$emit('select', message.id)"
          @keydown.enter.self.prevent="$emit('select', message.id)"
          @keydown.space.self.prevent="$emit('select', message.id)"
        >
          <div class="message-body">
            <div class="message-heading">
              <span class="message-identity">
                <MemberAvatar :member="findMember(message.senderId)" />
                <span class="message-author">{{ memberName(message.senderId) }}</span>
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
      <div v-if="hasNewer" class="timeline-page-actions">
        <AppButton variant="plain" @click="$emit('latest')">返回最新消息</AppButton>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { ref } from "vue";

  import AppIcon from "@/components/AppIcon.vue";
  import AppButton from "@/components/AppButton.vue";
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
    hasMore: boolean;
    hasNewer: boolean;
    loadingOlder: boolean;
  }>();
  const emit = defineEmits<{
    reply: [message: RoomMessage];
    reference: [messageId: string];
    select: [messageId: string];
    showDetails: [];
    loadOlder: [];
    latest: [];
  }>();

  const timeline = ref<HTMLElement>();
  let previousScroll = 0;
  let previousHeight = 0;

  function rememberScroll(): void {
    previousScroll = timeline.value?.scrollTop ?? 0;
    previousHeight = timeline.value?.scrollHeight ?? 0;
  }

  function restoreScroll(): void {
    if (timeline.value)
      timeline.value.scrollTop = previousScroll + timeline.value.scrollHeight - previousHeight;
  }

  function findMember(memberId: string | null): Member | undefined {
    return props.members.find((member) => member.id === memberId);
  }

  function memberName(memberId: string): string {
    return findMember(memberId)?.name ?? memberId;
  }

  function showDetails(messageId: string): void {
    emit("select", messageId);
    emit("showDetails");
  }

  function deliverySummary(message: RoomMessage): string {
    const labels = {
      pending: "待提交",
      submitting: "提交中",
      queued: "已入队",
      received: "已进入会话",
      rejected: "已拒绝",
      unknown: "结果未知",
    } as const;
    return Object.entries(labels)
      .map(([status, label]) => {
        const count = message.deliveries.filter((delivery) => delivery.status === status).length;
        return count ? `${count} ${label}` : "";
      })
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
    return message ? `#${message.seq} · ${memberName(message.senderId)}` : messageId;
  }

  function scrollToEnd(): void {
    if (timeline.value) {
      timeline.value.scrollTop = timeline.value.scrollHeight;
    }
  }

  function scrollToMessage(messageId: string): void {
    const index = props.messages.findIndex((message) => message.id === messageId);
    const article = timeline.value?.querySelectorAll<HTMLElement>("article")[index];
    article?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    article?.focus({ preventScroll: true });
  }

  defineExpose({ scrollToEnd, scrollToMessage, rememberScroll, restoreScroll });
</script>
