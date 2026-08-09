"""FastAPI routers for the transit API."""

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.favorites import router as favorites_router
from app.api.routes.lines import router as lines_router
from app.api.routes.stops import router as stops_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(favorites_router)
router.include_router(stops_router)
router.include_router(lines_router)

__all__ = ["router"]
