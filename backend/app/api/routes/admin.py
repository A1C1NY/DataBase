"""管理员路由。

TODO: 用户列表/创建/更新，采集运行列表/详情，高德线路/站点与上海附近手动同步，线路和
站点启停、数据质量摘要。全部要求 admin，手动任务需返回 ingestion_run_id 便于追踪。
"""

from fastapi import APIRouter

router = APIRouter()

