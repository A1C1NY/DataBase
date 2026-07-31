"""站点和实时信息路由。

TODO: 实现 /nearby、/search、/{id}、/{id}/lines、/{id}/arrivals、/{id}/refresh；注意固定
路径必须声明在 /{id} 前，参数设置范围和数量上限，刷新返回缓存命中与最后更新时间。
"""

from fastapi import APIRouter

router = APIRouter()

