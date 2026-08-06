"""Minimal application assembly for the stage 6 transit API."""

from fastapi import FastAPI

from app.api import router

app = FastAPI(title="Amap Transit API", version="0.1.0")
app.include_router(router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
