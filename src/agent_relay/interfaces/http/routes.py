"""HTTP route modules."""

from fastapi import APIRouter

from agent_relay.interfaces.http.capabilities.routes import router as capability_router
from agent_relay.interfaces.http.diagnostics import router as diagnostics_router
from agent_relay.interfaces.http.events import router as room_events_router
from agent_relay.interfaces.http.greetings import router as greetings_router
from agent_relay.interfaces.http.members.routes import router as member_router
from agent_relay.interfaces.http.rooms.routes import router as room_router

api_router = APIRouter(prefix="/api")
api_router.include_router(greetings_router)
api_router.include_router(diagnostics_router)
api_router.include_router(room_router)
api_router.include_router(capability_router)
api_router.include_router(member_router)
api_router.include_router(room_events_router)
