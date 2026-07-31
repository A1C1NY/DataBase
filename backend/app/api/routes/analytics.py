"""分析路由。

TODO: 实现四个计划接口；仅 analyst/admin 可访问，统一校验 start_at < end_at、上海时区、
最大时间范围和分页；CSV 导出可作为后续同一 service 的另一种表现形式。
"""

from fastapi import APIRouter

router = APIRouter()

