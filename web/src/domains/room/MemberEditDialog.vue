<template>
  <AppDialog
    :open="!!member"
    :title="t('forms.editMember')"
    :busy="saving || topicSaving"
    @close="$emit('close')"
  >
    <form class="setup-form" novalidate @submit.prevent="submit">
      <div class="setup-form-content">
        <div class="setup-field">
          <label id="edit-member-session-label">{{ t("forms.linkedSession") }}</label>
          <div class="session-options" role="group" aria-labelledby="edit-member-session-label">
            <div class="session-option-row">
              <div class="session-option linked-session-card">
                <span class="session-option-label">
                  <strong :title="linkedSession?.name">
                    {{ linkedSession?.name ?? t("forms.noSessionName") }}
                  </strong>
                  <span :title="member?.sessionId">{{ member?.sessionId }}</span>
                </span>
              </div>
              <span v-if="member" class="session-option-meta">
                {{ t(`sidebar.${member.presence}`) }}
              </span>
            </div>
          </div>
        </div>
        <div class="setup-field">
          <label for="edit-member-name"
            >{{ t("forms.memberName") }} <span class="required-mark">*</span></label
          >
          <AppInput
            id="edit-member-name"
            v-model="name"
            :maxlength="80"
            :disabled="saving"
            :invalid="!!errors.name"
            :clear-label="t('forms.clearName')"
            aria-describedby="edit-member-name-error"
            autocomplete="off"
          />
          <p v-if="errors.name" id="edit-member-name-error" class="field-error">
            {{ translateMessage(errors.name) }}
          </p>
        </div>
        <MemberTopicsField
          v-model="topicIds"
          v-model:busy="topicSaving"
          id-prefix="edit-member"
          :topics="topics"
          :room-id="roomId"
          :disabled="saving"
        />
        <p v-if="error" class="field-error" role="alert">{{ translateMessage(error) }}</p>
      </div>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="saving || topicSaving" @click="$emit('close')">
          {{ t("common.cancel") }}
        </AppButton>
        <AppButton
          type="submit"
          :loading="saving"
          :loading-label="t('settings.saving')"
          :disabled="topicSaving"
        >
          {{ t("forms.saveMember") }}
        </AppButton>
      </footer>
    </form>
  </AppDialog>
</template>

<script setup lang="ts">
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";
  import { ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import AppButton from "@/components/AppButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import AppInput from "@/components/AppInput.vue";
  import MemberTopicsField from "@/domains/room/MemberTopicsField.vue";
  import type { Member, Session, Topic, UpdateMember } from "@/services/roomApi";

  import "./member-session.css";

  const { t } = useI18n();
  const props = defineProps<{
    member?: Member;
    linkedSession?: Pick<Session, "id" | "name">;
    topics: Topic[];
    roomId?: string;
    saving: boolean;
    error: MessageDescriptor | null;
  }>();
  const emit = defineEmits<{
    close: [];
    save: [memberId: string, request: UpdateMember];
  }>();
  const name = ref("");
  const topicIds = ref<string[]>([]);
  const topicSaving = ref(false);
  const errors = ref<Record<string, MessageDescriptor>>({});

  watch(
    [() => props.member?.id, () => props.roomId],
    () => {
      name.value = props.member?.name ?? "";
      topicIds.value = [...(props.member?.topicIds ?? [])];
      errors.value = {};
    },
    { immediate: true },
  );
  watch(name, (value) => {
    if (value.trim()) delete errors.value.name;
  });

  function submit(): void {
    if (!props.member || props.saving || topicSaving.value) return;
    errors.value = {};
    if (!name.value.trim()) errors.value.name = { key: "validation.name" };
    if (Object.keys(errors.value).length) return;
    emit("save", props.member.id, { name: name.value.trim(), topicIds: [...topicIds.value] });
  }
</script>

<style scoped>
  .linked-session-card:hover {
    background: hsl(var(--card));
  }
</style>
