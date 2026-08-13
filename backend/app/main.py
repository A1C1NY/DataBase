"""Application assembly; schema migration and jobs deliberately live elsewhere."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Alembic owns the schema and this application has no scheduler.
    yield


description = """
高德公交站点与线路 API。公共查询采用数据库优先流程：本地无结果时由高德
`stopname` / `linename` 补数，点击未解析线路摘要时由 `lineid` 补数。

角色：`passenger` 使用公共与收藏接口；`analyst` 可读分析和导入记录；
`admin` 包含分析权限并可管理用户及逻辑启停基础数据。

错误统一为 `{\"detail\": {\"code\": \"...\", \"message\": \"...\"}}`；补数空结果为
`NOT_FOUND_AFTER_AMAP`，上游不可用为 `AMAP_UNAVAILABLE`，业务错误为 `AMAP_BUSINESS_ERROR`。
"""


app = FastAPI(
    title="Amap Transit API",
    version="0.1.0",
    description=description,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_strings,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    )
    return JSONResponse(
        content={"detail": detail},
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        content={"detail": {"code": "INVALID_REQUEST", "message": "请求参数校验失败"}},
        status_code=422,
    )


@app.exception_handler(Exception)
async def internal_error(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        content={"detail": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"}},
        status_code=500,
    )


@app.get("/health", tags=["health"], summary="应用存活检查")
def health() -> dict[str, str]:
    return {"status": "ok"}
