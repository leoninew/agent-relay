"""HTTP route modules."""

from fastapi import APIRouter

from agent_relay.interfaces.http.app_info import router as app_info_router
from agent_relay.interfaces.http.capabilities.routes import router as capability_router
from agent_relay.interfaces.http.diagnostics import router as diagnostics_router
from agent_relay.interfaces.http.events import router as room_events_router
from agent_relay.interfaces.http.members.routes import router as member_router
from agent_relay.interfaces.http.preferences.routes import router as preferences_router
from agent_relay.interfaces.http.rooms.routes import router as room_router

api_router = APIRouter(prefix="/api")
api_router.include_router(app_info_router)
api_router.include_router(diagnostics_router)
api_router.include_router(preferences_router)
api_router.include_router(room_router)
api_router.include_router(capability_router)
api_router.include_router(member_router)
api_router.include_router(room_events_router)
