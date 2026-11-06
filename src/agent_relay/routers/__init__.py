"""HTTP route modules."""

from fastapi import APIRouter

from agent_relay.routers.diagnostics import router as diagnostics_router
from agent_relay.routers.greetings import router as greetings_router

api_router = APIRouter(prefix="/api")
api_router.include_router(greetings_router)
api_router.include_router(diagnostics_router)
