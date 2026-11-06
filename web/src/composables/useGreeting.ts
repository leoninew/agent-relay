import { ref } from "vue";

import { ApiClientError } from "@/services/api";
import type { GreetingResponse } from "@/services/greetingApi";
import { fetchGreeting } from "@/services/greetingApi";

export type GreetingState = {
  data: GreetingResponse | null;
  error: string | null;
  loading: boolean;
};

export function useGreeting() {
  const data = ref<GreetingResponse | null>(null);
  const error = ref<string | null>(null);
  const loading = ref(false);
  let requestId = 0;

  async function load(name: string): Promise<void> {
    const currentRequest = ++requestId;
    loading.value = true;
    error.value = null;

    try {
      const result = await fetchGreeting(name);
      if (currentRequest === requestId) {
        data.value = result;
      }
    } catch (caught) {
      if (currentRequest === requestId) {
        data.value = null;
        error.value = errorMessage(caught);
      }
    } finally {
      if (currentRequest === requestId) {
        loading.value = false;
      }
    }
  }

  return { data, error, loading, load };
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiClientError) {
    return caught.message;
  }
  return caught instanceof Error ? caught.message : "Request failed";
}
