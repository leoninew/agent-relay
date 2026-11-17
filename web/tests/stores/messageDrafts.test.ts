import { describe, expect, it } from "vitest";

import type { MessageDraft } from "@/services/roomApi";
import { channelKey, DEFAULT_CHANNEL_ID } from "@/domains/channel/channelRoutes";
import { channelResourceKey } from "@/services/cacheKeys";
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
    const scope = channelKey("room", DEFAULT_CHANNEL_ID);
    const draft: MessageDraft = {
      content: "  第一行\nsecond line  ",
      topicIds: ["topic"],
      mentionedMemberIds: ["member"],
      capabilities: [{ type: "skill", id: "skill", name: "example" }],
      replyToMessageId: "message",
    };

    drafts.save(scope, draft);
    draft.topicIds.push("later-topic");

    expect(createMessageDraftStorage(storage).load(scope)).toEqual({
      ...draft,
      topicIds: ["topic"],
    });
  });

  it("deletes only the selected room draft and preserves pending publications", () => {
    const storage = storageFixture();
    const drafts = createMessageDraftStorage(storage);
    const draft: MessageDraft = { content: "first", topicIds: [], mentionedMemberIds: [] };
    const first = channelKey("room", "channel-first");
    const second = channelKey("room", "channel-second");
    const publication = channelResourceKey(first, "publication");
    storage.setItem(publication, "pending");
    drafts.save(first, draft);
    drafts.save(second, { ...draft, content: "second" });

    drafts.remove(first);

    expect(drafts.load(first)).toBeUndefined();
    expect(drafts.load(second)?.content).toBe("second");
    expect(storage.getItem(publication)).toBe("pending");
    expect(createMessageDraftStorage(storageFixture()).load(second)).toBeUndefined();
  });

  it("restores channel drafts independently and removes only the selected channel", () => {
    const storage = storageFixture();
    const draft: MessageDraft = {
      content: "default",
      topicIds: [],
      mentionedMemberIds: [],
    };
    const drafts = createMessageDraftStorage(storage);
    const defaultScope = channelKey("room", DEFAULT_CHANNEL_ID);
    const apiScope = channelKey("room", "channel-api");
    drafts.save(defaultScope, draft);
    drafts.save(apiScope, { ...draft, content: "api" });

    const restored = createMessageDraftStorage(storage);
    expect(restored.load(defaultScope)).toEqual(draft);
    expect(restored.load(apiScope)?.content).toBe("api");

    restored.remove(defaultScope);
    expect(restored.load(defaultScope)).toBeUndefined();
    expect(restored.load(apiScope)?.content).toBe("api");
  });
});
