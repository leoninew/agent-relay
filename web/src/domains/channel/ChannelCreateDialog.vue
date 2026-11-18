<template>
  <AppDialog
    :open="open"
    :title="t('channel.create')"
    :busy="busy"
    initial-focus="#channel-name"
    @close="close"
  >
    <form class="setup-form" novalidate @submit.prevent="submit">
      <div class="setup-form-content">
        <div class="setup-field">
          <label for="channel-name">
            {{ t("channel.name") }}
            <span class="required-mark">*</span>
          </label>
          <AppInput
            id="channel-name"
            v-model="name"
            maxlength="40"
            :disabled="busy || step === 'unknown'"
            :invalid="!!nameError"
            :clear-label="t('channel.clearName')"
            :aria-describedby="nameError ? 'channel-name-error' : undefined"
            autocomplete="off"
          />
          <p v-if="nameError" id="channel-name-error" class="field-error">
            {{ t("validation.name") }}
          </p>
        </div>
        <div class="setup-field">
          <label for="channel-description">{{ t("channel.description") }}</label>
          <AppInput
            id="channel-description"
            v-model="description"
            maxlength="300"
            :disabled="busy || step === 'unknown'"
            :clear-label="t('setup.clearDescription')"
          />
        </div>
        <div class="setup-field">
          <AppCheckbox
            v-model="useWorktree"
            class="channel-worktree-option"
            :disabled="busy || step === 'unknown'"
          >
            {{ t("channel.worktreeOption") }}
          </AppCheckbox>
        </div>
        <p v-if="error" class="field-error" role="alert">
          {{ t(error) }}
        </p>
        <p v-if="step === 'unknown'" class="channel-unknown" role="status">
          {{ t("channel.unknownHint") }}
          <button type="button" class="channel-link" :disabled="busy" @click="lookup()">
            {{ t("channel.lookup") }}
          </button>
        </p>
      </div>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="busy" @click="close">
          {{ t("common.cancel") }}
        </AppButton>
        <AppButton
          type="submit"
          :loading="busy"
          :loading-label="t('channel.creating')"
          :disabled="step === 'unknown'"
        >
          {{ t("channel.createAction") }}
        </AppButton>
      </footer>
    </form>
  </AppDialog>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import AppButton from "@/components/AppButton.vue";
  import AppCheckbox from "@/components/AppCheckbox.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import AppInput from "@/components/AppInput.vue";
  import { useChannelCreation } from "@/domains/channel/useChannelCreation";

  const props = defineProps<{
    open: boolean;
    roomId?: string;
    sourceChannelId?: string;
  }>();
  const emit = defineEmits<{
    close: [];
    created: [channelId: string];
  }>();
  const { t } = useI18n();
  const creation = useChannelCreation(
    () => props.roomId,
    () => props.sourceChannelId,
  );
  const {
    name,
    description,
    useWorktree,
    step,
    channelId,
    error,
    busy,
    reset,
    submit: createChannel,
    lookup: lookupChannel,
  } = creation;
  const submitted = ref(false);
  const nameError = computed(() => submitted.value && !name.value.trim());

  watch(
    () => props.open,
    (open) => {
      if (open) {
        reset();
      }
      submitted.value = false;
    },
  );

  function close(): void {
    if (busy.value) {
      return;
    }
    emit("close");
  }

  async function submit(): Promise<void> {
    if (busy.value) {
      return;
    }
    submitted.value = true;
    if (!name.value.trim()) {
      return;
    }
    if (await createChannel()) {
      emit("created", channelId.value!);
    }
  }

  async function lookup(): Promise<void> {
    if (channelId.value && (await lookupChannel(channelId.value))) {
      emit("created", channelId.value);
    }
  }
</script>

<style scoped>
  .channel-worktree-option {
    justify-self: start;
    padding: 6px 8px;
    color: hsl(var(--foreground));
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
  }
  .channel-worktree-option:focus-visible {
    outline: 2px solid hsl(var(--primary));
    outline-offset: 2px;
  }
  .channel-unknown {
    color: hsl(var(--warning));
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
  }
  .channel-link {
    color: hsl(var(--primary));
    text-decoration: underline;
  }
</style>
