<template>
  <aside class="message-details" :aria-label="`${detailLabel}详情`">
    <header class="room-panel-heading message-details-heading">
      <h2 class="room-panel-title">{{ detailLabel }}详情</h2>
      <button
        type="button"
        class="icon-button"
        :aria-label="`关闭${detailLabel}详情`"
        @click="$emit('close')"
      >
        <AppIcon name="close" />
      </button>
    </header>
    <div v-if="topic" class="message-details-content">
      <div class="detail-object-summary">
        <div class="detail-summary-heading">
          <h3># {{ topic.name }}</h3>
          <time v-if="topic.createdAt" :datetime="topic.createdAt">
            {{ formatDateTime(topic.createdAt) }}
          </time>
        </div>
        <p v-if="topic.description" class="detail-description">{{ topic.description }}</p>
      </div>
      <dl class="detail-stats" aria-label="话题概览">
        <div>
          <dt>消息</dt>
          <dd>{{ topic.messageCount }}</dd>
        </div>
        <div>
          <dt>成员</dt>
          <dd>{{ topicMembers.length }}</dd>
        </div>
      </dl>
      <section class="message-detail-section">
        <h3>成员</h3>
        <ul v-if="topicMembers.length" class="detail-members">
          <li v-for="subscriber in topicMembers" :key="subscriber.id">
            <div class="member-row">
              <MemberIdentity :member="subscriber" />
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
        <p v-else>暂无成员订阅</p>
      </section>
    </div>
    <div v-else-if="member" class="message-details-content">
      <div class="detail-object-summary">
        <MemberIdentity :member="member" />
        <div class="detail-member-meta">
          <span class="detail-member-kind">{{ member.kind === "agent" ? "Agent" : "用户" }}</span>
          <span
            v-if="member.kind === 'agent'"
            class="detail-presence"
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
            <span class="topic-chip" :data-topic="topicItem.id"># {{ topicItem.name }}</span>
          </li>
        </ul>
        <p v-else>未订阅话题</p>
      </section>
    </div>
    <div v-else-if="message" class="message-details-content">
      <div class="detail-message-summary">
        <div class="detail-summary-heading">
          <MemberIdentity :member="resolveMember(message.senderId)" />
          <time :datetime="message.createdAt">{{ formatDateTime(message.createdAt) }}</time>
        </div>
        <p class="detail-message-content">{{ messagePreview }}</p>
      </div>
      <section class="message-detail-section">
        <h3>话题</h3>
        <div v-if="message.topicIds.length" class="detail-topics">
          <span
            v-for="topicId in message.topicIds"
            :key="topicId"
            class="topic-chip"
            :data-topic="topicId"
          >
            # {{ topics.find((topic) => topic.id === topicId)?.name ?? topicId }}
          </span>
        </div>
        <p v-else>未选择话题</p>
      </section>
      <section v-if="mentionedMembers.length" class="message-detail-section">
        <h3>@ 成员</h3>
        <ul class="detail-members" aria-label="@ 成员">
          <li v-for="mentionedMember in mentionedMembers" :key="mentionedMember.id">
            <div class="member-row">
              <MemberIdentity :member="mentionedMember" />
            </div>
          </li>
        </ul>
      </section>
      <section v-if="dispatchRows.length" class="message-detail-section dispatch-details">
        <h3>分发状态</h3>
        <table class="dispatch-table" aria-label="分发状态">
          <thead>
            <tr>
              <th scope="col">成员</th>
              <th scope="col">入队</th>
              <th scope="col">进入会话</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="{ member: recipient, status, error } in dispatchRows" :key="recipient.id">
              <td><MemberIdentity :member="recipient" /></td>
              <td>
                <span class="dispatch-status" :data-state="status">
                  {{ status ? enqueueLabels[status] : "—" }}
                </span>
                <small v-if="error" class="dispatch-error">{{ error }}</small>
              </td>
              <td>
                <span
                  class="dispatch-status"
                  :data-state="status === 'received' ? 'received' : undefined"
                >
                  {{ status === "received" ? "已进入" : "—" }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
    <p v-else class="message-details-empty">暂无详情</p>
  </aside>
</template>

<script setup lang="ts">
  import { computed } from "vue";

  import AppIcon from "@/components/AppIcon.vue";
  import MemberIdentity from "@/domains/room/MemberIdentity.vue";
  import type { Member, RoomMessage, Topic } from "@/services/roomApi";
  import { formatDateTime } from "@/utils/time";

  const props = withDefaults(
    defineProps<{
      message?: RoomMessage;
      topic?: Topic;
      member?: Member;
      topics: Topic[];
      members: Member[];
    }>(),
    { message: undefined, topic: undefined, member: undefined },
  );
  defineEmits<{ close: [] }>();

  const detailLabel = computed(() => (props.topic ? "话题" : props.member ? "成员" : "消息"));
  const messagePreview = computed(() => {
    const content = props.message?.content ?? "";
    const characters = Array.from(content);
    return characters.length > 50 ? `${characters.slice(0, 50).join("")}…` : content;
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

  const mentionedMembers = computed(
    () => props.message?.mentionedMemberIds.map(resolveMember) ?? [],
  );
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
      return {
        member,
        status: delivery?.status,
        error:
          delivery?.status === "rejected" || delivery?.status === "unknown" ? delivery.error : null,
      };
    }),
  );
  const enqueueLabels = {
    pending: "待提交",
    submitting: "提交中",
    queued: "已入队",
    received: "已入队",
    rejected: "已拒绝",
    unknown: "结果未知",
  };
</script>
