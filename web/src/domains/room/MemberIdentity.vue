<template>
  <span class="member-identity">
    <MemberAvatar :member="member" />
    <span class="member-name">{{ member.name }}</span>
  </span>
</template>

<script setup lang="ts">
  import MemberAvatar from "@/domains/room/MemberAvatar.vue";
  import type { Member } from "@/services/roomApi";

  defineProps<{ member: Pick<Member, "id" | "name"> }>();
</script>
