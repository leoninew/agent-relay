import type { MessageDescriptor } from "@/i18n";
import { ApiClientError, describeApiError } from "@/services/api";
import { channelCacheKey, channelResourceKey } from "@/services/cacheKeys";
import { postRoomMessage } from "@/services/roomApi";
import type { CreateMessage, MessageDraft, RoomMessage } from "@/services/roomApi";
import { readJSON, type JSONStorage } from "@/services/storage";

type PendingPublication = CreateMessage & { draftSnapshot?: string };

export function createMessagePublication(
  storage: JSONStorage,
  toasts: Record<"error", (message: MessageDescriptor) => void>,
  finishDraft: (scope: string, sent: MessageDraft, snapshot: string) => void,
) {
  function pending(key: string): PendingPublication | undefined {
    return readJSON<PendingPublication | undefined>(storage, key, undefined);
  }

  function confirm(scope: string, key: string, cached: string, attempt: PendingPublication) {
    if (storage.getItem(key) !== cached) {
      return false;
    }
    if (typeof attempt.draftSnapshot === "string") {
      finishDraft(scope, attempt, attempt.draftSnapshot);
    }
    storage.removeItem(key);
    return true;
  }

  async function send(roomId: string, channelId: string, draft: MessageDraft, snapshot: string) {
    const scope = channelCacheKey(roomId, channelId);
    const key = channelResourceKey(scope, "publication");
    const previous = pending(key);
    const previousBody = { ...previous, publicationId: undefined, draftSnapshot: undefined };
    const request: CreateMessage = {
      ...draft,
      publicationId:
        previous?.publicationId && JSON.stringify(previousBody) === JSON.stringify(draft)
          ? previous.publicationId
          : crypto.randomUUID(),
    };
    const attempt: PendingPublication = { ...request, draftSnapshot: snapshot };
    const cached = JSON.stringify(attempt);
    storage.setItem(key, cached);
    let message: RoomMessage;
    try {
      message = await postRoomMessage(roomId, request, channelId);
    } catch (caught) {
      toasts.error(describeApiError(caught, "errors.publish"));
      if (
        caught instanceof ApiClientError &&
        caught.kind === "http_error" &&
        caught.status !== undefined &&
        caught.status >= 400 &&
        caught.status < 500
      ) {
        if (storage.getItem(key) === cached) {
          storage.removeItem(key);
        }
      }
      return undefined;
    }
    confirm(scope, key, cached, attempt);
    return message;
  }

  return { send };
}
