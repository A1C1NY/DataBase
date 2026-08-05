from datetime import UTC, datetime

import pytest

from app.core.time import (
    SHANGHAI_TZ,
    from_mysql_datetime,
    now_shanghai,
    to_mysql_datetime,
)


def test_now_shanghai_is_timezone_aware() -> None:
    current = now_shanghai()

    assert current.tzinfo is SHANGHAI_TZ
    assert current.utcoffset() is not None


def test_to_mysql_datetime_converts_to_shanghai_and_milliseconds() -> None:
    utc_value = datetime(2026, 8, 5, 2, 3, 4, 567_891, tzinfo=UTC)

    result = to_mysql_datetime(utc_value)

    assert result == datetime.fromisoformat("2026-08-05T10:03:04.567")
    assert result.tzinfo is None


def test_to_mysql_datetime_rejects_naive_value() -> None:
    with pytest.raises(ValueError, match="必须包含时区"):
        to_mysql_datetime(datetime.fromisoformat("2026-08-05T10:00:00"))


def test_from_mysql_datetime_attaches_shanghai_timezone() -> None:
    result = from_mysql_datetime(datetime.fromisoformat("2026-08-05T10:03:04.567"))

    assert result.tzinfo is SHANGHAI_TZ
    assert result.utcoffset() is not None


def test_from_mysql_datetime_rejects_aware_value() -> None:
    with pytest.raises(ValueError, match="不含时区"):
        from_mysql_datetime(datetime(2026, 8, 5, 10, 0, tzinfo=SHANGHAI_TZ))
