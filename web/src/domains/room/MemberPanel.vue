<template>
  <section class="sidebar-members" aria-label="聊天室成员">
    <header class="room-panel-heading sidebar-section-heading">
      <h2 class="room-panel-title">成员</h2>
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
    </header>

    <div class="sidebar-member-list">
      <div
        v-for="member in members"
        :key="member.id"
        class="sidebar-node"
        :class="{ 'is-active': selectedMemberId === member.id }"
      >
        <button
          type="button"
          class="member-row sidebar-member"
          :aria-label="`筛选成员：${member.name}`"
          :aria-pressed="selectedMemberId === member.id"
          @click="$emit('select', member.id)"
        >
          <MemberIdentity :member="member" />
          <span
            v-if="member.kind === 'agent'"
            class="member-row-status sidebar-member-status"
            :data-presence="member.presence"
          >
            {{ presenceLabel[member.presence] }}
          </span>
        </button>
        <div v-if="member.kind === 'agent'" class="sidebar-node-actions">
          <button
            type="button"
            :aria-label="`编辑成员：${member.name}`"
            :disabled="busy"
            @click="$emit('editMember', member)"
          >
            编辑
          </button>
          <button
            type="button"
            :aria-label="`删除成员：${member.name}`"
            :disabled="busy"
            @click="$emit('deleteMember', member)"
          >
            删除
          </button>
        </div>
      </div>
      <p v-if="!members.length" class="sidebar-members-empty">暂无成员</p>
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
    selectedMemberId?: string;
  }>();
  defineEmits<{
    addMember: [];
    select: [memberId: string];
    editMember: [member: Member];
    deleteMember: [member: Member];
  }>();

  const members = computed(() =>
    props.snapshot.members
      .filter((member) => !member.deletedAt)
      .toSorted((left, right) => Number(right.kind === "human") - Number(left.kind === "human")),
  );
  const presenceLabel = {
    available: "空闲",
    busy: "忙碌",
    offline: "离线",
    unknown: "接入未确认",
  };
</script>
