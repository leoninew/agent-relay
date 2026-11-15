<template>
  <div v-if="member" class="routing-row" @mouseenter="retryRead">
    <span class="routing-label">{{ t("models.label") }}</span>
    <div
      class="routing-options model-options"
      role="group"
      :aria-label="t('models.choices', { name: member.name })"
    >
      <span
        v-if="loading || updating"
        role="status"
        :aria-label="t(loading ? 'models.loading' : 'models.updating')"
      >
        <AppSpinner />
      </span>
      <span v-if="catalog && !catalog.models.length" class="routing-choice">
        {{ t("models.empty") }}
      </span>
      <button
        v-for="option in visibleModels"
        :key="option.id"
        type="button"
        class="routing-choice model-choice"
        :title="option.displayName"
        :aria-pressed="option.model === catalog?.currentModel"
        :disabled="disabled || loading || updating"
        @click="select(option.model)"
      >
        {{ option.model }}
      </button>
      <PopoverRoot
        v-if="catalog && catalog.models.length > 4"
        v-model:open="moreOpen"
        :modal="false"
      >
        <PopoverTrigger as-child>
          <button
            type="button"
            class="routing-choice model-choice model-more"
            :aria-label="t('models.all')"
            :aria-expanded="moreOpen"
            :aria-pressed="selectedInMore"
            aria-haspopup="dialog"
            :disabled="disabled || loading || updating"
            @pointerenter="openMore"
            @pointerleave="scheduleClose"
            @focus="openMore"
            @blur="scheduleClose"
            @click.stop.prevent="toggleMore"
          >
            ...
          </button>
        </PopoverTrigger>
        <PopoverPortal>
          <PopoverContent
            class="model-popover"
            role="dialog"
            :aria-label="t('models.choices', { name: member.name })"
            side="top"
            align="start"
            :side-offset="6"
            :collision-padding="12"
            @pointerenter="cancelClose"
            @pointerleave="scheduleClose"
            @focusin="cancelClose"
            @focusout="scheduleClose"
            @open-auto-focus.prevent
            @close-auto-focus.prevent
          >
            <button
              v-for="option in catalog.models"
              :key="option.id"
              type="button"
              class="routing-choice model-choice"
              :title="option.displayName"
              :aria-pressed="option.model === catalog.currentModel"
              :disabled="disabled || loading || updating"
              @click="choose(option.model)"
            >
              {{ option.model }}
            </button>
          </PopoverContent>
        </PopoverPortal>
      </PopoverRoot>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onUnmounted, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";
  import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from "reka-ui";

  import AppSpinner from "@/components/AppSpinner.vue";
  import {
    modelPreview,
    selectionIsInMore,
    useSessionModels,
  } from "@/domains/room/useSessionModels";
  import type { Member } from "@/services/roomApi";

  const props = defineProps<{
    roomId: string;
    channelId: string;
    member: Member | undefined;
    disabled: boolean;
  }>();
  const { t } = useI18n();
  const { catalog, loading, updating, refresh, select } = useSessionModels(
    () => props.roomId,
    () => props.channelId,
    () => props.member,
  );
  const moreOpen = ref(false);
  let closeTimer: ReturnType<typeof setTimeout> | undefined;
  const visibleModels = computed(() => modelPreview(catalog.value?.models));
  const selectedInMore = computed(() => selectionIsInMore(catalog.value));
  watch(
    [
      () => props.roomId,
      () => props.channelId,
      () => props.member?.id,
      () => props.member?.sessionId,
      () => props.disabled,
    ],
    () => {
      cancelClose();
      moreOpen.value = false;
    },
  );

  function retryRead(): void {
    if (!props.disabled && !catalog.value && !loading.value && !updating.value) void refresh();
  }

  function cancelClose(): void {
    if (closeTimer !== undefined) clearTimeout(closeTimer);
    closeTimer = undefined;
  }

  function openMore(): void {
    cancelClose();
    moreOpen.value = true;
  }

  function scheduleClose(): void {
    cancelClose();
    closeTimer = setTimeout(() => {
      moreOpen.value = false;
      closeTimer = undefined;
    }, 160);
  }

  function toggleMore(): void {
    if (moreOpen.value) {
      cancelClose();
      moreOpen.value = false;
    } else {
      openMore();
    }
  }

  function choose(model: string): void {
    cancelClose();
    moreOpen.value = false;
    void select(model);
  }

  onUnmounted(cancelClose);
</script>
