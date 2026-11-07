<template>
  <span
    class="member-avatar member-color"
    :data-member="member?.id ?? 'console'"
    aria-hidden="true"
  >
    {{ initials }}
  </span>
</template>

<script setup lang="ts">
  import { computed } from "vue";

  import type { Member } from "@/services/roomApi";

  const props = defineProps<{ member?: Pick<Member, "id" | "name"> }>();
  const initials = computed(() => {
    const name = props.member?.name.trim();
    return name ? Array.from(name)[0].toLocaleUpperCase() : "YOU";
  });
</script>
