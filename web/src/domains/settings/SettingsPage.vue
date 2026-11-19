<template>
  <section class="settings-page">
    <div class="settings-content">
      <header class="settings-heading">
        <h1>{{ t("memberRoles.title") }}</h1>
        <div class="settings-heading-actions">
          <AppButton :disabled="loading || !!loadError" @click="openEditor()">
            <template #icon><AppIcon name="plus" /></template>
            {{ t("memberRoles.add") }}
          </AppButton>
          <AppButton variant="secondary" @click="goBack">
            <template #icon><ArrowLeft :size="14" aria-hidden="true" /></template>
            {{ t("settings.back") }}
          </AppButton>
        </div>
      </header>

      <AppLoading v-if="loading" class="roles-state">{{ t("common.loading") }}</AppLoading>
      <div v-else-if="loadError" class="roles-state">
        <p role="alert" class="field-error">{{ translateMessage(loadError) }}</p>
        <AppButton variant="secondary" @click="load">{{ t("common.retry") }}</AppButton>
      </div>
      <p v-else-if="!roles.length" class="roles-state">{{ t("memberRoles.empty") }}</p>
      <table v-else class="roles-table" :aria-label="t('memberRoles.title')">
        <thead>
          <tr>
            <th scope="col" class="name-column">{{ t("memberRoles.name") }}</th>
            <th scope="col">{{ t("memberRoles.prompt") }}</th>
            <th scope="col" class="actions-column">{{ t("memberRoles.actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="role in roles" :key="role.id">
            <th scope="row">{{ role.name }}</th>
            <td>
              <span class="prompt-preview">{{ role.prompt }}</span>
            </td>
            <td>
              <div class="role-actions">
                <AppButton
                  variant="plain"
                  :aria-label="t('memberRoles.editNamed', { name: role.name })"
                  @click="openEditor(role)"
                >
                  {{ t("common.edit") }}
                </AppButton>
                <AppButton
                  variant="plain"
                  class="role-delete-action"
                  :aria-label="t('memberRoles.deleteNamed', { name: role.name })"
                  @click="openDelete(role)"
                >
                  {{ t("common.delete") }}
                </AppButton>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AppDialog
      :open="dialog?.kind === 'edit'"
      :title="t(dialog?.kind === 'edit' && dialog.role ? 'memberRoles.edit' : 'memberRoles.add')"
      :busy="busy"
      content-class="member-role-editor-dialog"
      initial-focus="#role-edit-name"
      @close="close"
    >
      <form class="setup-form" novalidate @submit.prevent="save">
        <div class="setup-form-content">
          <div class="setup-field">
            <label for="role-edit-name">
              {{ t("memberRoles.name") }} <span class="required-mark">*</span>
            </label>
            <AppInput
              id="role-edit-name"
              v-model="name"
              :clear-label="t('forms.clearName')"
              :disabled="busy"
              :invalid="!!fieldErrors.name"
              :aria-describedby="fieldErrors.name ? 'role-edit-name-error' : undefined"
              required
              autocomplete="off"
              @update:model-value="delete fieldErrors.name"
            />
            <p v-if="fieldErrors.name" id="role-edit-name-error" class="field-error" role="alert">
              {{ translateMessage(fieldErrors.name) }}
            </p>
          </div>
          <div class="setup-field">
            <label for="role-edit-prompt">
              {{ t("memberRoles.prompt") }} <span class="required-mark">*</span>
            </label>
            <AppInput
              id="role-edit-prompt"
              v-model="prompt"
              :clear-label="t('memberRoles.clearPrompt')"
              :disabled="busy"
              :invalid="!!fieldErrors.prompt"
              :aria-describedby="fieldErrors.prompt ? 'role-edit-prompt-error' : undefined"
              multiline
              rows="14"
              required
              @update:model-value="delete fieldErrors.prompt"
            />
            <p
              v-if="fieldErrors.prompt"
              id="role-edit-prompt-error"
              class="field-error"
              role="alert"
            >
              {{ translateMessage(fieldErrors.prompt) }}
            </p>
          </div>
          <p v-if="actionError" class="field-error" role="alert">
            {{ translateMessage(actionError) }}
          </p>
        </div>
        <footer class="dialog-actions">
          <AppButton variant="secondary" :disabled="busy" @click="close">{{
            t("common.cancel")
          }}</AppButton>
          <AppButton :loading="busy" :loading-label="t('settings.saving')" @click="save">
            {{ t("settings.save") }}
          </AppButton>
        </footer>
      </form>
    </AppDialog>

    <AppDialog
      :open="dialog?.kind === 'delete'"
      :title="t('memberRoles.delete')"
      :busy="busy"
      @close="close"
    >
      <div v-if="dialog?.kind === 'delete'" class="setup-form">
        <p class="delete-description">
          {{ t("memberRoles.deleteConfirm", { name: dialog.role.name }) }}
        </p>
        <p v-if="actionError" class="field-error" role="alert">
          {{ translateMessage(actionError) }}
        </p>
        <footer class="dialog-actions">
          <AppButton variant="secondary" :disabled="busy" @click="close">{{
            t("common.cancel")
          }}</AppButton>
          <AppButton
            class="delete-confirm"
            :loading="busy"
            :loading-label="t('forms.deleting')"
            @click="remove"
          >
            {{ t("forms.confirmDelete") }}
          </AppButton>
        </footer>
      </div>
    </AppDialog>
  </section>
</template>

<script setup lang="ts">
  import { ArrowLeft } from "@lucide/vue";
  import { onMounted } from "vue";
  import { useI18n } from "vue-i18n";
  import { useRouter } from "vue-router";

  import AppButton from "@/components/AppButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import AppIcon from "@/components/AppIcon.vue";
  import AppInput from "@/components/AppInput.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import { useMemberRoleSettings } from "@/domains/settings/useMemberRoleSettings";
  import { translateMessage } from "@/i18n";

  const { t } = useI18n();
  const router = useRouter();
  const {
    roles,
    loading,
    loadError,
    dialog,
    busy,
    actionError,
    name,
    prompt,
    fieldErrors,
    load,
    openEditor,
    openDelete,
    close,
    save,
    remove,
  } = useMemberRoleSettings();

  function goBack(): void {
    if (router.options.history.state.settingsFromMenu === true) {
      router.back();
      return;
    }
    void router.replace({ name: "room" });
  }

  onMounted(load);
</script>

<style scoped>
  .settings-page {
    min-height: calc(100dvh - var(--app-header-height));
    background: hsl(var(--card));
  }
  .settings-content {
    width: min(100%, 1120px);
    margin: 0 auto;
    padding: 8px 24px 40px;
  }
  .settings-heading {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    min-height: 64px;
    padding-block: 8px;
    border-bottom: 1px solid hsl(var(--border));
  }
  .settings-heading-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-inline-start: auto;
  }
  h1 {
    flex: 1 1 10rem;
    margin: 0;
    font-size: var(--font-size-title);
    line-height: var(--line-height-title);
    font-weight: 600;
  }
  .roles-state {
    margin-top: 20px;
    color: hsl(var(--muted-foreground));
  }
  .roles-state button {
    margin-top: 8px;
  }
  .roles-table {
    width: 100%;
    table-layout: fixed;
    margin-top: 12px;
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
  }
  .roles-table th,
  .roles-table td {
    border-bottom: 1px solid hsl(var(--border));
    padding: 8px;
    text-align: start;
    overflow-wrap: anywhere;
  }
  .roles-table th {
    font-weight: 500;
  }
  .roles-table thead th {
    color: hsl(var(--muted-foreground));
  }
  .name-column {
    width: 30%;
  }
  .actions-column {
    width: 116px;
  }
  .role-actions {
    display: flex;
    gap: 4px;
  }
  .role-actions button {
    min-height: 32px;
    padding-inline: 6px;
    border-radius: 4px;
  }
  .role-actions button:hover {
    background: hsl(var(--muted));
  }
  .role-delete-action {
    color: hsl(var(--destructive));
  }
  .prompt-preview {
    display: -webkit-box;
    overflow: hidden;
    white-space: pre-line;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
  .delete-description {
    overflow-wrap: anywhere;
  }
  @media (max-width: 480px) {
    .settings-content {
      padding-inline: 12px;
    }
    .roles-table th,
    .roles-table td {
      padding-inline: 4px;
    }
  }
</style>

<style>
  .app-dialog.member-role-editor-dialog {
    width: min(800px, calc(100vw - 32px));
  }
  .app-dialog.member-role-editor-dialog .app-input.is-multiline .app-input-control {
    max-height: min(640px, 55dvh);
  }
</style>
