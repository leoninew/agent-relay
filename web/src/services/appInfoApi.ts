import { apiClient } from "@/services/api";

export async function fetchAppInfo(): Promise<{ version: string | null }> {
  const { data } = await apiClient.get<{ version: string | null }>("/api/app", { timeout: 5000 });
  return data;
}
