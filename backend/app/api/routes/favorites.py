"""收藏路由。

TODO: 实现 GET /、POST /{stop_id}、DELETE /{stop_id}；必须登录，添加与删除保持幂等，
不允许收藏已停用或不存在站点。
"""

from fastapi import APIRouter

router = APIRouter()

