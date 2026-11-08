<template>
  <AppDialog
    :open="!!member"
    title="编辑成员"
    :busy="saving || topicSaving"
    @close="$emit('close')"
  >
    <form class="setup-form" novalidate @submit.prevent="submit">
      <div class="setup-form-content">
        <div class="setup-field">
          <label id="edit-member-session-label">关联会话</label>
          <div class="session-options" role="group" aria-labelledby="edit-member-session-label">
            <div class="session-option-row">
              <div class="session-option linked-session-card">
                <span class="session-option-label">
                  <strong :title="linkedSession?.name">
                    {{ linkedSession?.name ?? "会话名称不可用" }}
                  </strong>
                  <span :title="member?.sessionId">{{ member?.sessionId }}</span>
                </span>
              </div>
              <span v-if="member" class="session-option-meta">
                {{ presenceLabel[member.presence] }}
              </span>
            </div>
          </div>
        </div>
        <div class="setup-field">
          <label for="edit-member-name">成员名称 <span class="required-mark">*</span></label>
          <AppInput
            id="edit-member-name"
            v-model="name"
            :maxlength="80"
            :disabled="saving"
            :invalid="!!errors.name"
            clear-label="清空名称"
            aria-describedby="edit-member-name-error"
            autocomplete="off"
          />
          <p v-if="errors.name" id="edit-member-name-error" class="field-error">
            {{ errors.name }}
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
        <p v-if="error" class="field-error" role="alert">{{ error }}</p>
      </div>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="saving || topicSaving" @click="$emit('close')">
          取消
        </AppButton>
        <AppButton type="submit" :loading="saving" loading-label="保存中…" :disabled="topicSaving">
          保存成员
        </AppButton>
      </footer>
    </form>
  </AppDialog>
</template>

<script setup lang="ts">
  import { ref, watch } from "vue";

  import AppButton from "@/components/AppButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import AppInput from "@/components/AppInput.vue";
  import MemberTopicsField from "@/domains/room/MemberTopicsField.vue";
  import type { Member, Session, Topic, UpdateMember } from "@/services/roomApi";

  import "./member-session.css";

  const props = defineProps<{
    member?: Member;
    linkedSession?: Pick<Session, "id" | "name">;
    topics: Topic[];
    roomId?: string;
    saving: boolean;
    error: string | null;
  }>();
  const emit = defineEmits<{
    close: [];
    save: [memberId: string, request: UpdateMember];
  }>();
  const name = ref("");
  const topicIds = ref<string[]>([]);
  const topicSaving = ref(false);
  const errors = ref<Record<string, string>>({});
  const presenceLabel = {
    available: "空闲",
    busy: "忙碌",
    offline: "离线",
    unknown: "接入未确认",
  };

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
    if (!name.value.trim()) errors.value.name = "请输入名称";
    if (Object.keys(errors.value).length) return;
    emit("save", props.member.id, { name: name.value.trim(), topicIds: [...topicIds.value] });
  }
</script>

<style scoped>
  .linked-session-card:hover {
    background: hsl(var(--card));
  }
</style>
