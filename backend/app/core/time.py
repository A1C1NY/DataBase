"""Asia/Shanghai time helpers used at application and database boundaries."""

from datetime import datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def now_shanghai() -> datetime:
    """Return the current timezone-aware Shanghai time."""

    return datetime.now(tz=SHANGHAI_TZ)


def to_mysql_datetime(value: datetime) -> datetime:
    """Convert an aware datetime to a naive Shanghai ``DATETIME(3)`` value."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("写入数据库的 datetime 必须包含时区")
    local = value.astimezone(SHANGHAI_TZ)
    milliseconds = (local.microsecond // 1000) * 1000
    return local.replace(tzinfo=None, microsecond=milliseconds)


def from_mysql_datetime(value: datetime) -> datetime:
    """Attach the Shanghai timezone to a naive MySQL ``DATETIME(3)`` value."""

    if value.tzinfo is not None or value.utcoffset() is not None:
        raise ValueError("数据库 DATETIME 必须是不含时区的本地时间")
    return value.replace(tzinfo=SHANGHAI_TZ)

