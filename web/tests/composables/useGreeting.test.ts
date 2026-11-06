import { beforeEach, describe, expect, it, vi } from "vitest";

import { useGreeting } from "@/composables/useGreeting";
import { fetchGreeting } from "@/services/greetingApi";

vi.mock("@/services/greetingApi", () => ({
  fetchGreeting: vi.fn(),
}));

const mockedFetchGreeting = vi.mocked(fetchGreeting);

describe("useGreeting", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("stores the greeting after a successful request", async () => {
    mockedFetchGreeting.mockResolvedValue({ text: "Hello, Ada!" });
    const greeting = useGreeting();

    const loading = greeting.load("Ada");
    expect(greeting.loading.value).toBe(true);
    await loading;

    expect(greeting.loading.value).toBe(false);
    expect(greeting.error.value).toBeNull();
    expect(greeting.data.value?.text).toBe("Hello, Ada!");
  });

  it("stores a readable error after a failed request", async () => {
    mockedFetchGreeting.mockRejectedValue(new Error("name is required"));
    const greeting = useGreeting();

    await greeting.load(" ");

    expect(greeting.loading.value).toBe(false);
    expect(greeting.data.value).toBeNull();
    expect(greeting.error.value).toBe("name is required");
  });
});
