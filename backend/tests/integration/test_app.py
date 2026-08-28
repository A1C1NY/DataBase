"""Application assembly and public HTTP contract coverage."""

import asyncio
from contextlib import AsyncExitStack

from fastapi.exceptions import RequestValidationError

from app.main import app, health, lifespan, validation_error


def test_health_check() -> None:
    assert health() == {"status": "ok"}


def test_validation_errors_use_common_shape() -> None:
    response = asyncio.run(
        validation_error(
            None,  # type: ignore[arg-type]
            RequestValidationError([{"loc": ("query", "q"), "msg": "invalid"}]),
        )
    )

    assert response.status_code == 422
    assert b'"code":"INVALID_REQUEST"' in response.body


def test_openapi_registers_admin_routes_and_documents_workflow() -> None:
    document = app.openapi()

    assert "/api/admin/users" in document["paths"]
    assert "/api/admin/ingestion-runs" in document["paths"]
    assert "数据库优先" in document["info"]["description"]
    assert "NOT_FOUND_AFTER_AMAP" in document["info"]["description"]


def test_lifespan_has_no_schema_or_scheduler_side_effects(monkeypatch) -> None:
    import app.db.base as base_module

    monkeypatch.setattr(
        base_module.Base.metadata,
        "create_all",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("create_all called")
        ),
    )

    async def enter_lifespan() -> None:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(lifespan(app))

    asyncio.run(enter_lifespan())
