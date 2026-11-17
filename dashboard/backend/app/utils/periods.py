"""The days, ISO weeks and months the sensor CSVs are cut into (scripts/sharepoint_upload.py, scripts/upload_data.py).

recorded_at is naive Toronto wall-clock time, so a period runs from midnight to midnight there, half-open: a day is
00:00 to the next 00:00, a week Monday 00:00 to the next Monday 00:00 (ISO 8601 weeks, so week 1 is the one with the
year's first Thursday, and the days around New Year can belong to the other year's weeks), a month the 1st 00:00 to
the next 1st. Each has a key, the form people type and the upload records store:
  daily    2026-11-14   WELLWestCampus_2026-11-14.csv
  weekly   2026-W46     WELLWestCampus_2026-W46.csv
  monthly  2026-10      WELLWestCampus_Oct2026.csv (SharePoint's monthly name; the Borealis monthly upload names
                        the same file 2026-10_WELLWestCampus.csv, built in scripts/upload_data.py)
"""
import re
from collections import namedtuple
from datetime import date, datetime, timedelta

CADENCES = ("daily", "weekly", "monthly")
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

# start and end are naive datetimes at midnight (Toronto wall clock); the period holds start <= t < end
Period = namedtuple("Period", "cadence key start end")


def _midnight(day):
    return datetime(day.year, day.month, day.day)


def containing(cadence, day):
    """The period of `cadence` that holds the date `day`."""
    if cadence == "daily":
        return Period(cadence, day.isoformat(), _midnight(day), _midnight(day + timedelta(days=1)))
    if cadence == "weekly":
        year, week, weekday = day.isocalendar()
        monday = day - timedelta(days=weekday - 1)
        return Period(cadence, f"{year:04d}-W{week:02d}", _midnight(monday), _midnight(monday + timedelta(days=7)))
    if cadence == "monthly":
        first = day.replace(day=1)
        following = first.replace(year=first.year + 1, month=1) if first.month == 12 else \
            first.replace(month=first.month + 1)
        return Period(cadence, f"{first.year:04d}-{first.month:02d}", _midnight(first), _midnight(following))
    raise ValueError(f"unknown cadence {cadence!r}; expected one of {', '.join(CADENCES)}")


def parse(cadence, key):
    """The period of `cadence` named by `key` (2026-11-14, 2026-W46 or 2026-10). ValueError if it isn't one."""
    text = (key or "").strip()
    try:
        if cadence == "daily" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return containing(cadence, date.fromisoformat(text))
        match = re.fullmatch(r"(\d{4})-W(\d{2})", text)
        if cadence == "weekly" and match:
            return containing(cadence, date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1))
        match = re.fullmatch(r"(\d{4})-(\d{2})", text)
        if cadence == "monthly" and match:
            return containing(cadence, date(int(match.group(1)), int(match.group(2)), 1))
    except ValueError:
        pass   # e.g. 2026-02-30 or 2026-W53: reported below like any other bad key
    example = {"daily": "2026-11-14", "weekly": "2026-W46", "monthly": "2026-10"}.get(cadence)
    if example is None:
        raise ValueError(f"unknown cadence {cadence!r}; expected one of {', '.join(CADENCES)}")
    raise ValueError(f"expected a {cadence} period like {example}, got {key!r}")


def first_period(cadence, text, first_month):
    """The first period of `cadence` the scheduler uploads: `text` when set (a key of that cadence), else the one
    that holds the 1st of `first_month` ("YYYY-MM"), so every cadence starts where the monthly copy does."""
    if (text or "").strip():
        return parse(cadence, text)
    return containing(cadence, parse("monthly", first_month).start.date())


def ended(cadence, now, first):
    """Every period of `cadence` from `first` (a Period) on that has ended by `now` (site time), oldest first."""
    today = _midnight(now.date())
    out, period = [], first
    while period.end <= today:
        out.append(period)
        period = containing(cadence, period.end.date())
    return out


def file_name(period):
    """The CSV's name: WELLWestCampus_2026-11-14.csv, WELLWestCampus_2026-W46.csv or WELLWestCampus_Oct2026.csv
    (English month names, whatever the locale)."""
    if period.cadence == "monthly":
        return f"WELLWestCampus_{MONTHS[period.start.month - 1]}{period.start.year}.csv"
    return f"WELLWestCampus_{period.key}.csv"
