import { apiClient } from "@/services/api";

export type GreetingResponse = {
  text: string;
};

export async function fetchGreeting(name: string): Promise<GreetingResponse> {
  const { data } = await apiClient.get<GreetingResponse>("/api/greet", {
    params: { name },
  });
  return data;
}
