import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";
import { ref } from "vue";

import AppCheckbox from "@/components/AppCheckbox.vue";
import AppCheckboxGroup from "@/components/AppCheckboxGroup.vue";

describe("AppCheckboxGroup", () => {
  afterEach(cleanup);

  it("clears its selection without affecting another group and returns focus to its choices", async () => {
    render({
      components: { AppCheckbox, AppCheckboxGroup },
      setup: () => ({ topics: ref(["frontend", "backend"]), members: ref(["tester"]) }),
      template: `
        <AppCheckboxGroup v-model="topics" clear-label="清空话题" aria-label="话题">
          <AppCheckbox value="frontend">前端</AppCheckbox>
          <AppCheckbox value="backend">后端</AppCheckbox>
        </AppCheckboxGroup>
        <AppCheckboxGroup v-model="members" clear-label="清空成员" aria-label="成员">
          <AppCheckbox value="tester">测试成员</AppCheckbox>
        </AppCheckboxGroup>
      `,
    });

    await fireEvent.click(screen.getByRole("button", { name: "清空话题" }));

    const firstChoice = screen.getByRole("checkbox", { name: "前端" });
    expect(firstChoice.getAttribute("aria-checked")).toBe("false");
    expect(screen.getByRole("checkbox", { name: "后端" }).getAttribute("aria-checked")).toBe(
      "false",
    );
    expect(screen.getByRole("checkbox", { name: "测试成员" }).getAttribute("aria-checked")).toBe(
      "true",
    );
    await waitFor(() => expect(document.activeElement).toBe(firstChoice));
  });
});
