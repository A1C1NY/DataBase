"""密码与 JWT 工具。

TODO: 用 Argon2 哈希/验证密码；签发带 sub、role、iat、exp 的短期 JWT；严格校验算法、
过期时间和用户启用状态。禁止把密码、哈希或 token 写入日志。
"""

from typing import NoReturn


def _pending() -> NoReturn:
    raise NotImplementedError("按计划书实现 Argon2 与 JWT")


hash_password = verify_password = create_access_token = decode_access_token = _pending

