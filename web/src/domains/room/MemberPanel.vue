<template>
  <RoomSidebarSection
    title="成员"
    action-label="添加成员"
    aria-label="聊天室成员"
    :busy="busy"
    @create="$emit('addMember')"
  >
    <div class="sidebar-list">
      <div class="sidebar-node sidebar-node-fixed">
        <button
          type="button"
          class="sidebar-list-item"
          :class="{ 'is-active': selectedMemberId === undefined }"
          :aria-pressed="selectedMemberId === undefined"
          aria-label="筛选成员：全部成员"
          @click="$emit('select', undefined)"
        >
          <span class="member-identity">
            <AppIcon name="at" class="member-marker" />
            <span class="member-name">全部成员</span>
          </span>
        </button>
      </div>
      <div v-if="humanMember" class="sidebar-node sidebar-node-fixed">
        <button
          type="button"
          class="sidebar-list-item"
          :class="{ 'is-active': selectedMemberId === humanMember.id }"
          :aria-label="`筛选成员：${humanMember.name}`"
          :aria-pressed="selectedMemberId === humanMember.id"
          @click="$emit('select', humanMember.id)"
        >
          <MemberIdentity :member="humanMember" />
        </button>
      </div>
      <VueDraggable
        v-model="members"
        class="sidebar-sortable-list"
        draggable=".sidebar-node"
        handle=".sidebar-drag-handle"
        ghost-class="sidebar-drag-ghost"
        chosen-class="sidebar-drag-chosen"
        :animation="150"
        :disabled="busy"
      >
        <div v-for="member in members" :key="member.id" class="sidebar-node">
          <button
            type="button"
            class="sidebar-drag-handle"
            :aria-label="`调整成员顺序：${member.name}`"
            title="拖动排序，也可使用上下方向键"
            :disabled="busy || members.length < 2"
            @keydown.up.prevent="moveMember(member.id, -1)"
            @keydown.down.prevent="moveMember(member.id, 1)"
          >
            <AppIcon name="grip" />
          </button>
          <button
            type="button"
            class="sidebar-list-item"
            :class="{ 'is-active': selectedMemberId === member.id }"
            :aria-label="`筛选成员：${member.name}`"
            :aria-pressed="selectedMemberId === member.id"
            @click="$emit('select', member.id)"
          >
            <MemberIdentity
              :member="member"
              :session-name="memberSessionName(member, snapshot.members, snapshot.sessions)"
            />
            <span
              v-if="member.kind === 'agent'"
              class="sidebar-item-meta sidebar-member-status"
              :data-presence="member.presence"
            >
              {{ presenceLabel[member.presence] }}
            </span>
          </button>
        </div>
      </VueDraggable>
      <p v-if="!humanMember && !members.length" class="sidebar-members-empty">暂无成员</p>
    </div>
  </RoomSidebarSection>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { VueDraggable } from "vue-draggable-plus";

  import AppIcon from "@/components/AppIcon.vue";
  import MemberIdentity from "@/domains/room/MemberIdentity.vue";
  import RoomSidebarSection from "@/domains/room/RoomSidebarSection.vue";
  import { memberSessionName } from "@/domains/room/memberSessionName";
  import { useSidebarOrder } from "@/domains/room/useSidebarOrder";
  import type { RoomSnapshot } from "@/services/roomApi";

  const props = defineProps<{
    snapshot: RoomSnapshot;
    busy: boolean;
    selectedMemberId?: string;
  }>();
  defineEmits<{
    addMember: [];
    select: [memberId: string | undefined];
  }>();

  const humanMember = computed(() =>
    props.snapshot.members.find((member) => member.kind === "human" && !member.deletedAt),
  );
  const { orderedItems: members, moveItem: moveMember } = useSidebarOrder(
    () => props.snapshot.room.id,
    "members",
    () => props.snapshot.members.filter((member) => member.kind === "agent" && !member.deletedAt),
  );
  const presenceLabel = {
    available: "空闲",
    busy: "忙碌",
    offline: "离线",
    unknown: "接入未确认",
  };
</script>
