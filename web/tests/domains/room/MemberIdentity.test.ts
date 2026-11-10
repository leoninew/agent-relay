import { cleanup, render, screen } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MemberIdentity from "@/domains/room/MemberIdentity.vue";
import { memberSessionName } from "@/domains/room/memberSessionName";

import { roomFixture } from "../../fixtures/room";

const tooltipStub = {
  props: ["text"],
  template: '<span><slot /><span v-if="text" role="tooltip">{{ text }}</span></span>',
};
const iconStub = {
  props: ["name"],
  template: '<span :data-icon="name" aria-hidden="true"></span>',
};

describe("MemberIdentity", () => {
  afterEach(cleanup);

  it("keeps the member alias and author styling while updating the Codex tooltip", async () => {
    const room = roomFixture();
    const member = room.members[0];
    const { container, rerender } = render(MemberIdentity, {
      props: {
        member,
        sessionName: memberSessionName(member, room.members, room.sessions),
        appearance: "author",
      },
      global: { stubs: { AppTooltip: tooltipStub, AppIcon: iconStub } },
    });
    expect(container.querySelector(".message-author")?.textContent).toBe("前端 Worker");
    expect(container.querySelector('[data-icon="at"]')).toBeTruthy();
    expect(screen.getByRole("tooltip").textContent).toBe("Codex 会话：前端会话");
    await rerender({ sessionName: "改名后的会话" });
    expect(screen.getByRole("tooltip").textContent?.trim()).toBe("Codex 会话：改名后的会话");
    expect(container.querySelector(".message-author")?.textContent).toBe("前端 Worker");
  });

  it("marks inline members with @ and identifies missing session metadata", () => {
    const room = roomFixture();
    const { container } = render(MemberIdentity, {
      props: { member: room.members[1], appearance: "text" },
      global: { stubs: { AppTooltip: tooltipStub, AppIcon: iconStub } },
    });
    expect(container.querySelector(".member-name")?.textContent).toBe("后端 Worker");
    expect(container.querySelectorAll('[data-icon="at"]')).toHaveLength(1);
    expect(screen.getByRole("tooltip").textContent).toBe("Codex 会话名称暂不可用");
  });

  it("does not offer a Codex tooltip for the fixed user", () => {
    const { container } = render(MemberIdentity, {
      props: { member: roomFixture().members[3], sessionName: "不应展示" },
      global: { stubs: { AppTooltip: tooltipStub } },
    });
    expect(container.querySelector("[tabindex]")).toBeNull();
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("resolves saved session names for deleted members in message history", () => {
    const room = roomFixture();
    const member = room.members[0];
    member.deletedAt = "2026-11-10T00:00:00Z";
    render(MemberIdentity, {
      props: { member, sessionName: memberSessionName(member, room.members, room.sessions) },
      global: { stubs: { AppTooltip: tooltipStub } },
    });
    expect(screen.getByRole("tooltip").textContent).toBe("Codex 会话：前端会话");
  });
});
