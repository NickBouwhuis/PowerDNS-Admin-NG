"""FastAPI v1 API routers."""
from fastapi import APIRouter

from .health import router as health_router
from .zones import router as zones_router
from .servers import router as servers_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(zones_router)
router.include_router(servers_router)
