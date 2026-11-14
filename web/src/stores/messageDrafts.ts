import type { MessageDraft } from "@/services/roomApi";
import type { JSONStorage } from "@/services/storage";

export function createMessageDraftStorage(storage: JSONStorage = window.sessionStorage) {
  return {
    load(scope: string): MessageDraft | undefined {
      const saved = storage.getItem(`relay-draft:${scope}`);
      return saved ? (JSON.parse(saved) as MessageDraft) : undefined;
    },
    save(scope: string, draft: MessageDraft): void {
      storage.setItem(`relay-draft:${scope}`, JSON.stringify(draft));
    },
    remove(scope: string): void {
      storage.removeItem(`relay-draft:${scope}`);
    },
  };
}
