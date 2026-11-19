import { beforeEach, expect, it, vi } from "vitest";

import { memberRoleNotFound, useMemberRolePicker } from "@/domains/room/useMemberRolePicker";
import { listMemberRoles, type MemberRole } from "@/services/memberRoleApi";

vi.mock("@/services/memberRoleApi");

const reviewer = { id: "role-reviewer", name: "Reviewer", prompt: "Review" };
const developer = { id: "role-developer", name: "Developer", prompt: "Implement" };
const draft = { name: "Member", sessionId: "thread", topicIds: ["backend"] };

beforeEach(() => {
  vi.mocked(listMemberRoles).mockReset().mockResolvedValue([reviewer, developer]);
});

it("keeps the role optional and sends only the chosen identifier", async () => {
  const picker = useMemberRolePicker();
  const loading = picker.load();
  expect(picker.withRole(draft)).toEqual(draft);
  await loading;
  picker.select(reviewer.id);
  expect(picker.withRole(draft)).toEqual({ ...draft, roleId: reviewer.id });
  picker.select("");
  expect(picker.withRole(draft)).toEqual(draft);
});

it("allows the original submission when the catalog is empty or unavailable", async () => {
  const picker = useMemberRolePicker();
  vi.mocked(listMemberRoles).mockResolvedValueOnce([]);
  await picker.load();
  expect(picker.roles.value).toEqual([]);
  expect(picker.withRole(draft)).toEqual(draft);
  vi.mocked(listMemberRoles).mockRejectedValueOnce(new Error("offline"));
  await picker.load();
  expect(picker.loadError.value?.key).toBe("memberRoles.loadFailed");
  expect(picker.withRole(draft)).toEqual(draft);
  await picker.load();
  expect(picker.roles.value).toEqual([reviewer, developer]);
  expect(picker.loadError.value).toBeNull();
});

it("keeps other fields when a deleted role must be replaced or cleared", async () => {
  const picker = useMemberRolePicker();
  await picker.load();
  picker.select(reviewer.id);
  const error = { key: memberRoleNotFound, requestId: "test-request" };
  vi.mocked(listMemberRoles).mockResolvedValue([developer]);
  await picker.reject(error);
  expect(picker.rejected.value).toEqual({ id: reviewer.id, name: reviewer.name, error });
  expect(picker.roles.value).toEqual([developer]);
  expect(picker.withRole(draft)).toBeUndefined();
  picker.select(developer.id);
  expect(picker.rejected.value).toBeUndefined();
  expect(picker.withRole(draft)).toEqual({ ...draft, roleId: developer.id });
  picker.select("");
  expect(picker.withRole(draft)).toEqual(draft);
});

it("discards an in-flight catalog and selection when reset", async () => {
  const picker = useMemberRolePicker();
  let finish: (roles: MemberRole[]) => void = () => undefined;
  vi.mocked(listMemberRoles).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const pending = picker.load();
  const signal = vi.mocked(listMemberRoles).mock.calls[0][0];
  picker.select(reviewer.id);
  picker.reset();
  finish([reviewer]);
  await pending;
  expect(signal?.aborted).toBe(true);
  expect(picker.roles.value).toEqual([]);
  expect(picker.withRole(draft)).toEqual(draft);
});
