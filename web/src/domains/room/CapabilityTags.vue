<template>
  <ul
    v-if="capabilities?.length"
    class="capability-tags"
    :aria-label="t('dialog.capabilityReferences')"
  >
    <li
      v-for="reference in capabilities"
      :key="`${reference.type}:${reference.id}`"
      :class="{ 'is-skill': reference.type === 'skill' }"
    >
      <AppIcon :name="reference.type === 'skill' ? 'skill' : 'plug'" />
      <span :title="description(reference)">{{ reference.name }}</span>
      <button
        v-if="removable"
        type="button"
        class="icon-button"
        :aria-label="t('dialog.removeCapability', { name: reference.name })"
        :disabled="disabled"
        @click.stop="$emit('remove', reference)"
      >
        <AppIcon name="close" />
      </button>
    </li>
  </ul>
</template>

<script setup lang="ts">
  import { useI18n } from "vue-i18n";
  import AppIcon from "@/components/AppIcon.vue";
  import type { CapabilityReference } from "@/services/roomApi";

  const { t } = useI18n();
  const props = withDefaults(
    defineProps<{
      capabilities?: CapabilityReference[];
      skillDescriptions?: ReadonlyMap<string, string>;
      removable?: boolean;
      disabled?: boolean;
    }>(),
    {
      capabilities: () => [],
      skillDescriptions: () => new Map(),
    },
  );
  defineEmits<{ remove: [reference: CapabilityReference] }>();
  function description(reference: CapabilityReference): string {
    return reference.type === "skill"
      ? props.skillDescriptions.get(reference.id)?.trim() || reference.name
      : reference.name;
  }
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
    max-width: 100%;
    color: hsl(var(--primary));
  }
  li.is-skill {
    cursor: help;
  }
  li:not(.is-skill) {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 6px;
    border: 1px solid hsl(var(--primary) / 0.12);
    border-radius: 4px;
    background: hsl(var(--primary) / 0.08);
  }
  li > svg {
    flex: none;
    width: 14px;
    height: 14px;
  }
  li.is-skill > svg {
    display: inline-block;
    width: 1em;
    height: 1em;
    margin-inline-end: 4px;
    vertical-align: -0.125em;
  }
  li:not(.is-skill) > span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  button {
    width: 20px;
    height: 20px;
    padding: 2px;
    color: inherit;
  }
</style>
