import { ref } from "vue";

import type { MessageDescriptor } from "@/i18n";
import { describeApiError } from "@/services/api";
import { listMemberRoles, type MemberRole } from "@/services/memberRoleApi";
import type { CreateMember } from "@/services/roomApi";

export const memberRoleNotFound = "errors.member_role_not_found";

export function useMemberRolePicker() {
  const roles = ref<MemberRole[]>([]);
  const roleId = ref("");
  const loading = ref(false);
  const loadError = ref<MessageDescriptor | null>(null);
  const rejected = ref<{ id: string; name: string; error: MessageDescriptor }>();
  let controller: AbortController | undefined;

  function reset(): void {
    controller?.abort();
    controller = undefined;
    roles.value = [];
    roleId.value = "";
    rejected.value = undefined;
    loading.value = false;
    loadError.value = null;
  }

  async function load(): Promise<void> {
    controller?.abort();
    const current = new AbortController();
    controller = current;
    loading.value = true;
    loadError.value = null;
    try {
      const result = await listMemberRoles(current.signal);
      if (controller === current) {
        roles.value = result.filter((role) => role.id !== rejected.value?.id);
      }
    } catch (caught) {
      if (controller === current) {
        loadError.value = describeApiError(caught, "memberRoles.loadFailed");
      }
    } finally {
      if (controller === current) {
        controller = undefined;
        loading.value = false;
      }
    }
  }

  function select(id: string): void {
    roleId.value = id;
    if (id !== rejected.value?.id) {
      rejected.value = undefined;
    }
  }

  async function reject(error: MessageDescriptor): Promise<void> {
    const id = roleId.value;
    if (!id) {
      return;
    }
    const name = roles.value.find((role) => role.id === id)?.name ?? id;
    rejected.value = { id, name, error };
    roles.value = roles.value.filter((role) => role.id !== id);
    await load();
  }

  function withRole(request: Omit<CreateMember, "roleId">): CreateMember | undefined {
    if (rejected.value) {
      return undefined;
    }
    return roleId.value ? { ...request, roleId: roleId.value } : request;
  }

  return { roles, roleId, loading, loadError, rejected, load, reset, select, reject, withRole };
}
