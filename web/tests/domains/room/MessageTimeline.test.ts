import { cleanup, fireEvent, render, screen } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MessageTimeline from "@/domains/room/MessageTimeline.vue";

import { roomFixture } from "../../fixtures/room";

describe("MessageTimeline history", () => {
  afterEach(cleanup);

  it("offers older and latest pages and lets an off-page reference be located", async () => {
    const snapshot = roomFixture();
    snapshot.messages[1].replyToMessageId = "off-page-message";
    const { emitted } = render(MessageTimeline, {
      props: {
        messages: snapshot.messages,
        members: snapshot.members,
        topics: snapshot.topics,
        hasMore: true,
        hasNewer: true,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    await fireEvent.click(screen.getByRole("button", { name: "加载更早消息" }));
    await fireEvent.click(screen.getByRole("button", { name: "返回最新消息" }));
    await fireEvent.click(screen.getByRole("button", { name: "引用 off-page-message" }));

    expect(emitted().loadOlder).toEqual([[]]);
    expect(emitted().latest).toEqual([[]]);
    expect(emitted().reference).toEqual([["off-page-message"]]);
  });

  it("identifies messages addressed to the room user", () => {
    const snapshot = roomFixture();
    snapshot.messages[1].mentionedMemberIds = ["user"];
    snapshot.messages[1].recipientIds = ["user"];
    snapshot.messages[1].deliveries = [];
    snapshot.messages[1].replyToMessageId = snapshot.messages[0].id;
    render(MessageTimeline, {
      props: {
        messages: snapshot.messages,
        members: snapshot.members,
        topics: snapshot.topics,
        hasMore: false,
        hasNewer: false,
        loadingOlder: false,
        loading: false,
        unavailable: false,
        detailsOpen: false,
      },
    });

    expect(screen.getByText("@ 你")).toBeTruthy();
    expect(screen.getByRole("article", { name: "你的消息" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "引用 #1 · 你" })).toBeTruthy();
    expect(screen.queryByText("YOU")).toBeNull();
  });
});
