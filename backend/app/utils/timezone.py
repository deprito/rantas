"""Timezone utilities for converting UTC to local timezone.

All timestamps are stored in UTC in the database and converted to
Asia/Jakarta timezone when displaying to users.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.config import settings

# Display timezone (Asia/Jakarta)
DISPLAY_TZ = ZoneInfo(settings.TIMEZONE)
# UTC timezone
UTC_TZ = timezone.utc


def now_utc() -> datetime:
    """Get current datetime in UTC for database storage.

    Returns:
        Current datetime in UTC (timezone-aware)
    """
    return datetime.now(UTC_TZ)


def to_local_timezone(dt: datetime) -> datetime:
    """Convert a datetime to Asia/Jakarta timezone for display.

    Args:
        dt: DateTime to convert (can be naive or timezone-aware)

    Returns:
        DateTime in Asia/Jakarta timezone
    """
    if dt is None:
        return None

    # If naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)

    # Convert to display timezone
    return dt.astimezone(DISPLAY_TZ)


def to_iso_with_timezone(dt: datetime) -> str:
    """Convert datetime to ISO string with timezone offset.

    Args:
        dt: DateTime to convert

    Returns:
        ISO formatted string with timezone offset
    """
    if dt is None:
        return None

    # Convert to local timezone first
    local_dt = to_local_timezone(dt)
    return local_dt.isoformat()


def format_datetime(dt: datetime, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime for display in local timezone.

    Args:
        dt: DateTime to format
        format: strftime format string

    Returns:
        Formatted datetime string
    """
    if dt is None:
        return None

    local_dt = to_local_timezone(dt)
    return local_dt.strftime(format)
