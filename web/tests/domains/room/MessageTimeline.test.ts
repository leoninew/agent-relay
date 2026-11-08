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
});
