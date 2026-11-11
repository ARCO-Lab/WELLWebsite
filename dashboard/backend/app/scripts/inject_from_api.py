# Fetches new weather, logger and water quality readings from the vendor APIs and stores them.
# scripts/scheduler_temp.py runs this every 10 minutes; `python scripts/inject_from_api.py` runs it once.
#
# How a run works:
#  - Each group (Weather, Logger, Quality) continues from its newest stored reading minus an hour, so
#    readings that arrive late are still picked up and a short outage catches up by itself. A run
#    never looks back more than 14 days; older gaps are filled by scripts/licor_backfill.py (LI-COR)
#    and scripts/wqdata_backfill.py (WQData).
#  - LI-COR (the weather station and the water-level loggers) is read once for both groups, in windows
#    of at most 7 days, splitting any window LI-COR truncates (it caps responses at 100,000 records;
#    see utils/fetching.py). Longer requests used to lose whole sensors silently.
#  - Rows are inserted with ON CONFLICT DO NOTHING, so the overlap costs nothing and repeats don't
#    fill the database log with duplicate-key errors. Each run logs one summary line per source.

import sys
import pathlib
from datetime import datetime, timedelta, timezone

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import sentry_sdk
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from zoneinfo import ZoneInfo

from server import create_app
from db.database import db
from db.models import SensorMeasurement
from api.services.weather import WeatherService
from api.services.quality import QualityService
from config import Config
from utils.fetching import FMT, MAX_DAYS, RUN_LOOKBACK, fetch_range, start_from_newest
from utils.sentry import capture_job_error
from utils.parsers import (LOGGER_CONFIG, QUALITY_PARAM_ID_MAP, licor_rows,  # noqa: F401 (re-exported for other scripts)
                           parse_logger_entry, parse_quality_entry, parse_weather_entry, quality_rows)

app = create_app()
weather_service = WeatherService(Config.HOBO_API_URL, Config.HOBO_API_TOKEN, Config.HOBO_LOGGERS)
quality_service = QualityService(Config.WQ_API_URL, Config.WQ_API_KEY, Config.WQ_DEVICE_ID)

# Where to start when a group has nothing stored yet (when each data source went live).
FIRST_START = {
    "Weather": datetime(2025, 8, 3, 11, 0, tzinfo=timezone.utc),
    "Logger": datetime(2025, 7, 18, 13, 40, tzinfo=timezone.utc),
    "Quality": datetime(2025, 5, 8, 11, 0, tzinfo=timezone.utc),
}
KEY_COLUMNS = ["station_id", "measurement_type", "recorded_at"]   # the table's unique key


def newest_stored(group):
    return db.session.query(func.max(SensorMeasurement.recorded_at)).filter_by(group_type=group).scalar()


def store(rows):
    """Insert rows, skipping any already stored (same station, measurement and time). Returns how many were new."""
    new = 0
    for i in range(0, len(rows), 1000):
        stmt = (insert(SensorMeasurement.__table__).values(rows[i:i + 1000])
                .on_conflict_do_nothing(index_elements=KEY_COLUMNS))
        new += db.session.execute(stmt).rowcount
    db.session.commit()
    return new


def run_start(group, tz, now):
    """Where this run starts for a group: its newest stored reading minus the overlap, at most RUN_LOOKBACK ago."""
    return max(start_from_newest(newest_stored(group), tz, FIRST_START[group]), now - RUN_LOOKBACK)


def inject_licor(tz, now):
    # One read of LI-COR covers both the weather station and the water-level loggers.
    start = max(min(run_start("Weather", tz, now), run_start("Logger", tz, now)), now - timedelta(days=MAX_DAYS))
    records = fetch_range(weather_service.get_page, start, now)
    rows = licor_rows(records, {"Weather", "Logger"}, weather_service.get_logger_id(), tz)
    new = store(list(rows.values()))
    print(f"[INFO] LI-COR: {start:%Y-%m-%d %H:%M} to {now:%Y-%m-%d %H:%M} UTC: {len(records)} records, "
          f"{len(rows)} readings, {new} new")


def inject_quality(tz, now):
    # QualityService follows WQData's paging (until a response holds all the values it reports), so one call
    # covers the range.
    start = run_start("Quality", tz, now)
    entries = quality_service.get_quality_data(start.strftime(FMT), now.strftime(FMT))
    rows = quality_rows(entries, Config.WQ_DEVICE_ID, tz)
    new = store(list(rows.values()))
    print(f"[INFO] WQData: {start:%Y-%m-%d %H:%M} to {now:%Y-%m-%d %H:%M} UTC: {len(entries)} points, "
          f"{len(rows)} readings, {new} new")


def inject_all_new_data():
    # Fetch and store new readings from both vendors. A failure in one doesn't stop the other,
    # but the run still ends with an error so the scheduler logs it as failed.
    with app.app_context():
        tz = ZoneInfo(db.session.execute(text("show timezone")).scalar())   # recorded_at is stored in this zone
        now = datetime.now(timezone.utc)
        failed = []
        for name, job in (("LI-COR", inject_licor), ("WQData", inject_quality)):
            try:
                job(tz, now)
            except Exception as e:
                db.session.rollback()
                failed.append(name)
                print(f"[ERROR] {name} ingestion failed: {e!r}")
                with sentry_sdk.new_scope() as scope:   # a no-op unless the scheduler turned Sentry on
                    scope.set_tag("source", name)
                    capture_job_error(e)
        if failed:
            error = RuntimeError(f"ingestion failed for: {', '.join(failed)}")
            error.already_reported = True   # each failure above went to Sentry with its own traceback
            raise error


if __name__ == "__main__":
    print("[INFO] Starting new data injection...")
    inject_all_new_data()
