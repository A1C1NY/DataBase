"""Logging configuration with credential and token redaction."""

import logging
import re
from typing import Final

REDACTED: Final = "***"

_DATABASE_PASSWORD = re.compile(
    r"(?i)\b(mysql(?:\+pymysql)?://[^:\s/@]+:)([^@\s/]+)(@)"
)
_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:key|token|access_token|authorization)=)([^&\s]+)"
)
_NAMED_SECRET = re.compile(
    r"(?i)\b((?:key|api[_-]?key|jwt[_-]?secret|password|passwd|token)\s*[:=]\s*)"
    r"([^\s,;&]+)"
)
_AUTHORIZATION = re.compile(
    r"(?i)\b(authorization\s*[:=]\s*)(?:bearer\s+)?([^\s,;]+)"
)


def redact_sensitive(value: object) -> str:
    """Return log text with common credentials replaced by a marker."""

    text = str(value)
    text = _DATABASE_PASSWORD.sub(rf"\1{REDACTED}\3", text)
    text = _QUERY_SECRET.sub(rf"\1{REDACTED}", text)
    text = _AUTHORIZATION.sub(rf"\1{REDACTED}", text)
    return _NAMED_SECRET.sub(rf"\1{REDACTED}", text)


class SensitiveDataFilter(logging.Filter):
    """Redact secrets after logging arguments have been interpolated."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_sensitive(record.getMessage())
        record.args = ()
        return True


class RedactingFormatter(logging.Formatter):
    """Apply redaction to the final formatted text, including exceptions."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive(super().format(record))


def configure_logging(*, debug: bool = False) -> None:
    """Configure one concise, idempotent root logger for the application."""

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    for existing in root.handlers:
        if getattr(existing, "_amap_transit_handler", False):
            existing.setLevel(root.level)
            return

    handler = logging.StreamHandler()
    handler.setLevel(root.level)
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    handler._amap_transit_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
