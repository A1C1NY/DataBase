"""FastAPI 应用装配。

TODO: 加入统一异常响应、结构化日志、CORS 白名单和 lifespan；仅当
ENABLE_SCHEDULER=true 时在唯一进程启动/停止 APScheduler。
"""

from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(title="城市公共交通实时状态查询与分析系统", version="0.1.0")
app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    # TODO: 增加数据库连通性检查；不得在响应中泄露连接参数。
    return {"status": "ok"}

