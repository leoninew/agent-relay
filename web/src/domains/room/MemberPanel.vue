<template>
  <section class="sidebar-members" aria-label="聊天室成员">
    <div class="sidebar-section-heading">
      <h2>成员</h2>
      <button
        type="button"
        class="icon-button"
        aria-label="添加成员"
        title="添加成员"
        :disabled="busy"
        @click="$emit('addMember')"
      >
        <AppIcon name="plus" />
      </button>
    </div>

    <div class="sidebar-member-list">
      <button
        v-for="member in members"
        :key="member.id"
        type="button"
        class="sidebar-member"
        :aria-label="`编辑成员：${member.name}`"
        :title="`${member.role} · ${member.activity}`"
        :disabled="busy"
        @click="$emit('editMember', member)"
      >
        <MemberIdentity :member="member" />
        <span class="sidebar-member-status" :data-presence="member.presence">
          {{ presenceLabel[member.presence] }}
        </span>
      </button>
      <p v-if="!members.length" class="sidebar-members-empty">
        {{ selectedTopicId ? "暂无成员关注此话题" : "暂无成员" }}
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { computed } from "vue";

  import AppIcon from "@/components/AppIcon.vue";
  import MemberIdentity from "@/domains/room/MemberIdentity.vue";
  import type { Member, RoomSnapshot } from "@/services/roomApi";

  const props = defineProps<{
    snapshot: RoomSnapshot;
    busy: boolean;
    selectedTopicId?: string;
  }>();
  defineEmits<{ addMember: []; editMember: [member: Member] }>();

  const members = computed(() =>
    props.snapshot.members.filter(
      (member) => !props.selectedTopicId || member.topicIds.includes(props.selectedTopicId),
    ),
  );
  const presenceLabel = { available: "可接收", busy: "忙碌", offline: "离线" };
</script>
