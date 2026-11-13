<template>
  <aside class="message-details" :aria-label="detailLabel">
    <header class="room-panel-heading message-details-heading">
      <div class="detail-heading-title">
        <h2 class="room-panel-title">{{ detailLabel }}</h2>
        <div v-if="topic && !topic.deletedAt" class="detail-heading-actions">
          <button
            type="button"
            class="detail-action-link"
            :disabled="busy"
            :aria-label="t('details.editTopic', { name: topic.name })"
            @click="$emit('editTopic', topic)"
          >
            {{ t("common.edit") }}
          </button>
          <button
            type="button"
            class="detail-action-link detail-delete-link"
            :disabled="busy"
            :aria-label="t('details.deleteTopic', { name: topic.name })"
            @click="$emit('deleteTopic', topic)"
          >
            {{ t("common.delete") }}
          </button>
        </div>
        <div
          v-else-if="member?.kind === 'agent' && !member.deletedAt"
          class="detail-heading-actions"
        >
          <button
            type="button"
            class="detail-action-link"
            :disabled="busy"
            :aria-label="t('details.editMember', { name: member.name })"
            @click="$emit('editMember', member)"
          >
            {{ t("common.edit") }}
          </button>
          <button
            type="button"
            class="detail-action-link detail-delete-link"
            :disabled="busy"
            :aria-label="t('details.deleteMember', { name: member.name })"
            @click="$emit('deleteMember', member)"
          >
            {{ t("common.delete") }}
          </button>
        </div>
      </div>
      <div class="detail-panel-actions">
        <button
          type="button"
          class="icon-button"
          :aria-label="t('details.close', { details: detailLabel })"
          @click="$emit('close')"
        >
          <AppIcon name="close" />
        </button>
        <button
          type="button"
          class="icon-button detail-drawer-close"
          :aria-label="t('details.collapse')"
          @click="$emit('collapse')"
        >
          <AppIcon name="chevron" />
        </button>
      </div>
    </header>
    <div class="message-details-content">
      <template v-if="topic">
        <section class="message-detail-section detail-object-summary">
          <h3>{{ t("sidebar.topics") }}</h3>
          <dl class="detail-message-meta">
            <dt>{{ t("details.name") }}</dt>
            <dd>
              <TopicIdentity :topic="topic" />
            </dd>
            <dt>{{ t("details.description") }}</dt>
            <dd>{{ topic.description }}</dd>
          </dl>
        </section>
        <section class="message-detail-section">
          <h3>{{ t("sidebar.members") }}</h3>
          <ul v-if="topicMembers.length" class="detail-members">
            <li v-for="subscriber in topicMembers" :key="subscriber.id">
              <div class="member-row">
                <MemberIdentity :member="subscriber" :session-name="sessionName(subscriber)" />
                <span
                  v-if="subscriber.kind === 'agent'"
                  class="member-row-status detail-presence"
                  :data-presence="subscriber.presence"
                >
                  {{ t(`sidebar.${subscriber.presence}`) }}
                </span>
                <span v-else class="member-row-status">{{ t("details.user") }}</span>
              </div>
            </li>
          </ul>
          <p v-else class="detail-empty">{{ t("details.noSubscribers") }}</p>
        </section>
      </template>
      <template v-else-if="member">
        <section class="message-detail-section detail-object-summary">
          <h3>{{ t("sidebar.members") }}</h3>
          <dl class="detail-message-meta">
            <dt>{{ t("details.name") }}</dt>
            <dd>
              <MemberIdentity :member="member" :session-name="sessionName(member)" />
            </dd>
            <template v-if="member.kind === 'agent'">
              <dt>{{ t("queue.status") }}</dt>
              <dd>
                <span class="detail-presence" :data-presence="member.presence">
                  {{ t(`sidebar.${member.presence}`) }}
                </span>
              </dd>
            </template>
            <template v-if="member.sessionId">
              <dt>{{ t("details.codexSessionId") }}</dt>
              <dd class="detail-copyable-id">
                <span>{{ member.sessionId }}</span>
                <button
                  type="button"
                  class="icon-button"
                  :aria-label="t('details.copyCodexId')"
                  :title="t('details.copyCodexId')"
                  @click="copyCodexId(member.sessionId)"
                >
                  <AppIcon name="copy" />
                </button>
              </dd>
            </template>
          </dl>
        </section>
        <section class="message-detail-section">
          <h3>{{ t("sidebar.topics") }}</h3>
          <ul v-if="memberTopics.length" class="detail-topics">
            <li v-for="topicItem in memberTopics" :key="topicItem.id">
              <span class="detail-topic"># {{ topicItem.name }}</span>
            </li>
          </ul>
          <p v-else class="detail-empty">{{ t("details.noSubscriptions") }}</p>
        </section>
      </template>
      <template v-else-if="message">
        <section v-if="sender" class="message-detail-section">
          <h3>{{ t("queue.message") }}</h3>
          <dl class="detail-message-meta">
            <dt>{{ t("details.sequence") }}</dt>
            <dd>#{{ message.seq }}</dd>
            <dt>{{ t("details.sender") }}</dt>
            <dd>
              <MemberIdentity :member="sender" :session-name="sessionName(sender)" />
            </dd>
            <dt>{{ t("details.sentAt") }}</dt>
            <dd>
              <time :datetime="message.createdAt">{{ formatDateTime(message.createdAt) }}</time>
            </dd>
          </dl>
        </section>
        <section class="message-detail-section">
          <h3>{{ t("sidebar.topics") }}</h3>
          <div v-if="message.topicIds.length" class="detail-topics">
            <span v-for="topicId in message.topicIds" :key="topicId" class="detail-topic">
              # {{ topics.find((topic) => topic.id === topicId)?.name ?? topicId }}
            </span>
          </div>
          <p v-else class="detail-empty">{{ t("details.noTopics") }}</p>
        </section>
        <section v-if="dispatchRows.length" class="message-detail-section">
          <h3>{{ t("sidebar.members") }}</h3>
          <table class="dispatch-table" :aria-label="t('sidebar.members')">
            <thead>
              <tr>
                <th scope="col">{{ t("details.name") }}</th>
                <th scope="col">{{ t("queue.status") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="{ member: recipient, stage, error } in dispatchRows" :key="recipient.id">
                <td>
                  <MemberIdentity :member="recipient" :session-name="sessionName(recipient)" />
                </td>
                <td>
                  <span class="delivery-stage">{{ stage ? t(`delivery.${stage}`) : "-" }}</span>
                  <small v-if="error" class="dispatch-error">
                    {{ t("delivery.diagnostic") }}: {{ error }}
                  </small>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </template>
      <p v-else class="detail-empty">{{ t("details.empty") }}</p>
      <slot name="queue" />
    </div>
  </aside>
</template>

<script setup lang="ts">
  import { computed } from "vue";

  import AppIcon from "@/components/AppIcon.vue";
  import MemberIdentity from "@/domains/room/MemberIdentity.vue";
  import TopicIdentity from "@/domains/room/TopicIdentity.vue";
  import { deliveryStage } from "@/domains/room/deliveryStage";
  import { useI18n } from "vue-i18n";
  import { memberSessionName } from "@/domains/room/memberSessionName";
  import type { Member, RoomMessage, Session, Topic } from "@/services/roomApi";
  import { useToastsStore } from "@/stores/toasts";
  import { formatDateTime } from "@/utils/time";

  const props = withDefaults(
    defineProps<{
      message?: RoomMessage;
      topic?: Topic;
      member?: Member;
      topics: Topic[];
      members: Member[];
      sessions: Session[];
      busy?: boolean;
    }>(),
    { message: undefined, topic: undefined, member: undefined, busy: false },
  );
  const { t } = useI18n();
  const toasts = useToastsStore();
  defineEmits<{
    close: [];
    collapse: [];
    editTopic: [topic: Topic];
    deleteTopic: [topic: Topic];
    editMember: [member: Member];
    deleteMember: [member: Member];
  }>();

  function sessionName(member: Pick<Member, "id">): string | undefined {
    return memberSessionName(member, props.members, props.sessions);
  }

  async function copyCodexId(sessionId: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(sessionId);
      toasts.success({ key: "notice.codexIdCopied" });
    } catch {
      toasts.error({ key: "notice.codexIdCopyFailed" });
    }
  }

  const detailLabel = computed(() =>
    t(props.topic ? "details.topic" : props.member ? "details.member" : "details.message"),
  );

  const sender = computed(() => {
    const message = props.message;
    return message
      ? (props.members.find((member) => member.id === message.senderId) ?? {
          id: message.senderId,
          name: message.senderName || message.senderId,
        })
      : undefined;
  });

  const topicMembers = computed(() => {
    const topic = props.topic;
    return topic
      ? props.members.filter(
          (subscriber) => !subscriber.deletedAt && subscriber.topicIds.includes(topic.id),
        )
      : [];
  });

  const memberTopics = computed(() => {
    const member = props.member;
    return member
      ? member.topicIds
          .map((topicId) => props.topics.find((topic) => topic.id === topicId && !topic.deletedAt))
          .filter((topic): topic is Topic => Boolean(topic))
      : [];
  });

  function resolveMember(memberId: string): Pick<Member, "id" | "name"> {
    return (
      props.members.find((member) => member.id === memberId) ?? { id: memberId, name: memberId }
    );
  }

  const recipients = computed(
    () =>
      props.message?.recipientIds
        .filter(
          (id) => !props.members.some((member) => member.id === id && member.kind === "human"),
        )
        .map(resolveMember) ?? [],
  );
  const dispatchRows = computed(() =>
    recipients.value.map((member) => {
      const delivery = props.message?.deliveries.find(
        (delivery) => delivery.targetMemberId === member.id,
      );
      const status = delivery?.status;
      return {
        member,
        stage: delivery ? deliveryStage([delivery]) : undefined,
        error: status === "rejected" || status === "unknown" ? delivery?.error : null,
      };
    }),
  );
</script>
