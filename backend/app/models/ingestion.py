"""采集运行、到站快照和发车计划模型。

TODO: 实现 ingestion_runs、arrival_infos、dispatch_schedules、dispatch_cars。保留两辆车
横向结构，不创建 Vehicle 表；使用数据库唯一约束避免一次导入内重复，所有可选字段允许
NULL。课程版只使用简单成功/失败记录，不实现自动任务恢复和历史清理。
"""

from app.db.base import Base


class IngestionRun(Base):
    # TODO: 补齐主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "ingestion_runs"


class ArrivalInfo(Base):
    # TODO: 补齐主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "arrival_infos"


class DispatchSchedule(Base):
    # TODO: 补齐主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "dispatch_schedules"


class DispatchCar(Base):
    # TODO: 补齐主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "dispatch_cars"
