import { ref } from "vue";

import { inlineSkills } from "@/domains/room/inlineSkills";
import type { MessageDescriptor } from "@/i18n";
import { ApiClientError, describeApiError } from "@/services/api";
import {
  createMemberRole,
  deleteMemberRole,
  listMemberRoles,
  updateMemberRole,
  type MemberRole,
  type MemberRoleInput,
} from "@/services/memberRoleApi";

type RoleFields = Partial<Record<keyof MemberRoleInput, MessageDescriptor>>;
type RoleDialog = { kind: "edit"; role?: MemberRole } | { kind: "delete"; role: MemberRole };

export function useMemberRoleSettings() {
  const roles = ref<MemberRole[]>([]);
  const loading = ref(false);
  const loadError = ref<MessageDescriptor | null>(null);
  const dialog = ref<RoleDialog>();
  const busy = ref(false);
  const actionError = ref<MessageDescriptor | null>(null);
  const name = ref("");
  const prompt = ref("");
  const fieldErrors = ref<RoleFields>({});

  async function load(): Promise<void> {
    if (loading.value || busy.value) {
      return;
    }
    loading.value = true;
    loadError.value = null;
    try {
      roles.value = await listMemberRoles();
    } catch (caught) {
      loadError.value = describeApiError(caught, "memberRoles.loadFailed");
    } finally {
      loading.value = false;
    }
  }

  function openEditor(role?: MemberRole): void {
    name.value = role?.name ?? "";
    prompt.value = role?.prompt ?? "";
    fieldErrors.value = {};
    actionError.value = null;
    dialog.value = { kind: "edit", role };
  }

  function openDelete(role: MemberRole): void {
    actionError.value = null;
    dialog.value = { kind: "delete", role };
  }

  function close(): void {
    if (!busy.value) {
      dialog.value = undefined;
    }
  }

  function checkInput(request: MemberRoleInput): RoleFields {
    const errors: RoleFields = {};
    if (!request.name || [...request.name].length > 80) {
      errors.name = { key: "memberRoles.invalidName" };
    }
    if (!request.prompt || [...request.prompt].length > 6000) {
      errors.prompt = { key: "memberRoles.invalidPrompt" };
    } else if (inlineSkills(request.prompt).length) {
      errors.prompt = { key: "memberRoles.noSkillLinks" };
    }
    return errors;
  }

  async function save(): Promise<void> {
    const target = dialog.value;
    if (target?.kind !== "edit" || busy.value) {
      return;
    }
    const request = { name: name.value.trim(), prompt: prompt.value.trim() };
    fieldErrors.value = checkInput(request);
    actionError.value = null;
    if (fieldErrors.value.name || fieldErrors.value.prompt) {
      return;
    }
    busy.value = true;
    try {
      const role = target.role
        ? await updateMemberRole(target.role.id, request)
        : await createMemberRole(request);
      if (target.role) {
        roles.value = roles.value.map((item) => (item.id === role.id ? role : item));
      } else {
        roles.value = [...roles.value, role];
      }
      dialog.value = undefined;
    } catch (caught) {
      const message = describeApiError(caught, "errors.save");
      if (caught instanceof ApiClientError && caught.code === "member_role_name_conflict") {
        fieldErrors.value.name = message;
      } else {
        actionError.value = message;
      }
    } finally {
      busy.value = false;
    }
  }

  async function remove(): Promise<void> {
    const target = dialog.value;
    if (target?.kind !== "delete" || busy.value) {
      return;
    }
    actionError.value = null;
    busy.value = true;
    try {
      await deleteMemberRole(target.role.id);
      roles.value = roles.value.filter((role) => role.id !== target.role.id);
      dialog.value = undefined;
    } catch (caught) {
      actionError.value = describeApiError(caught, "errors.remove");
    } finally {
      busy.value = false;
    }
  }

  return {
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
  };
}
