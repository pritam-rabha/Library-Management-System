"""Today's date in the library's timezone."""
from datetime import date, datetime, timezone

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

_tz = timezone.utc


def configure(name):
    global _tz
    try:
        _tz = ZoneInfo(name) if ZoneInfo else timezone.utc
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        _tz = timezone.utc


def today():
    return datetime.now(_tz).date()


def parse(value):
    return date.fromisoformat(value)
