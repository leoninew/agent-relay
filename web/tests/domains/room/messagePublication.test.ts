import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, type EffectScope } from "vue";

import type { ComposerDraft } from "@/domains/room/composerMemberMention";
import { createMessagePublication } from "@/domains/room/messagePublication";
import { draftSnapshot, useRoomDraft } from "@/domains/room/useRoomDraft";
import { ApiClientError } from "@/services/api";
import { channelCacheKey } from "@/services/cacheKeys";
import { postRoomMessage, type MessageDraft, type RoomMessage } from "@/services/roomApi";
import { createMessageDraftStorage } from "@/stores/messageDrafts";

vi.mock("@/services/roomApi", () => ({ postRoomMessage: vi.fn() }));

const roomId = "0000000000122";
const channelId = "0000000000123";
const publicationId = "original-publication";
const scope = channelCacheKey(roomId, channelId);
const key = channelCacheKey(roomId, channelId, "publication");
const draft: MessageDraft = {
  content: "@Worker hello",
  topicIds: ["topic"],
  mentionedMemberIds: ["worker"],
  replyToMessageId: "quote",
  capabilities: [{ type: "skill", id: "skill", name: "dev-check" }],
};
const original: ComposerDraft = {
  ...draft,
  content: `  ${draft.content}  `,
  memberMentions: [{ id: "worker", name: "Worker", start: 2, end: 9 }],
};
const message: RoomMessage = {
  ...draft,
  publicationId,
  id: "0000000000126",
  seq: 1,
  senderId: "0000000000124",
  senderName: "You",
  createdAt: "2026-11-19T08:50:00Z",
  recipientIds: draft.mentionedMemberIds,
  replyToMessageId: null,
  deliveries: [],
};
const scopes: EffectScope[] = [];

function fixture() {
  const snapshot = draftSnapshot(original);
  const saved = new Map([
    [key, JSON.stringify({ ...draft, publicationId, draftSnapshot: snapshot })],
  ]);
  const storage = {
    getItem: (name: string) => saved.get(name) ?? null,
    setItem: (name: string, value: string) => saved.set(name, value),
    removeItem: (name: string) => saved.delete(name),
  };
  const toasts = { error: vi.fn() };
  const draftStorage = createMessageDraftStorage(storage);
  draftStorage.save(scope, original);
  const effects = effectScope();
  scopes.push(effects);
  const editor = effects.run(() => useRoomDraft(draftStorage))!;
  editor.open(scope);
  const flow = createMessagePublication(storage, toasts, editor.finish);
  return { flow, saved, toasts, editor, draftStorage, snapshot };
}

describe("message publication", () => {
  beforeEach(() => vi.resetAllMocks());
  afterEach(() => scopes.splice(0).forEach((effects) => effects.stop()));

  it("clears the submitted draft and only its publication cache on success", async () => {
    const { flow, saved, editor, snapshot } = fixture();
    const other = channelCacheKey(roomId, "0000000000223", "publication");
    saved.set(other, JSON.stringify({ ...draft, publicationId: "other" }));
    vi.mocked(postRoomMessage).mockResolvedValue(message);

    expect(await flow.send(roomId, channelId, draft, snapshot)).toEqual(message);

    expect(postRoomMessage).toHaveBeenCalledOnce();
    expect(postRoomMessage).toHaveBeenCalledWith(roomId, { ...draft, publicationId }, channelId);
    expect(saved.has(key)).toBe(false);
    expect(saved.has(other)).toBe(true);
    expect(editor.drafts.value[scope].content).toBe("");
  });

  it.each([
    new ApiClientError("timeout", "timeout"),
    new ApiClientError("server error", "http_error", { status: 500 }),
    new ApiClientError("bad request", "http_error", { status: 400 }),
  ])("reports a failed send and retains the editable draft", async (error) => {
    const { flow, toasts, editor, draftStorage, snapshot } = fixture();
    vi.mocked(postRoomMessage).mockRejectedValueOnce(error);

    expect(await flow.send(roomId, channelId, draft, snapshot)).toBeUndefined();

    expect(postRoomMessage).toHaveBeenCalledOnce();
    expect(toasts.error).toHaveBeenCalledOnce();
    expect(editor.drafts.value[scope]).toEqual(original);
    expect(draftStorage.load(scope)).toEqual(original);
    expect(flow).not.toHaveProperty("recover");
  });
});
