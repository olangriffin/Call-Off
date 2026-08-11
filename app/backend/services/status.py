from __future__ import annotations

import re

from sqlalchemy import func


COMPLETE_STATUSES = frozenset(
    {
        "accepted",
        "accepted_with_comments",
        "approved",
        "closed",
        "complete",
        "completed",
    }
)

_STATUS_SEPARATOR_RE = re.compile(r"[\s_-]+")
_SQL_WHITESPACE = " \t\n\r\f\v"


def normalize_status(value: object | None) -> str:
    """Return the canonical comparison form for an operational status."""

    if value is None:
        return ""

    return _STATUS_SEPARATOR_RE.sub("_", str(value).strip().lower())


def normalize_status_expression(column):
    """Return the SQL equivalent of :func:`normalize_status`.

    The bounded underscore-collapse loop covers every possible separator run
    in the current 30-character status columns while remaining portable across
    PostgreSQL and the SQLite test database.
    """

    expression = func.lower(
        func.ltrim(func.rtrim(column, _SQL_WHITESPACE), _SQL_WHITESPACE)
    )
    for separator in ("-", " ", "\t", "\n", "\r", "\f", "\v"):
        expression = func.replace(expression, separator, "_")
    for _ in range(5):
        expression = func.replace(expression, "__", "_")

    return expression


def is_complete_status(value: object | None) -> bool:
    return normalize_status(value) in COMPLETE_STATUSES


def is_complete_status_expression(column):
    return normalize_status_expression(column).in_(COMPLETE_STATUSES)
