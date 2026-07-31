"""站点和实时信息路由。

TODO: 实现 /nearby、/search、/{id}、/{id}/lines、/{id}/arrivals 和 /{id}/refresh；注意
固定路径必须声明在 /{id} 前。refresh 直接调用上游，不实现短时缓存和并发锁。
"""

from fastapi import APIRouter

router = APIRouter()
