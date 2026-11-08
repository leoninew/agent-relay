import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { createPinia } from "pinia";
import { afterEach, describe, expect, it } from "vitest";

import MemberEditDialog from "@/domains/room/MemberEditDialog.vue";

import { roomFixture } from "../../fixtures/room";

describe("MemberEditDialog form", () => {
  afterEach(cleanup);

  function renderForm() {
    const room = roomFixture();
    return render(MemberEditDialog, {
      props: {
        member: room.members[0],
        linkedSession: room.sessions[0],
        topics: room.topics,
        roomId: room.room.id,
        saving: false,
        error: null,
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          AppDialog: {
            props: ["open", "title", "busy"],
            template: '<section v-if="open"><h2>{{ title }}</h2><slot /></section>',
          },
        },
      },
    });
  }

  it("emits an edited member with multiple subscriptions", async () => {
    const member = roomFixture().members[0];
    const { emitted } = renderForm();
    await fireEvent.click(screen.getByRole("checkbox", { name: "# 后端" }));
    await fireEvent.click(screen.getByRole("button", { name: "保存成员" }));

    expect(emitted().save).toEqual([
      [member.id, { name: member.name, topicIds: ["frontend", "backend"] }],
    ]);
  });

  it("shows the linked session name and ID when editing a member", () => {
    renderForm();
    expect(screen.getByText("前端会话")).toBeTruthy();
    expect(screen.getByText("session-frontend")).toBeTruthy();
    expect(screen.getByText("忙碌")).toBeTruthy();
  });
});
