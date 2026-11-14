import { describe, expect, it } from "vitest";

import type { MessageDraft } from "@/services/roomApi";
import { DEFAULT_CHANNEL_ID } from "@/domains/channel/channelRoutes";
import { createMessageDraftStorage } from "@/stores/messageDrafts";

function storageFixture() {
  const saved = new Map<string, string>();
  return {
    getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => saved.set(key, value),
    removeItem: (key: string) => saved.delete(key),
  };
}

describe("message drafts", () => {
  it("restores the full editing context without trimming the content", () => {
    const storage = storageFixture();
    const drafts = createMessageDraftStorage(storage);
    const draft: MessageDraft = {
      content: "  第一行\nsecond line  ",
      topicIds: ["topic"],
      mentionedMemberIds: ["member"],
      capabilities: [{ type: "skill", id: "skill", name: "example" }],
      replyToMessageId: "message",
    };

    drafts.save("room", draft);
    draft.topicIds.push("later-topic");

    expect(createMessageDraftStorage(storage).load("room")).toEqual({
      ...draft,
      topicIds: ["topic"],
    });
  });

  it("deletes only the selected room draft and preserves pending publications", () => {
    const storage = storageFixture();
    const drafts = createMessageDraftStorage(storage);
    const draft: MessageDraft = { content: "first", topicIds: [], mentionedMemberIds: [] };
    storage.setItem("relay-publication:first", "pending");
    drafts.save("first", draft);
    drafts.save("second", { ...draft, content: "second" });

    drafts.remove("first");

    expect(drafts.load("first")).toBeUndefined();
    expect(drafts.load("second")?.content).toBe("second");
    expect(storage.getItem("relay-publication:first")).toBe("pending");
    expect(createMessageDraftStorage(storageFixture()).load("second")).toBeUndefined();
  });

  it("restores channel drafts independently and removes only the selected channel", () => {
    const storage = storageFixture();
    const draft: MessageDraft = {
      content: "default",
      topicIds: [],
      mentionedMemberIds: [],
    };
    const drafts = createMessageDraftStorage(storage);
    drafts.save(`room:${DEFAULT_CHANNEL_ID}`, draft);
    drafts.save("room:channel-api", { ...draft, content: "api" });

    const restored = createMessageDraftStorage(storage);
    expect(restored.load(`room:${DEFAULT_CHANNEL_ID}`)).toEqual(draft);
    expect(restored.load("room:channel-api")?.content).toBe("api");

    restored.remove(`room:${DEFAULT_CHANNEL_ID}`);
    expect(restored.load(`room:${DEFAULT_CHANNEL_ID}`)).toBeUndefined();
    expect(restored.load("room:channel-api")?.content).toBe("api");
  });
});
