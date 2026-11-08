<template>
  <aside class="message-details" aria-label="消息详情">
    <header class="message-details-heading">
      <h2>消息详情</h2>
      <button type="button" class="icon-button" aria-label="关闭消息详情" @click="$emit('close')">
        <AppIcon name="close" />
      </button>
    </header>
    <div v-if="message" class="message-details-content">
      <section class="message-detail-section">
        <h3>所属话题</h3>
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
          <li v-for="member in mentionedMembers" :key="member.id">
            <MemberTag :member="member" />
          </li>
        </ul>
      </section>
      <section class="message-detail-section dispatch-details">
        <h3>分发状态</h3>
        <table v-if="dispatchRows.length" class="dispatch-table">
          <thead>
            <tr>
              <th>成员</th>
              <th>投递状态</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="{
                member,
                status,
                updatedAt,
                queuedAt,
                receiptId,
                receivedItemId,
                receivedTurnId,
                note,
                error,
              } in dispatchRows"
              :key="member.id"
            >
              <td><MemberIdentity :member="member" /></td>
              <td :data-state="status">
                <span>{{ status ? enqueueLabels[status] : "—" }}</span>
                <time v-if="updatedAt" class="dispatch-time" :datetime="updatedAt">
                  {{ formatTime(updatedAt) }}
                </time>
                <small v-if="status === 'received' && queuedAt" class="dispatch-receipt">
                  入队 {{ formatTime(queuedAt) }}
                </small>
                <small v-if="note" class="dispatch-receipt">{{ note }}</small>
                <small v-if="error" class="dispatch-receipt">{{ error }}</small>
                <details
                  v-if="receiptId || receivedItemId || receivedTurnId"
                  class="dispatch-evidence"
                >
                  <summary>投递凭证<AppIcon name="chevron" /></summary>
                  <dl>
                    <template v-if="receiptId">
                      <dt>入队凭证</dt>
                      <dd>
                        <code>{{ receiptId }}</code>
                      </dd>
                    </template>
                    <template v-if="receivedItemId">
                      <dt>接收凭证</dt>
                      <dd>
                        <code>{{ receivedItemId }}</code>
                      </dd>
                    </template>
                    <template v-if="receivedTurnId">
                      <dt>Turn ID</dt>
                      <dd>
                        <code>{{ receivedTurnId }}</code>
                      </dd>
                    </template>
                  </dl>
                </details>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else>暂无分发</p>
      </section>
    </div>
    <p v-else class="message-details-empty">选择一条消息查看详情</p>
  </aside>
</template>

<script setup lang="ts">
  import { computed } from "vue";

  import AppIcon from "@/components/AppIcon.vue";
  import MemberIdentity from "@/domains/room/MemberIdentity.vue";
  import MemberTag from "@/domains/room/MemberTag.vue";
  import type { Member, RoomMessage, Topic } from "@/services/roomApi";
  import { formatTime } from "@/utils/time";

  const props = defineProps<{ message?: RoomMessage; topics: Topic[]; members: Member[] }>();
  defineEmits<{ close: [] }>();

  function resolveMember(memberId: string): Pick<Member, "id" | "name"> {
    return (
      props.members.find((member) => member.id === memberId) ?? { id: memberId, name: memberId }
    );
  }

  const mentionedMembers = computed(
    () => props.message?.mentionedMemberIds.map(resolveMember) ?? [],
  );
  const recipients = computed(() => props.message?.recipientIds.map(resolveMember) ?? []);
  const dispatchRows = computed(() =>
    recipients.value.map((member) => {
      const delivery = props.message?.deliveries.find(
        (delivery) => delivery.targetMemberId === member.id,
      );
      return {
        member,
        status: delivery?.status,
        updatedAt: delivery?.updatedAt,
        queuedAt: delivery?.queuedAt,
        receiptId: delivery?.queuedSubmissionId,
        receivedItemId: delivery?.receivedItemId,
        receivedTurnId: delivery?.receivedTurnId,
        note: delivery?.note,
        error: delivery?.error,
      };
    }),
  );
  const enqueueLabels = {
    pending: "待提交",
    submitting: "提交中",
    queued: "已入队",
    received: "已进入会话",
    rejected: "已拒绝",
    unknown: "结果未知",
  };
</script>
