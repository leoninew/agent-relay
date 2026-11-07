import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import AppButton from "@/components/AppButton.vue";

describe("AppButton", () => {
  afterEach(cleanup);

  it("blocks activation while submitting and becomes usable after completion", async () => {
    const onClick = vi.fn();
    const { rerender } = render(AppButton, {
      props: { loading: true, loadingLabel: "保存中…", onClick },
      slots: { default: "保存" },
    });

    const button = screen.getByRole("button", { name: "保存中…" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("aria-busy")).toBe("true");
    await fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();

    await rerender({ loading: false });
    expect(button.disabled).toBe(false);
    expect(button.hasAttribute("aria-busy")).toBe(false);
    await fireEvent.click(screen.getByRole("button", { name: "保存" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("does not submit its containing form unless explicitly configured", async () => {
    const onSubmit = vi.fn();
    render({
      components: { AppButton },
      setup: () => ({ onSubmit }),
      template: `
        <form @submit.prevent="onSubmit">
          <AppButton>取消</AppButton>
          <AppButton type="submit">保存</AppButton>
        </form>
      `,
    });

    await fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(onSubmit).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole("button", { name: "保存" }));
    expect(onSubmit).toHaveBeenCalledOnce();
  });
});
