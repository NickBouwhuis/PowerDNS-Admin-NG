"""FastAPI v1 API routers."""
from fastapi import APIRouter

from .health import router as health_router
from .zones import router as zones_router
from .servers import router as servers_router
from .users import router as users_router
from .accounts import router as accounts_router
from .apikeys import router as apikeys_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(zones_router)
router.include_router(users_router)
router.include_router(accounts_router)
router.include_router(apikeys_router)
# Server routes MUST be last -- they have catch-all path patterns
router.include_router(servers_router)
