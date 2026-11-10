<template>
  <aside class="message-details" :aria-label="`${detailLabel}详情`">
    <header class="room-panel-heading message-details-heading">
      <div class="detail-heading-title">
        <h2 class="room-panel-title">{{ detailLabel }}详情</h2>
        <div v-if="topic && !topic.deletedAt" class="detail-heading-actions">
          <button
            type="button"
            class="detail-action-link"
            :disabled="busy"
            :aria-label="`编辑话题：${topic.name}`"
            @click="$emit('editTopic', topic)"
          >
            编辑
          </button>
          <button
            type="button"
            class="detail-action-link detail-delete-link"
            :disabled="busy"
            :aria-label="`删除话题：${topic.name}`"
            @click="$emit('deleteTopic', topic)"
          >
            删除
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
            :aria-label="`编辑成员：${member.name}`"
            @click="$emit('editMember', member)"
          >
            编辑
          </button>
          <button
            type="button"
            class="detail-action-link detail-delete-link"
            :disabled="busy"
            :aria-label="`删除成员：${member.name}`"
            @click="$emit('deleteMember', member)"
          >
            删除
          </button>
        </div>
      </div>
      <div class="detail-panel-actions">
        <button
          type="button"
          class="icon-button"
          :aria-label="`关闭${detailLabel}详情`"
          @click="$emit('close')"
        >
          <AppIcon name="close" />
        </button>
        <button
          type="button"
          class="icon-button detail-drawer-close"
          aria-label="收起右侧面板"
          @click="$emit('collapse')"
        >
          <AppIcon name="chevron" />
        </button>
      </div>
    </header>
    <div class="message-details-content">
      <template v-if="topic">
        <div class="detail-object-summary">
          <div class="sidebar-list-item detail-object-identity">
            <TopicIdentity :topic="topic" />
            <span class="sidebar-item-meta">{{ topic.messageCount }}</span>
          </div>
          <p v-if="topic.description" class="detail-description">{{ topic.description }}</p>
        </div>
        <section class="message-detail-section">
          <h3>成员</h3>
          <ul v-if="topicMembers.length" class="detail-members">
            <li v-for="subscriber in topicMembers" :key="subscriber.id">
              <div class="member-row">
                <MemberIdentity :member="subscriber" :session-name="sessionName(subscriber)" />
                <span
                  v-if="subscriber.kind === 'agent'"
                  class="member-row-status detail-presence"
                  :data-presence="subscriber.presence"
                >
                  {{ presenceLabel[subscriber.presence] }}
                </span>
                <span v-else class="member-row-status">用户</span>
              </div>
            </li>
          </ul>
          <p v-else class="detail-empty">暂无成员订阅</p>
        </section>
      </template>
      <template v-else-if="member">
        <div class="detail-object-summary">
          <div class="sidebar-list-item detail-object-identity">
            <MemberIdentity :member="member" :session-name="sessionName(member)" />
            <span
              v-if="member.kind === 'agent'"
              class="sidebar-item-meta sidebar-member-status"
              :data-presence="member.presence"
            >
              {{ presenceLabel[member.presence] }}
            </span>
          </div>
        </div>
        <section class="message-detail-section">
          <h3>订阅话题</h3>
          <ul v-if="memberTopics.length" class="detail-topics">
            <li v-for="topicItem in memberTopics" :key="topicItem.id">
              <span class="detail-topic"># {{ topicItem.name }}</span>
            </li>
          </ul>
          <p v-else class="detail-empty">未订阅话题</p>
        </section>
      </template>
      <template v-else-if="message">
        <section class="message-detail-section">
          <h3>话题</h3>
          <div v-if="message.topicIds.length" class="detail-topics">
            <span v-for="topicId in message.topicIds" :key="topicId" class="detail-topic">
              # {{ topics.find((topic) => topic.id === topicId)?.name ?? topicId }}
            </span>
          </div>
          <p v-else class="detail-empty">未选择话题</p>
        </section>
        <section v-if="dispatchRows.length" class="message-detail-section">
          <h3>成员</h3>
          <table class="dispatch-table" aria-label="成员">
            <thead>
              <tr>
                <th scope="col">名称</th>
                <th scope="col">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="{ member: recipient, stage, error } in dispatchRows" :key="recipient.id">
                <td>
                  <MemberIdentity :member="recipient" :session-name="sessionName(recipient)" />
                </td>
                <td>
                  <span class="delivery-stage">{{ stage ?? "-" }}</span>
                  <small v-if="error" class="dispatch-error">{{ error }}</small>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </template>
      <p v-else class="detail-empty">暂无详情</p>
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
  import { memberSessionName } from "@/domains/room/memberSessionName";
  import type { Member, RoomMessage, Session, Topic } from "@/services/roomApi";

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

  const detailLabel = computed(() => (props.topic ? "话题" : props.member ? "成员" : "消息"));

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

  const presenceLabel = {
    available: "空闲",
    busy: "忙碌",
    offline: "离线",
    unknown: "接入未确认",
  };

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
