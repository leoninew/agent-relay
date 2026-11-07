import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

import AppInput from "@/components/AppInput.vue";

describe("AppInput", () => {
  afterEach(cleanup);

  it.each([false, true])(
    "clears its value and restores focus (multiline: %s)",
    async (multiline) => {
      const submit = vi.fn();
      render({
        components: { AppInput },
        setup: () => ({ value: ref("待清空内容"), multiline, submit }),
        template: `
        <form @submit.prevent="submit">
          <label for="test-input">测试字段</label>
          <AppInput id="test-input" v-model="value" :multiline="multiline" clear-label="清空测试字段" />
        </form>
      `,
      });

      const input = screen.getByRole("textbox", { name: "测试字段" }) as
        HTMLInputElement | HTMLTextAreaElement;
      await fireEvent.click(screen.getByRole("button", { name: "清空测试字段" }));

      expect(input.value).toBe("");
      expect(screen.queryByRole("button", { name: "清空测试字段" })).toBeNull();
      await waitFor(() => expect(document.activeElement).toBe(input));
      expect(submit).not.toHaveBeenCalled();
    },
  );

  it("preserves field errors and prevents clearing a disabled input", async () => {
    const update = vi.fn();
    render(AppInput, {
      props: {
        modelValue: "保留内容",
        clearLabel: "清空测试字段",
        disabled: true,
        invalid: true,
        "onUpdate:modelValue": update,
      },
      attrs: { "aria-label": "测试字段", "aria-describedby": "test-error" },
    });

    const input = screen.getByRole("textbox", { name: "测试字段" }) as HTMLInputElement;
    await fireEvent.click(screen.getByRole("button", { name: "清空测试字段" }));

    expect(input.disabled).toBe(true);
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(input.getAttribute("aria-describedby")).toBe("test-error");
    expect(input.value).toBe("保留内容");
    expect(update).not.toHaveBeenCalled();
  });
});
