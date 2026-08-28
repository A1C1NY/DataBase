from decimal import Decimal

from app.services.ingestion import (
    determine_status,
    distance_meters,
    sanitize_request_keyword,
    summarize_messages,
)


def test_distance_matching_distinguishes_nearby_and_separate_stops() -> None:
    near = distance_meters(
        Decimal("121.510610"),
        Decimal("31.153278"),
        Decimal("121.510700"),
        Decimal("31.153300"),
    )
    far = distance_meters(
        Decimal("121.510610"),
        Decimal("31.153278"),
        Decimal("121.511367"),
        Decimal("31.154614"),
    )

    assert near < 50
    assert far > 50


def test_run_status_is_success_partial_or_failed() -> None:
    assert determine_status(successful_records=2, errors=[]) == "success"
    assert determine_status(successful_records=1, errors=["one conflict"]) == "partial"
    assert determine_status(successful_records=0, errors=["all failed"]) == "failed"
    assert (
        determine_status(
            successful_records=0,
            errors=["recoverable conflict"],
            recoverable_errors=True,
        )
        == "partial"
    )


def test_error_summary_is_redacted_and_bounded() -> None:
    summary = summarize_messages(["key=secret-value", "x" * 3000])

    assert summary is not None
    assert "secret-value" not in summary
    assert len(summary) == 2000


def test_request_keyword_is_redacted_and_bounded() -> None:
    keyword = sanitize_request_keyword("云台路 key=secret-value " + "x" * 300)

    assert keyword is not None
    assert "secret-value" not in keyword
    assert len(keyword) == 255
