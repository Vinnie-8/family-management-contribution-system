"""
One place for "what day is it" and "what is the time".

A family in Nairobi that records a payment at 01:00 on 1 January expects it to
belong to the new year, even though that moment is still 31 December in UTC.
So "today" and the edges of a financial year are always worked out in the
app's timezone. Change APP_TIMEZONE here if the app is used elsewhere.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("Africa/Nairobi")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_local() -> date:
    return datetime.now(APP_TIMEZONE).date()


def local_date(moment: datetime) -> date:
    """The calendar date of a timestamp, in the app's timezone."""
    return moment.astimezone(APP_TIMEZONE).date()


def day_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """[start of the first day, start of the day after the last day) as aware datetimes.
    Use as:  column >= lower  AND  column < upper."""
    lower = datetime.combine(start, time.min, tzinfo=APP_TIMEZONE)
    upper = datetime.combine(end + timedelta(days=1), time.min, tzinfo=APP_TIMEZONE)
    return lower, upper