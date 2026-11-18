import { effectScope } from "vue";
import type { EffectScope } from "vue";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useRoomDraft } from "@/domains/room/useRoomDraft";
import { formatSkillReference, referencedCapabilities } from "@/domains/room/inlineSkills";
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

  it("restores inline skill positions and identities together with the quoted message", () => {
    const skill = { type: "skill", id: "skill-check", name: "dev-check" } as const;
    const marker = formatSkillReference(skill);
    const content = `@Architect   前文🙂 ${marker}\n再用 ${marker} 检查  `;
    const memberMentions = [{ id: "member", name: "Architect", start: 0, end: 10 }];
    const editing = editor();
    editing.open("room");
    editing.drafts.value.room = {
      content,
      topicIds: ["topic"],
      mentionedMemberIds: ["member"],
      memberMentions,
      capabilities: referencedCapabilities(content, [skill]),
      replyToMessageId: "quote",
    };

    const restored = editor();
    restored.open("room");
    const draft = restored.drafts.value.room;

    expect(draft.content).toBe(content);
    expect(draft.replyToMessageId).toBe("quote");
    expect(draft.capabilities).toEqual([skill]);
    expect(draft.memberMentions).toEqual(memberMentions);
    expect(referencedCapabilities(draft.content, draft.capabilities ?? [])).toEqual([skill]);
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

  it("keeps the editable draft and its mention offsets independent of a pending request", () => {
    const original = {
      content: "  @Worker  ",
      topicIds: ["topic"],
      mentionedMemberIds: ["agent"],
      memberMentions: [{ id: "agent", name: "Worker", start: 2, end: 9 }],
    };
    storage.save("room", original);
    const pending: CreateMessage = {
      publicationId: "original-id",
      content: "sent snapshot",
      topicIds: ["original-topic"],
      mentionedMemberIds: ["original-member"],
    };
    const editing = editor(() => true);
    editing.open("room", pending);
    expect(editing.drafts.value.room).toEqual(original);
    editing.drafts.value.room.topicIds = [];

    expect(pending.topicIds).toEqual(["original-topic"]);
    expect(pending.publicationId).toBe("original-id");
    expect(storage.load("room")).toEqual(original);
    expect(editing.drafts.value.room).not.toHaveProperty("publicationId");
    const fallback = editor(() => true);
    fallback.open("missing", pending);
    expect(fallback.drafts.value.missing.content).toBe(pending.content);
    expect(fallback.drafts.value.missing).not.toHaveProperty("publicationId");
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

  it("clears sent content while retaining routing for the next message", () => {
    let locked = false;
    const editing = editor(() => locked);
    editing.open("other");
    editing.drafts.value.other.content = "other draft";
    editing.open("sent");
    editing.drafts.value.sent = {
      content: "sent text",
      topicIds: ["topic"],
      mentionedMemberIds: ["member"],
      capabilities: [{ type: "skill", id: "skill", name: "example" }],
      replyToMessageId: "quote",
    };
    locked = true;
    editing.finish("sent", editing.drafts.value.sent);
    locked = false;

    expect(storage.load("sent")).toEqual({
      content: "",
      topicIds: ["topic"],
      mentionedMemberIds: ["member"],
    });
    expect(storage.load("other")?.content).toBe("other draft");
    const restored = editor();
    restored.open("sent");
    expect(restored.drafts.value.sent.content).toBe("");
    expect(restored.drafts.value.sent.topicIds).toEqual(["topic"]);
    expect(restored.drafts.value.sent.mentionedMemberIds).toEqual(["member"]);
    expect(restored.drafts.value.sent.capabilities).toBeUndefined();
    expect(restored.drafts.value.sent.replyToMessageId).toBeUndefined();
  });
});
