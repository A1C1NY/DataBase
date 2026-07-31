"""API 总路由。"""

from fastapi import APIRouter

from app.api.routes import admin, analytics, auth, favorites, lines, stops

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(stops.router, prefix="/stops", tags=["stops"])
api_router.include_router(lines.router, prefix="/lines", tags=["lines"])
api_router.include_router(favorites.router, prefix="/me/favorite-stops", tags=["favorites"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

