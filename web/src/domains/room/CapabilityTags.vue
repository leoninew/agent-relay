<template>
  <ul v-if="capabilities?.length" class="capability-tags" aria-label="消息能力引用">
    <li v-for="reference in capabilities" :key="`${reference.type}:${reference.id}`">
      <AppIcon :name="reference.type === 'skill' ? 'skill' : 'plug'" />
      <span :title="reference.name">{{ reference.name }}</span>
      <button
        v-if="removable"
        type="button"
        class="icon-button"
        :aria-label="`移除能力 ${reference.name}`"
        :disabled="disabled"
        @click.stop="$emit('remove', reference)"
      >
        <AppIcon name="close" />
      </button>
    </li>
  </ul>
</template>

<script setup lang="ts">
  import AppIcon from "@/components/AppIcon.vue";
  import type { CapabilityReference } from "@/services/roomApi";

  defineProps<{
    capabilities?: CapabilityReference[];
    removable?: boolean;
    disabled?: boolean;
  }>();
  defineEmits<{ remove: [reference: CapabilityReference] }>();
</script>

<style scoped>
  .capability-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 6px 0;
    padding: 0;
    list-style: none;
  }
  li {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    max-width: 100%;
    padding: 2px 6px;
    border: 1px solid hsl(var(--border));
    border-radius: 4px;
    color: hsl(var(--muted-foreground));
    background: hsl(var(--muted));
  }
  li > svg {
    flex: none;
    width: 14px;
    height: 14px;
  }
  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  button {
    width: 20px;
    height: 20px;
    padding: 2px;
  }
</style>
