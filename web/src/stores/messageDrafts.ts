import type { MessageDraft } from "@/services/roomApi";
import type { JSONStorage } from "@/services/storage";

export function createMessageDraftStorage(storage: JSONStorage = window.sessionStorage) {
  return {
    load(roomId: string): MessageDraft | undefined {
      const saved = storage.getItem(`relay-draft:${roomId}`);
      return saved ? (JSON.parse(saved) as MessageDraft) : undefined;
    },
    save(roomId: string, draft: MessageDraft): void {
      storage.setItem(`relay-draft:${roomId}`, JSON.stringify(draft));
    },
    remove(roomId: string): void {
      storage.removeItem(`relay-draft:${roomId}`);
    },
  };
}
