import type { MessageDraft } from "@/services/roomApi";
import type { JSONStorage } from "@/services/storage";
import { channelResourceKey } from "@/services/cacheKeys";

export function createMessageDraftStorage(storage: JSONStorage = window.sessionStorage) {
  return {
    load(scope: string): MessageDraft | undefined {
      const saved = storage.getItem(channelResourceKey(scope, "draft"));
      return saved ? (JSON.parse(saved) as MessageDraft) : undefined;
    },
    save(scope: string, draft: MessageDraft): void {
      storage.setItem(channelResourceKey(scope, "draft"), JSON.stringify(draft));
    },
    remove(scope: string): void {
      storage.removeItem(channelResourceKey(scope, "draft"));
    },
  };
}
