import { cleanup, render, screen } from "@testing-library/vue";
import { afterEach, describe, expect, it } from "vitest";

import MemberTopicPositions from "@/domains/room/MemberTopicPositions.vue";
import { formatDateTime } from "@/utils/time";

import { roomFixture } from "../../fixtures/room";

describe("MemberTopicPositions", () => {
  afterEach(cleanup);

  it("shows per-topic positions, later counts and a time with seconds", () => {
    const snapshot = roomFixture();
    const updatedAt = "2026-11-06T10:00:17Z";
    render(MemberTopicPositions, {
      props: {
        member: snapshot.members[0],
        topics: snapshot.topics,
        positions: [{ ...snapshot.positions[0], seq: 104, updatedAt, laterCount: 3 }],
      },
    });

    expect(screen.getByRole("region", { name: "前端 Worker的查阅位置" })).toBeTruthy();
    expect(screen.getByText("# 前端")).toBeTruthy();
    expect(screen.getByText("位置 #104")).toBeTruthy();
    expect(screen.getByText("位置后新增 3 条")).toBeTruthy();
    expect(screen.getByText(formatDateTime(updatedAt)).getAttribute("datetime")).toBe(updatedAt);
    expect(screen.getByText("服务提供过的最大消息序号，允许跳读。")).toBeTruthy();
  });

  it("offers an initial position and a count for a subscribed topic before any query", () => {
    const snapshot = roomFixture();
    render(MemberTopicPositions, {
      props: {
        member: snapshot.members[0],
        topics: snapshot.topics,
        positions: [snapshot.positions[0]],
      },
    });
    expect(screen.getByText("尚无查阅位置")).toBeTruthy();
    expect(screen.getByText("位置后新增 1 条")).toBeTruthy();
  });
});
