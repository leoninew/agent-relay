<template>
  <div ref="timeline" class="message-timeline" :aria-busy="loading" aria-label="消息时间线">
    <AppLoading v-if="loading" class="timeline-placeholder">正在加载讨论…</AppLoading>
    <div v-else-if="unavailable" class="timeline-placeholder">暂时无法加载消息，请重试。</div>
    <div v-else-if="messages.length === 0" class="timeline-placeholder">
      <span class="empty-icon"><AppIcon name="chat" /></span>
      <h3>{{ searching ? "未找到匹配的消息" : "暂无消息" }}</h3>
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
      <template v-for="({ message, status }, index) in rows" :key="message.id">
        <div v-if="startsNewDay(index)" class="timeline-date">
          <span>{{ formatDate(message.createdAt) }}</span>
        </div>
        <div v-if="startsNewMinute(index)" class="timeline-time">
          <time :datetime="message.createdAt">{{ formatMinute(message.createdAt) }}</time>
        </div>
        <article
          class="message"
          :class="{
            'is-selected': message.id === selectedMessageId,
            'is-user': findMember(message.senderId)?.kind === 'human',
          }"
          tabindex="0"
          :aria-label="`${memberName(message.senderId)}的消息`"
          @click="$emit('select', message.id)"
          @keydown.enter.self.prevent="$emit('select', message.id)"
          @keydown.space.self.prevent="$emit('select', message.id)"
        >
          <div class="message-body">
            <div class="message-main">
              <div class="message-heading">
                <div class="message-heading-main">
                  <button
                    type="button"
                    class="message-heading-action"
                    :aria-label="`勾选成员：${memberName(message.senderId)}`"
                    :disabled="!isRoutableMember(message.senderId)"
                    @click.stop="$emit('addMember', message.senderId)"
                  >
                    <MemberIdentity
                      :member="identityMember(message.senderId)"
                      :session-name="sessionName(message.senderId)"
                      appearance="author"
                    />
                  </button>
                  <div v-if="message.topicIds.length" class="message-topics" aria-label="所属话题">
                    <button
                      v-for="topicId in message.topicIds"
                      :key="topicId"
                      type="button"
                      class="message-heading-action topic-chip"
                      :data-topic="topicId"
                      :aria-label="`勾选话题：${findTopic(topicId)?.name ?? topicId}`"
                      :disabled="findTopic(topicId)?.deletedAt !== null"
                      @click.stop="$emit('addTopic', topicId)"
                    >
                      # {{ findTopic(topicId)?.name ?? topicId }}
                    </button>
                  </div>
                  <div
                    v-if="message.mentionedMemberIds.length"
                    class="message-mentions"
                    aria-label="@ 成员"
                  >
                    <button
                      v-for="memberId in message.mentionedMemberIds"
                      :key="memberId"
                      type="button"
                      class="message-heading-action mention-chip"
                      :aria-label="`勾选成员：${memberName(memberId)}`"
                      :disabled="!isRoutableMember(memberId)"
                      @click.stop="$emit('addMember', memberId)"
                    >
                      <MemberIdentity
                        :member="identityMember(memberId)"
                        :session-name="sessionName(memberId)"
                        appearance="text"
                      />
                    </button>
                  </div>
                </div>
                <div
                  v-if="status"
                  class="message-delivery-summary"
                  :class="{ 'is-complete': status.label === '已接收' }"
                  aria-label="分发状态"
                >
                  <span class="message-delivery-status" :data-tone="status.tone">
                    {{ status.label }}
                  </span>
                </div>
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
              </p>
            </div>
            <div class="message-actions">
              <button
                type="button"
                class="message-copy icon-button"
                :aria-label="`复制消息 #${message.seq} 正文`"
                title="复制正文"
                @click.stop="copyMessage(message)"
              >
                <AppIcon name="copy" />
              </button>
              <button
                type="button"
                class="message-reply icon-button"
                :aria-label="`引用消息 #${message.seq}`"
                title="引用回复"
                @click.stop="$emit('reply', message)"
              >
                <AppIcon name="reply" />
              </button>
              <button
                type="button"
                class="message-details icon-button"
                :aria-label="`查看消息 #${message.seq} 详情`"
                :aria-expanded="message.id === selectedMessageId && detailsOpen"
                title="查看详情"
                @click.stop="$emit('select', message.id)"
              >
                <AppIcon name="info" />
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
  import { computed, ref } from "vue";

  import AppIcon from "@/components/AppIcon.vue";
  import AppButton from "@/components/AppButton.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import MemberIdentity from "@/domains/room/MemberIdentity.vue";
  import { deliveryStage } from "@/domains/room/deliveryStage";
  import { memberSessionName } from "@/domains/room/memberSessionName";
  import type { Member, RoomMessage, Session, Topic } from "@/services/roomApi";
  import { useToastsStore } from "@/stores/toasts";
  import { formatDate, formatMinute } from "@/utils/time";

  const props = withDefaults(
    defineProps<{
      messages: RoomMessage[];
      members: Member[];
      sessions: Session[];
      topics: Topic[];
      selectedMessageId?: string;
      detailsOpen: boolean;
      loading: boolean;
      searching?: boolean;
      unavailable: boolean;
      hasMore: boolean;
      hasNewer: boolean;
      loadingOlder: boolean;
    }>(),
    { selectedMessageId: undefined, searching: false },
  );
  defineEmits<{
    reply: [message: RoomMessage];
    reference: [messageId: string];
    select: [messageId: string];
    addTopic: [topicId: string];
    addMember: [memberId: string];
    loadOlder: [];
    latest: [];
  }>();

  const timeline = ref<HTMLElement>();
  const toasts = useToastsStore();
  const rows = computed(() =>
    props.messages.map((message) => ({ message, status: deliverySummary(message) })),
  );
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

  function findTopic(topicId: string): Topic | undefined {
    return props.topics.find((topic) => topic.id === topicId);
  }

  function isRoutableMember(memberId: string): boolean {
    const member = findMember(memberId);
    return member?.kind === "agent" && !member.deletedAt;
  }

  function memberName(memberId: string): string {
    return findMember(memberId)?.name ?? memberId;
  }

  function identityMember(memberId: string): Pick<Member, "id" | "name"> {
    return findMember(memberId) ?? { id: memberId, name: memberId };
  }

  function sessionName(memberId: string): string | undefined {
    return memberSessionName({ id: memberId }, props.members, props.sessions);
  }

  function deliverySummary(
    message: RoomMessage,
  ): { label: string; tone: "info" | "success" | "error" | "warning" } | undefined {
    const deliveries = message.deliveries.filter((delivery) => !delivery.deletedAt);
    if (deliveries.some((delivery) => delivery.status === "rejected")) {
      return { label: "入队失败", tone: "error" };
    }
    if (deliveries.some((delivery) => delivery.status === "unknown")) {
      return { label: "入队待确认", tone: "warning" };
    }
    const stage = deliveryStage(deliveries);
    return stage ? { label: stage, tone: stage === "已接收" ? "success" : "info" } : undefined;
  }

  async function copyMessage(message: RoomMessage): Promise<void> {
    try {
      await navigator.clipboard.writeText(message.content);
      toasts.success("消息正文已复制");
    } catch {
      toasts.error("复制失败，请重试或手动复制消息正文");
    }
  }

  function startsNewDay(index: number): boolean {
    return (
      index === 0 ||
      formatDate(props.messages[index - 1].createdAt) !==
        formatDate(props.messages[index].createdAt)
    );
  }

  function startsNewMinute(index: number): boolean {
    if (index === 0) return true;
    const previousMinute = Math.floor(
      new Date(props.messages[index - 1].createdAt).getTime() / 60000,
    );
    const currentMinute = Math.floor(new Date(props.messages[index].createdAt).getTime() / 60000);
    return previousMinute !== currentMinute;
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

  function isAtEnd(): boolean {
    const element = timeline.value;
    return Boolean(element && element.scrollHeight - element.scrollTop - element.clientHeight <= 2);
  }

  function scrollToMessage(messageId: string): void {
    const index = props.messages.findIndex((message) => message.id === messageId);
    const article = timeline.value?.querySelectorAll<HTMLElement>("article")[index];
    article?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    article?.focus({ preventScroll: true });
  }

  defineExpose({ scrollToEnd, isAtEnd, scrollToMessage, rememberScroll, restoreScroll });
</script>
