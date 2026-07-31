from datetime import UTC, datetime

import pytest

from app.core.time import (
    SHANGHAI_TZ,
    build_planned_departure_at,
    now,
    to_mysql_datetime,
)


def test_now_uses_shanghai_timezone() -> None:
    result = now()

    assert result.tzinfo == SHANGHAI_TZ


def test_to_mysql_datetime_converts_utc_to_shanghai() -> None:
    value = datetime(2026, 7, 31, 2, 0, tzinfo=UTC)

    result = to_mysql_datetime(value)

    assert result == datetime(2026, 7, 31, 10, 0)
    assert result.tzinfo is None


def test_to_mysql_datetime_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        to_mysql_datetime(datetime(2026, 7, 31, 10, 0))


def test_departure_on_same_day() -> None:
    collected = datetime(2026, 7, 31, 10, 0, tzinfo=SHANGHAI_TZ)

    result = build_planned_departure_at("10:30", collected)

    assert result == datetime(2026, 7, 31, 10, 30, tzinfo=SHANGHAI_TZ)


def test_departure_after_midnight() -> None:
    collected = datetime(2026, 7, 31, 23, 50, tzinfo=SHANGHAI_TZ)

    result = build_planned_departure_at("00:10", collected)

    assert result == datetime(2026, 8, 1, 0, 10, tzinfo=SHANGHAI_TZ)


def test_ambiguous_past_departure_returns_none() -> None:
    collected = datetime(2026, 7, 31, 10, 10, tzinfo=SHANGHAI_TZ)

    assert build_planned_departure_at("10:05", collected) is None


def test_invalid_departure_returns_none() -> None:
    collected = datetime(2026, 7, 31, 10, 0, tzinfo=SHANGHAI_TZ)

    assert build_planned_departure_at("not-a-time", collected) is None

# 使用方法：
# cd backend
# source ../.database/bin/activate
# unset PYTHONPATH
# pytest tests/unit/test_time.py -v
