import { effectScope } from "vue";
import type { EffectScope } from "vue";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useRoomDraft } from "@/domains/room/useRoomDraft";
import type { CreateMessage } from "@/services/roomApi";
import { createMessageDraftStorage } from "@/stores/messageDrafts";

describe("room draft editing", () => {
  const saved = new Map<string, string>();
  const storage = createMessageDraftStorage({
    getItem: (key) => saved.get(key) ?? null,
    setItem: (key, value) => saved.set(key, value),
    removeItem: (key) => saved.delete(key),
  });
  const scopes: EffectScope[] = [];

  function editor(locked: () => boolean = () => false) {
    const scope = effectScope();
    scopes.push(scope);
    return scope.run(() => useRoomDraft(storage, locked))!;
  }

  beforeEach(() => saved.clear());
  afterEach(() => scopes.splice(0).forEach((scope) => scope.stop()));

  it("saves model updates synchronously and restores them in a new editor", () => {
    const first = editor();
    first.open("room");
    first.drafts.value.room.content = "  已提交中文\nnext line  ";
    first.drafts.value.room.capabilities = [{ type: "skill", id: "skill", name: "example" }];
    first.drafts.value.room.replyToMessageId = "quote";

    expect(storage.load("room")?.content).toBe("  已提交中文\nnext line  ");
    const restored = editor();
    restored.open("room");
    expect(restored.drafts.value.room).toEqual(first.drafts.value.room);
  });

  it("keeps each room's text, routing and quote while switching rooms", () => {
    const editing = editor();
    editing.open("first");
    editing.drafts.value.first = {
      content: "first draft",
      topicIds: ["topic"],
      mentionedMemberIds: ["member"],
      replyToMessageId: "quote",
    };
    editing.open("second");
    editing.drafts.value.second.content = "second draft";
    editing.open("first");

    expect(editing.drafts.value.first).toEqual(storage.load("first"));
    expect(storage.load("second")?.content).toBe("second draft");
  });

  it("persists cleared text and cancelled quotes without restoring old content", () => {
    const editing = editor();
    editing.open("room");
    editing.drafts.value.room.content = "old content";
    editing.drafts.value.room.replyToMessageId = "quote";
    editing.drafts.value.room.content = "";

    expect(storage.load("room")?.replyToMessageId).toBe("quote");
    editing.drafts.value.room.replyToMessageId = undefined;
    expect(storage.load("room")).toBeUndefined();
    editing.open("room");
    expect(editing.drafts.value.room.content).toBe("");
  });

  it("restores a pending request without rewriting it or the saved editable draft", () => {
    const original = { content: "editable", topicIds: ["topic"], mentionedMemberIds: [] };
    storage.save("room", original);
    const pending: CreateMessage = {
      publicationId: "original-id",
      content: "sent snapshot",
      topicIds: ["original-topic"],
      mentionedMemberIds: ["original-member"],
    };
    const editing = editor(() => true);
    editing.open("room", pending);
    editing.drafts.value.room.topicIds = [];

    expect(pending.topicIds).toEqual(["original-topic"]);
    expect(pending.publicationId).toBe("original-id");
    expect(storage.load("room")).toEqual(original);
    expect(editing.drafts.value.room).not.toHaveProperty("publicationId");
  });

  it("keeps unsent content when a send is rejected and editing resumes", () => {
    let locked = false;
    const editing = editor(() => locked);
    editing.open("room");
    editing.drafts.value.room.content = "original text";
    locked = true;

    expect(storage.load("room")?.content).toBe("original text");
    locked = false;
    editing.drafts.value.room.content = "corrected text";

    const restored = editor();
    restored.open("room");
    expect(restored.drafts.value.room.content).toBe("corrected text");
  });

  it("clears the sent room without reset restoring its content or deleting another draft", () => {
    let locked = false;
    const editing = editor(() => locked);
    editing.open("other");
    editing.drafts.value.other.content = "other draft";
    editing.open("sent");
    editing.drafts.value.sent = {
      content: "sent text",
      topicIds: ["topic"],
      mentionedMemberIds: [],
      replyToMessageId: "quote",
    };
    locked = true;
    editing.remove("sent");
    editing.drafts.value.sent = { content: "", topicIds: ["topic"], mentionedMemberIds: [] };
    locked = false;

    expect(storage.load("sent")).toBeUndefined();
    expect(storage.load("other")?.content).toBe("other draft");
    const restored = editor();
    restored.open("sent");
    expect(restored.drafts.value.sent.content).toBe("");
    expect(restored.drafts.value.sent.replyToMessageId).toBeUndefined();
  });
});
