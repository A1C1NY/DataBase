import logging

from app.core.logging import RedactingFormatter, SensitiveDataFilter, redact_sensitive


def test_redact_sensitive_hides_database_and_request_credentials() -> None:
    message = (
        "database=mysql+pymysql://user:db-secret@127.0.0.1/transit "
        "url=https://restapi.amap.com/v3/bus/stopname?key=amap-secret&keywords=test "
        "JWT_SECRET=jwt-secret Authorization: Bearer bearer-secret"
    )

    redacted = redact_sensitive(message)

    assert "db-secret" not in redacted
    assert "amap-secret" not in redacted
    assert "jwt-secret" not in redacted
    assert "bearer-secret" not in redacted
    assert redacted.count("***") >= 4


def test_filter_redacts_interpolated_logging_arguments() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request key=%s",
        args=("secret-value",),
        exc_info=None,
    )

    assert SensitiveDataFilter().filter(record) is True
    assert record.getMessage() == "request key=***"


def test_formatter_redacts_exception_messages() -> None:
    try:
        raise RuntimeError("password=exception-secret")
    except RuntimeError:
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="upstream failed",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )

    output = RedactingFormatter("%(levelname)s %(message)s").format(record)

    assert "exception-secret" not in output
    assert "password=***" in output
