"""HTTP route modules."""

from fastapi import APIRouter

from conflua.interfaces.http.app_info import router as app_info_router
from conflua.interfaces.http.capabilities.routes import router as capability_router
from conflua.interfaces.http.channels.routes import router as channel_router
from conflua.interfaces.http.diagnostics import router as diagnostics_router
from conflua.interfaces.http.events import router as room_events_router
from conflua.interfaces.http.member_roles.routes import router as member_role_router
from conflua.interfaces.http.members.routes import router as member_router
from conflua.interfaces.http.preferences.routes import router as preferences_router
from conflua.interfaces.http.rooms.routes import channel_router as channel_resource_router
from conflua.interfaces.http.rooms.routes import router as room_router

api_router = APIRouter(prefix="/api")
api_router.include_router(app_info_router)
api_router.include_router(diagnostics_router)
api_router.include_router(preferences_router)
api_router.include_router(member_role_router)
api_router.include_router(room_router)
api_router.include_router(channel_router)
api_router.include_router(channel_resource_router)
api_router.include_router(capability_router)
api_router.include_router(member_router)
api_router.include_router(room_events_router)
