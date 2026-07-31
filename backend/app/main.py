"""FastAPI 应用装配。

TODO: 加入简单的统一异常响应和前端开发地址 CORS。课程版不启动定时任务，
数据库结构只通过 Alembic 管理。
"""

from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(title="城市公共交通实时状态查询与分析系统", version="0.1.0")
app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    # TODO: 增加数据库连通性检查；不得在响应中泄露连接参数。
    return {"status": "ok"}
