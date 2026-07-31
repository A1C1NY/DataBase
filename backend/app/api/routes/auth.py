"""认证路由。

TODO: POST /register、POST /login、GET /me；路由只做 HTTP 校验和 service 调用，
为重复用户名、错误凭据、停用账户提供稳定错误码。
"""

from fastapi import APIRouter

router = APIRouter()

