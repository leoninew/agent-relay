import type { AxiosAdapter, InternalAxiosRequestConfig } from "axios";
import { afterEach, expect, it, vi } from "vitest";

import { apiClient } from "@/services/api";
import {
  createMemberRole,
  deleteMemberRole,
  listMemberRoles,
  updateMemberRole,
} from "@/services/memberRoleApi";

const originalAdapter = apiClient.defaults.adapter;

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter;
});

it("uses the site role endpoints and preserves the complete prompt", async () => {
  const input = { name: "Reviewer", prompt: "Read\nReview" };
  const role = { id: "role/one", ...input };
  const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
    config,
    data: config.method === "get" ? [role] : config.method === "delete" ? "" : role,
    headers: config.method === "delete" ? {} : { "content-type": "application/json" },
    status: config.method === "delete" ? 204 : config.method === "post" ? 201 : 200,
    statusText: "OK",
  }));
  apiClient.defaults.adapter = adapter as AxiosAdapter;

  await expect(listMemberRoles()).resolves.toEqual([role]);
  await expect(createMemberRole(input)).resolves.toEqual(role);
  await expect(updateMemberRole(role.id, input)).resolves.toEqual(role);
  await expect(deleteMemberRole(role.id)).resolves.toBeUndefined();
  expect(adapter.mock.calls.map(([config]) => [config.method, config.url])).toEqual([
    ["get", "/api/member-role"],
    ["post", "/api/member-role"],
    ["patch", "/api/member-role/role%2Fone"],
    ["delete", "/api/member-role/role%2Fone"],
  ]);
  expect(adapter.mock.calls[1][0].data).toBe(JSON.stringify(input));
  expect(adapter.mock.calls[2][0].data).toBe(JSON.stringify(input));
});
