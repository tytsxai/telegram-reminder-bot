"""Time utility helpers."""

from datetime import datetime
import calendar
import pytz
from src.config import settings


def get_timezone(name: str | None = None) -> pytz.BaseTzInfo:
    """Return timezone from config."""
    return pytz.timezone(name or settings.TIMEZONE)


def now_in_timezone(name: str | None = None) -> datetime:
    """Return localized "now" as naive datetime."""
    tz = get_timezone(name)
    return datetime.now(tz).replace(tzinfo=None)


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
