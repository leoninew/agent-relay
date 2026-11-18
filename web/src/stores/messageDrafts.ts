import type { ComposerDraft } from "@/domains/room/composerMemberMention";
import type { JSONStorage } from "@/services/storage";
import { channelResourceKey } from "@/services/cacheKeys";

export function createMessageDraftStorage(storage: JSONStorage = window.sessionStorage) {
  return {
    load(scope: string): ComposerDraft | undefined {
      const saved = storage.getItem(channelResourceKey(scope, "draft"));
      return saved ? (JSON.parse(saved) as ComposerDraft) : undefined;
    },
    save(scope: string, draft: ComposerDraft): void {
      storage.setItem(channelResourceKey(scope, "draft"), JSON.stringify(draft));
    },
    remove(scope: string): void {
      storage.removeItem(channelResourceKey(scope, "draft"));
    },
  };
}
