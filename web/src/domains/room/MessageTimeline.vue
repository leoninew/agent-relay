<template>
  <div
    ref="timeline"
    class="message-timeline"
    :aria-busy="loading"
    :aria-label="t('timeline.label')"
  >
    <AppLoading v-if="loading" class="timeline-placeholder">{{ t("timeline.loading") }}</AppLoading>
    <div v-else-if="unavailable" class="timeline-placeholder">{{ t("timeline.unavailable") }}</div>
    <div v-else-if="messages.length === 0" class="timeline-placeholder">
      <span class="empty-icon"><AppIcon name="chat" /></span>
      <h3>{{ t(searching ? "timeline.noMatches" : "timeline.empty") }}</h3>
    </div>
    <template v-else>
      <div v-if="hasMore" class="timeline-page-actions">
        <AppButton
          variant="plain"
          :loading="loadingOlder"
          :loading-label="t('common.loading')"
          @click="$emit('loadOlder')"
        >
          {{ t("timeline.older") }}
        </AppButton>
      </div>
      <template
        v-for="({ message, status, renderedContent, remainingCapabilities }, index) in rows"
        :key="message.id"
      >
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
          :aria-label="t('timeline.authorMessage', { name: memberName(message.senderId) })"
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
                    :aria-label="t('timeline.selectMember', { name: memberName(message.senderId) })"
                    :disabled="!isRoutableMember(message.senderId)"
                    @click.stop="$emit('addMember', message.senderId)"
                  >
                    <MemberIdentity
                      :member="identityMember(message.senderId)"
                      :session-name="sessionName(message.senderId)"
                      appearance="author"
                    />
                  </button>
                  <div
                    v-if="message.topicIds.length"
                    class="message-topics"
                    :aria-label="t('timeline.topics')"
                  >
                    <button
                      v-for="topicId in message.topicIds"
                      :key="topicId"
                      type="button"
                      class="message-heading-action topic-chip"
                      :data-topic="topicId"
                      :aria-label="
                        t('timeline.selectTopic', { name: findTopic(topicId)?.name ?? topicId })
                      "
                      :disabled="findTopic(topicId)?.deletedAt !== null"
                      @click.stop="$emit('addTopic', topicId)"
                    >
                      # {{ findTopic(topicId)?.name ?? topicId }}
                    </button>
                  </div>
                  <div
                    v-if="message.mentionedMemberIds.length"
                    class="message-mentions"
                    :aria-label="t('timeline.mentions')"
                  >
                    <button
                      v-for="memberId in message.mentionedMemberIds"
                      :key="memberId"
                      type="button"
                      class="message-heading-action mention-chip"
                      :aria-label="t('timeline.selectMember', { name: memberName(memberId) })"
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
                  :class="{ 'is-complete': status.stage === 'received' }"
                  :aria-label="t('timeline.delivery')"
                >
                  <span class="message-delivery-status" :data-tone="status.tone">
                    {{ t(`delivery.${status.stage}`) }}
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
                <span>{{
                  t("timeline.reference", { reference: referenceLabel(message.replyToMessageId) })
                }}</span>
              </button>
              <CapabilityTags :capabilities="remainingCapabilities" />
              <div class="message-content" v-html="renderedContent"></div>
            </div>
            <div class="message-actions">
              <button
                type="button"
                class="message-copy icon-button"
                :aria-label="t('timeline.copyMessage', { seq: message.seq })"
                :title="t('timeline.copy')"
                @click.stop="copyMessage(message)"
              >
                <AppIcon name="copy" />
              </button>
              <button
                type="button"
                class="message-reply icon-button"
                :aria-label="t('timeline.replyMessage', { seq: message.seq })"
                :title="t('timeline.reply')"
                @click.stop="$emit('reply', message)"
              >
                <AppIcon name="reply" />
              </button>
              <button
                type="button"
                class="message-details icon-button"
                :aria-label="t('queue.viewMessage', { seq: message.seq })"
                :aria-expanded="message.id === selectedMessageId && detailsOpen"
                :title="t('timeline.view')"
                @click.stop="$emit('select', message.id)"
              >
                <AppIcon name="info" />
              </button>
            </div>
          </div>
        </article>
      </template>
      <div v-if="hasNewer" class="timeline-page-actions">
        <AppButton variant="plain" @click="$emit('latest')">{{ t("timeline.latest") }}</AppButton>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import CapabilityTags from "@/domains/room/CapabilityTags.vue";
  import { computed, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import AppIcon from "@/components/AppIcon.vue";
  import AppButton from "@/components/AppButton.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import MemberIdentity from "@/domains/room/MemberIdentity.vue";
  import { deliveryStage } from "@/domains/room/deliveryStage";
  import { memberSessionName } from "@/domains/room/memberSessionName";
  import { messageText } from "@/domains/room/inlineSkills";
  import { renderMessage } from "@/domains/room/messageMarkdown";
  import type { Member, RoomMessage, Session, Topic } from "@/services/roomApi";
  import { useToastsStore } from "@/stores/toasts";
  import { formatDate, formatMinute, sameLocalDay } from "@/utils/time";

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
  const { t } = useI18n();
  const toasts = useToastsStore();
  const rows = computed(() =>
    props.messages.map((message) => {
      const rendered = renderMessage(message.content, message.capabilities);
      return {
        message,
        status: deliverySummary(message),
        renderedContent: rendered.html,
        remainingCapabilities: rendered.remainingCapabilities,
      };
    }),
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
    return memberId === "user" ? t("member.you") : (findMember(memberId)?.name ?? memberId);
  }

  function identityMember(memberId: string): Pick<Member, "id" | "name"> {
    return findMember(memberId) ?? { id: memberId, name: memberId };
  }

  function sessionName(memberId: string): string | undefined {
    return memberSessionName({ id: memberId }, props.members, props.sessions);
  }

  function deliverySummary(message: RoomMessage):
    | {
        stage: NonNullable<ReturnType<typeof deliveryStage>>;
        tone: "info" | "success" | "error" | "warning";
      }
    | undefined {
    const deliveries = message.deliveries.filter((delivery) => !delivery.deletedAt);
    if (deliveries.some((delivery) => delivery.status === "rejected")) {
      return { stage: "failed", tone: "error" };
    }
    if (deliveries.some((delivery) => delivery.status === "unknown")) {
      return { stage: "unknown", tone: "warning" };
    }
    const stage = deliveryStage(deliveries);
    return stage ? { stage, tone: stage === "received" ? "success" : "info" } : undefined;
  }

  async function copyMessage(message: RoomMessage): Promise<void> {
    try {
      await navigator.clipboard.writeText(messageText(message.content, message.capabilities));
      toasts.success({ key: "notice.copied" });
    } catch {
      toasts.error({ key: "notice.copyFailed" });
    }
  }

  function startsNewDay(index: number): boolean {
    return (
      index === 0 ||
      !sameLocalDay(props.messages[index - 1].createdAt, props.messages[index].createdAt)
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
