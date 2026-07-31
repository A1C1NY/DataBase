"""已完成的上海时区与计划发车时间工具。"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def now() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def to_mysql_datetime(value: datetime) -> datetime:
    """转换为写入 MySQL DATETIME 的上海本地无时区时间。"""
    if value.tzinfo is None:
        raise ValueError("必须传入带时区 datetime")

    return value.astimezone(SHANGHAI_TZ).replace(tzinfo=None)


def from_mysql_datetime(value: datetime) -> datetime:
    """把从 MySQL DATETIME 读取的时间解释为上海时间。"""
    if value.tzinfo is not None:
        return value.astimezone(SHANGHAI_TZ)

    return value.replace(tzinfo=SHANGHAI_TZ)


def build_planned_departure_at(time_text: str | None, collected_at: datetime) -> datetime | None:
    if not time_text:
        return None

    if collected_at.tzinfo is None:
        raise ValueError("collected_at 必须是带时区的 datetime")

    collected_shanghai = collected_at.astimezone(SHANGHAI_TZ)

    try:
        departure_time = time.fromisoformat(time_text)
    except ValueError:
        return None

    planned_at = datetime.combine(collected_shanghai.date(), departure_time, tzinfo=SHANGHAI_TZ)

    # 当天尚未到达的时间，可以直接使用。
    if planned_at >= collected_shanghai:
        return planned_at

    next_day_at = planned_at + timedelta(days=1)

    # 只把临近午夜、且距离不超过 12 小时的情况解释为次日。
    if collected_shanghai.hour >= 18:
        if next_day_at - collected_shanghai <= timedelta(hours=12):
            return next_day_at

    # 时间已经过去，但又没有足够证据认为它属于次日。
    return None
