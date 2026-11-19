import { beforeEach, expect, it, vi } from "vitest";

import { useMemberRoleSettings } from "@/domains/settings/useMemberRoleSettings";
import { ApiClientError } from "@/services/api";
import {
  createMemberRole,
  deleteMemberRole,
  listMemberRoles,
  updateMemberRole,
} from "@/services/memberRoleApi";

vi.mock("@/services/memberRoleApi");

const reviewer = { id: "reviewer", name: "Reviewer", prompt: "Read\nReview" };

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listMemberRoles).mockResolvedValue([reviewer]);
});

it("validates fields and saves the normalized draft using the server response", async () => {
  const model = useMemberRoleSettings();
  await model.load();
  model.openEditor();
  await model.save();
  expect(model.fieldErrors.value).toMatchObject({
    name: { key: "memberRoles.invalidName" },
    prompt: { key: "memberRoles.invalidPrompt" },
  });
  expect(createMemberRole).not.toHaveBeenCalled();

  model.name.value = "  Developer ";
  model.prompt.value = "  Plan\nBuild  ";
  const created = { id: "developer", name: "Developer", prompt: "Plan\nBuild" };
  vi.mocked(createMemberRole).mockResolvedValue(created);
  await model.save();
  expect(createMemberRole).toHaveBeenCalledWith({ name: "Developer", prompt: "Plan\nBuild" });
  expect(model.roles.value).toEqual([reviewer, created]);
  expect(model.dialog.value).toBeUndefined();
});

it("keeps the API order and updates a renamed role in place", async () => {
  const architect = { id: "architect", name: "Architect", prompt: "Plan" };
  vi.mocked(listMemberRoles).mockResolvedValue([reviewer, architect]);
  const model = useMemberRoleSettings();
  await model.load();
  expect(model.roles.value).toEqual([reviewer, architect]);

  model.openEditor(reviewer);
  model.name.value = "Verifier";
  const renamed = { ...reviewer, name: "Verifier" };
  vi.mocked(updateMemberRole).mockResolvedValue(renamed);
  await model.save();
  expect(model.roles.value).toEqual([renamed, architect]);
});

it("keeps the edit draft on a name conflict and keeps the row if deletion fails", async () => {
  const model = useMemberRoleSettings();
  await model.load();
  model.openEditor(reviewer);
  expect(model.prompt.value).toBe("Read\nReview");
  model.name.value = "Developer";
  vi.mocked(updateMemberRole).mockRejectedValue(
    new ApiClientError("Duplicate", "http_error", { code: "member_role_name_conflict" }),
  );
  await model.save();
  expect(model.fieldErrors.value.name?.key).toBe("errors.member_role_name_conflict");
  expect(model.name.value).toBe("Developer");
  expect(model.dialog.value?.kind).toBe("edit");
  expect(model.roles.value).toEqual([reviewer]);
  model.close();

  model.openDelete(reviewer);
  vi.mocked(deleteMemberRole).mockRejectedValueOnce(new Error("Network error"));
  await model.remove();
  expect(model.actionError.value?.key).toBe("errors.remove");
  expect(model.roles.value).toEqual([reviewer]);
  expect(model.dialog.value?.kind).toBe("delete");
  await model.remove();
  expect(model.roles.value).toEqual([]);
  expect(model.dialog.value).toBeUndefined();
});
