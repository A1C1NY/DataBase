"""线路路由。

TODO: 实现 GET /{id}、/{id}/stops、/{id}/dispatch；展示方向时同时返回起终点，
停用线路对普通用户返回 404，但历史数据仍供分析服务使用。
"""

from fastapi import APIRouter

router = APIRouter()

