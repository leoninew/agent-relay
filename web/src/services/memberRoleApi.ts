import { apiClient } from "@/services/api";

export type MemberRole = { id: string; name: string; prompt: string };
export type MemberRoleInput = Pick<MemberRole, "name" | "prompt">;

const rolesPath = "/api/member-role";

function rolePath(roleId: string): string {
  return `${rolesPath}/${encodeURIComponent(roleId)}`;
}

export async function listMemberRoles(signal?: AbortSignal): Promise<MemberRole[]> {
  const { data } = await apiClient.get<MemberRole[]>(rolesPath, { signal });
  return data;
}

export async function createMemberRole(request: MemberRoleInput): Promise<MemberRole> {
  const { data } = await apiClient.post<MemberRole>(rolesPath, request);
  return data;
}

export async function updateMemberRole(
  roleId: string,
  request: MemberRoleInput,
): Promise<MemberRole> {
  const { data } = await apiClient.patch<MemberRole>(rolePath(roleId), request);
  return data;
}

export async function deleteMemberRole(roleId: string): Promise<void> {
  await apiClient.delete(rolePath(roleId));
}
