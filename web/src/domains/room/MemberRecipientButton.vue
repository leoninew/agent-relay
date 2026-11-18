<template>
  <button
    type="button"
    class="message-heading-action"
    :aria-label="t('timeline.selectMember', { name: member.name })"
    :disabled="disabled || member.kind !== 'agent' || Boolean(member.deletedAt)"
    @click.stop="$emit('select', member.id)"
  >
    <MemberIdentity
      :member="member"
      :session-name="sessionName"
      :appearance="appearance"
      tabindex="-1"
    />
  </button>
</template>

<script setup lang="ts">
  import { useI18n } from "vue-i18n";
  import MemberIdentity from "@/domains/room/MemberIdentity.vue";
  import type { Member } from "@/services/roomApi";

  defineProps<{
    member: Pick<Member, "id" | "name"> & Partial<Pick<Member, "kind" | "deletedAt">>;
    sessionName?: string;
    appearance?: "default" | "author" | "text";
    disabled?: boolean;
  }>();
  defineEmits<{ select: [memberId: string] }>();
  const { t } = useI18n();
</script>
