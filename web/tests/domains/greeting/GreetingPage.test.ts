import { fireEvent, render, screen } from "@testing-library/vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

import GreetingPage from "@/domains/greeting/GreetingPage.vue";
import { fetchGreeting } from "@/services/greetingApi";

vi.mock("@/services/greetingApi", () => ({
  fetchGreeting: vi.fn(),
}));

const mockedFetchGreeting = vi.mocked(fetchGreeting);

describe("GreetingPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockedFetchGreeting.mockImplementation(async (name) => ({ text: `Hello, ${name}!` }));
  });

  it("shows greetings returned by the API service", async () => {
    render(GreetingPage);

    expect(await screen.findByText("Hello, Ada!")).toBeTruthy();

    await fireEvent.update(screen.getByRole("textbox", { name: "Name" }), "Grace");
    await fireEvent.click(screen.getByRole("button", { name: "Load greeting" }));

    expect(await screen.findByText("Hello, Grace!")).toBeTruthy();
    expect(mockedFetchGreeting).toHaveBeenLastCalledWith("Grace");
  });
});
