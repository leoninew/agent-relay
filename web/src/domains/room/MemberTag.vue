<template>
  <span class="member-tag member-color" :data-member="member.id">
    <MemberIdentity :member="member" />
  </span>
</template>

<script setup lang="ts">
  import MemberIdentity from "@/domains/room/MemberIdentity.vue";
  import type { Member } from "@/services/roomApi";

  defineProps<{ member: Pick<Member, "id" | "name"> }>();
</script>
