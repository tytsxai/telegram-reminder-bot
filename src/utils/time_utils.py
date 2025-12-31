"""Time utility helpers."""

from datetime import datetime, timedelta
import calendar
import pytz
from src.config import settings


def get_timezone(name: str | None = None) -> pytz.BaseTzInfo:
    """Return timezone from config."""
    return pytz.timezone(name or settings.TIMEZONE)


def _localize(dt: datetime, tz: pytz.BaseTzInfo) -> datetime:
    """Localize naive datetime with DST-safe handling."""
    if dt.tzinfo:
        return dt.astimezone(tz)
    try:
        return tz.localize(dt, is_dst=None)
    except pytz.NonExistentTimeError:
        # Shift forward to the next valid wall-clock time.
        return tz.localize(dt + timedelta(hours=1), is_dst=None)
    except pytz.AmbiguousTimeError:
        # Prefer standard time on ambiguous fall-back hours.
        return tz.localize(dt, is_dst=False)


def now_in_timezone(name: str | None = None) -> datetime:
    """Return localized "now" as naive datetime."""
    tz = get_timezone(name)
    return datetime.now(tz).replace(tzinfo=None)


def now_utc() -> datetime:
    """Return current UTC time as aware datetime."""
    return datetime.now(tz=pytz.UTC)


def to_utc(dt: datetime, name: str | None = None) -> datetime:
    """Convert naive local time to aware UTC datetime."""
    tz = get_timezone(name)
    localized = _localize(dt, tz)
    return localized.astimezone(pytz.UTC)


def to_utc_iso(dt: datetime, name: str | None = None) -> str:
    """Convert local time to UTC ISO string."""
    return to_utc(dt, name).isoformat()


def from_utc_iso(value: str, name: str | None = None) -> datetime:
    """Parse ISO string and convert UTC to local naive time."""
    tz = get_timezone(name)
    text = value.strip()
    if not text:
        raise ValueError("Empty datetime value")
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        # Backward-compat: treat naive values as local time.
        localized = _localize(dt, tz)
        return localized.replace(tzinfo=None)
    local = dt.astimezone(tz)
    return local.replace(tzinfo=None)


def days_in_month(year: int, month: int) -> int:
    """Return days count for year/month."""
    return calendar.monthrange(year, month)[1]


def add_months(dt: datetime, months: int, target_day: int | None = None) -> datetime:
    """Add months, clamping day to month end when needed."""
    target = target_day or dt.day
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(target, days_in_month(year, month))
    return dt.replace(year=year, month=month, day=day)
