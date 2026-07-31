"""ORM 模型注册。

TODO: 下列模块合计实现计划书 4.2-4.11 的 10 张表，补全 mapped_column、relationship、
唯一约束、外键、CHECK 与显式索引；完成前不能生成最终迁移。
"""

from app.models.account import FavoriteStop, QueryLog, User
from app.models.ingestion import ArrivalInfo, DispatchCar, DispatchSchedule, IngestionRun
from app.models.transit import Line, LineRoute, Stop

__all__ = ["ArrivalInfo", "DispatchCar", "DispatchSchedule", "FavoriteStop", "IngestionRun",
           "Line", "LineRoute", "QueryLog", "Stop", "User"]

