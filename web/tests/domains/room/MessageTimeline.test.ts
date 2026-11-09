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

  it("shows one standalone time marker per minute before its message group", () => {
    const snapshot = roomFixture();
    const messages = snapshot.messages.map((message, index) => ({
      ...message,
      createdAt: index === 0 ? "2026-11-06T10:00:23Z" : "2026-11-06T10:00:48Z",
    }));
    messages.push({
      ...messages[1],
      id: "msg-0003",
      seq: 3,
      createdAt: "2026-11-06T10:01:00Z",
    });
    const { container } = render(MessageTimeline, {
      props: {
        messages,
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

    const markers = Array.from(container.querySelectorAll(".timeline-time time"));
    expect(markers).toHaveLength(2);
    expect(markers.map((marker) => marker.getAttribute("datetime"))).toEqual([
      messages[0].createdAt,
      messages[2].createdAt,
    ]);
    expect(markers.every((marker) => /^\d{2}:\d{2}$/.test(marker.textContent ?? ""))).toBe(true);
    expect(container.querySelectorAll(".message-content .message-time")).toHaveLength(0);
    expect(markers[0].parentElement?.nextElementSibling?.classList.contains("message")).toBe(true);
    expect(markers[1].parentElement?.nextElementSibling?.classList.contains("message")).toBe(true);
  });

  it("updates authors and references when members are renamed without reloading messages", async () => {
    const snapshot = roomFixture();
    snapshot.messages[0].replyToMessageId = snapshot.messages[1].id;
    const { rerender } = render(MessageTimeline, {
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

    expect(screen.getByRole("article", { name: "后端 Worker的消息" })).toBeTruthy();
    await rerender({
      members: snapshot.members.map((member) =>
        member.id === "backend-worker" ? { ...member, name: "后端开发" } : member,
      ),
    });

    expect(screen.getByRole("article", { name: "后端开发的消息" })).toBeTruthy();
    expect(screen.getByText("后端开发", { selector: ".message-author" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "引用 #2 · 后端开发" })).toBeTruthy();
    expect(screen.queryByText("后端 Worker")).toBeNull();
  });
});
