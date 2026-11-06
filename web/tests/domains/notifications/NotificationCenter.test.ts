import { fireEvent, render, screen, within } from "@testing-library/vue";
import { createPinia } from "pinia";
import { describe, expect, it } from "vitest";
import { nextTick } from "vue";

import NotificationCenter from "@/domains/notifications/NotificationCenter.vue";

describe("NotificationCenter", () => {
  it("filters the list with the Reka tabs", async () => {
    render(NotificationCenter, {
      global: {
        plugins: [createPinia()],
      },
    });

    expect(screen.getByText("Deploy finished")).toBeTruthy();
    expect(screen.getByText("Review requested")).toBeTruthy();

    const unreadTab = screen.getByRole("tab", { name: "Unread" });
    await fireEvent.mouseDown(unreadTab, { button: 0 });
    await nextTick();

    expect(unreadTab.getAttribute("data-state")).toBe("active");

    const activePanel = document.querySelector<HTMLElement>(
      '[role="tabpanel"][data-state="active"]',
    );
    expect(activePanel).toBeTruthy();

    if (!activePanel) {
      throw new Error("Expected an active notification tab panel.");
    }

    expect(within(activePanel).getByText("Deploy finished")).toBeTruthy();
    expect(within(activePanel).queryByText("Review requested")).toBeNull();
  });
});
