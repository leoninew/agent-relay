import asyncio
import logging
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from agent_relay.room_errors import RoomNotFoundError
from agent_relay.room_queries import RoomQueries

router = APIRouter()


@router.websocket("/room/{room_id}/event/stream")
async def stream_events(websocket: WebSocket, room_id: str, after_event_id: int = 0) -> None:
    queries = RoomQueries(websocket.app.state.room_service.store)
    if after_event_id < 0:
        await websocket.close(code=1008)
        return
    try:
        page = await run_in_threadpool(queries.events, room_id, after_event_id)
    except RoomNotFoundError:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(page.model_dump(mode="json", by_alias=True))
            if page.resync_required:
                await websocket.close(code=1000)
                return
            after_event_id = page.next_event_id
            if not page.has_more:
                with suppress(TimeoutError):
                    await asyncio.wait_for(websocket.receive_text(), timeout=1)
            page = await run_in_threadpool(queries.events, room_id, after_event_id)
    except WebSocketDisconnect:
        return
    except Exception:
        logging.getLogger("agent_relay.http").exception("Room event stream failed room=%s", room_id)
        await websocket.close(code=1011)
