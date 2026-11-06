import { fireEvent, render, screen } from "@testing-library/vue";
import { describe, expect, it } from "vitest";

import GreetingCard from "@/components/GreetingCard.vue";

describe("GreetingCard", () => {
  it("shows a loading state", () => {
    render(GreetingCard, {
      props: { message: null, loading: true, error: null },
    });

    expect(screen.getByRole("status").textContent).toContain("Loading greeting");
  });

  it("shows a greeting message", () => {
    render(GreetingCard, {
      props: { message: "Hello, Ada!", loading: false, error: null },
    });

    expect(screen.getByText("Hello, Ada!")).toBeTruthy();
  });

  it("emits retry when the retry button is clicked", async () => {
    const result = render(GreetingCard, {
      props: { message: null, loading: false, error: "Request failed" },
    });

    await fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(result.emitted().retry).toHaveLength(1);
  });
});
