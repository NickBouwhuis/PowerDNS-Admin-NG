"""
PowerDNS-AdminNG API v2 — session-based endpoints for the SPA frontend.

Unlike API v1 (HTTP Basic + API Key auth), v2 uses server-side sessions
shared with the web layer. All endpoints return JSON.
"""
from fastapi import APIRouter, Depends

from powerdnsadmin.api.deps import db_session_cleanup
from .admin import router as admin_router
from .auth import router as auth_router
from .history import router as history_router
from .lookups import router as lookups_router
from .search import router as search_router
from .server import router as server_router
from .settings import router as settings_router
from .zones import router as zones_router

router = APIRouter(prefix="/api/v2", tags=["api-v2"], dependencies=[Depends(db_session_cleanup)])
router.include_router(admin_router)
router.include_router(auth_router)
router.include_router(history_router)
router.include_router(lookups_router)
router.include_router(search_router)
router.include_router(server_router)
router.include_router(settings_router)
router.include_router(zones_router)
