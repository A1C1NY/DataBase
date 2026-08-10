"""Schemas for stop detail view event context."""

from enum import StrEnum


class StopViewEntryPoint(StrEnum):
    """Allowed UI entry points for a stop detail view."""

    SEARCH = "search"
    LINE_MAP = "line_map"
    FAVORITE = "favorite"
    DIRECT = "direct"


class StopViewActorRole(StrEnum):
    """Role snapshot stored with a stop detail view."""

    ANONYMOUS = "anonymous"
    PASSENGER = "passenger"
    ANALYST = "analyst"
    ADMIN = "admin"
