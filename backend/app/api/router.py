"""Top-level API router registration."""

from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.favorites import router as favorites_router
from app.api.routes.lines import router as lines_router
from app.api.routes.stops import router as stops_router

router = APIRouter(prefix="/api")
for child in (
    auth_router,
    stops_router,
    lines_router,
    favorites_router,
    analytics_router,
    admin_router,
):
    router.include_router(child)
