"""HTTP route modules."""

from fastapi import APIRouter

from agent_relay.room_events import router as room_events_router
from agent_relay.routers.diagnostics import router as diagnostics_router
from agent_relay.routers.greetings import router as greetings_router
from agent_relay.routers.member import router as member_router
from agent_relay.routers.room import router as room_router

api_router = APIRouter(prefix="/api")
api_router.include_router(greetings_router)
api_router.include_router(diagnostics_router)
api_router.include_router(room_router)
api_router.include_router(member_router)
api_router.include_router(room_events_router)
