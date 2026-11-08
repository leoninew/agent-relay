import { fetchRoomEvents } from "@/services/roomApi";
import type { RoomEventPage } from "@/services/roomApi";

export type SyncState = "connecting" | "connected" | "reconnecting";

export function subscribeRoomEvents(
  roomId: string,
  afterEventId: number,
  apply: (page: RoomEventPage) => Promise<void>,
  status: (state: SyncState) => void,
): () => void {
  let stopped = false;
  let socket: WebSocket | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const controller = new AbortController();
  let chain = Promise.resolve();
  let generation = 0;

  async function consume(page: RoomEventPage): Promise<void> {
    if (stopped || (!page.resyncRequired && page.nextEventId <= afterEventId)) return;
    await apply(page);
    if (!stopped) afterEventId = page.nextEventId;
  }

  function reconnect(): void {
    if (stopped || timer) return;
    status("reconnecting");
    timer = setTimeout(() => {
      timer = undefined;
      void connect();
    }, 1000);
  }

  async function connect(): Promise<void> {
    const currentGeneration = ++generation;
    try {
      await chain;
      let page: RoomEventPage;
      do {
        page = await fetchRoomEvents(roomId, afterEventId, controller.signal);
        if (stopped) return;
        await consume(page);
      } while (!stopped && page.hasMore && !page.resyncRequired);
      if (stopped) return;
      const url = new URL(
        `/api/room/${encodeURIComponent(roomId)}/event/stream`,
        window.location.href,
      );
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      url.searchParams.set("after_event_id", String(afterEventId));
      const active = new WebSocket(url);
      socket = active;
      active.onopen = () => {
        if (!stopped) status("connected");
      };
      active.onmessage = (event: MessageEvent<string>) => {
        chain = chain
          .then(async () => {
            if (stopped || currentGeneration !== generation) return;
            await consume(JSON.parse(event.data) as RoomEventPage);
          })
          .catch(() => {
            if (currentGeneration === generation) generation++;
            active.close();
            reconnect();
          });
      };
      active.onclose = reconnect;
      active.onerror = () => active.close();
    } catch {
      reconnect();
    }
  }

  status("connecting");
  void connect();
  return () => {
    stopped = true;
    generation++;
    controller.abort();
    if (timer) clearTimeout(timer);
    socket?.close();
  };
}
