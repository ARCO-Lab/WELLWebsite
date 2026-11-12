# Fetches new weather, logger and water quality readings from the vendor APIs and stores them.
# scripts/scheduler_temp.py runs this every 10 minutes; `python scripts/inject_from_api.py` runs it once.
#
# How a run works:
#  - WQData (Quality) continues from its newest stored reading minus an hour, so readings that arrive late
#    are still picked up and a short outage catches up by itself. LI-COR continues from a few hours before
#    the end of its last fully stored fetch, or from a group's newest reading after a short gap or when the
#    whole station has been silent (see licor_start), so a group silent for days doesn't widen every request;
#    once it reports again, its gap is fetched in the same run (catch_up).
#    A run never looks back more than 14 days; older gaps are filled by scripts/licor_backfill.py (LI-COR)
#    and scripts/wqdata_backfill.py (WQData).
#  - LI-COR (the weather station and the water-level loggers) is read once for both groups, in windows
#    of at most 7 days, splitting any window LI-COR truncates (it caps responses at 100,000 records;
#    see utils/fetching.py). Longer requests used to lose whole sensors silently.
#  - Rows are inserted with ON CONFLICT DO NOTHING, so the overlap costs nothing and repeats don't
#    fill the database log with duplicate-key errors. Each run logs one summary line per source.
#  - The outcome of each vendor call (answered, or the error it failed with) is recorded in the vendor_status
#    table for the email alerts (scripts/check_alerts.py), which use it to tell "the vendor is down" from
#    "the vendor answers but a sensor sent nothing". It is recorded once the answer is parsed: records that
#    can't be read (no or a garbled timestamp, or one without a UTC offset) are skipped, counted in one log line
#    and noted for the alerts, and an answer none of whose records can be read counts as a failed call. A
#    WQData request that fails, or whose paging stalls, fails the run, like LI-COR's.

import sys
import pathlib
from datetime import datetime, timedelta, timezone

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from zoneinfo import ZoneInfo

from server import create_app
from db.database import db
from db.models import SensorMeasurement
from api.services.weather import WeatherService
from api.services.quality import QualityService
from config import Config
from utils.fetching import FMT, RUN_LOOKBACK, UnreadableRecords, fetch_range, start_from_newest
from utils.sentry import capture_job_error
from utils.alerts import describe_vendor_error
from utils.alert_state import fetched_until, record_fetched_until, record_vendor_result
from utils.parsers import (LOGGER_CONFIG, QUALITY_PARAM_ID_MAP, SkippedRecords, licor_rows,  # noqa: F401 (re-exported)
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
# How far before the end of the last LI-COR fetch the next one starts. The station uploads about hourly, so a reading
# is up to an hour old when it appears at LI-COR; one held back by a missed upload (a dropped cellular connection) or
# resent by a wireless logger that lost contact with the station comes later still. 3 hours covers two missed uploads
# and costs about 600 records (one request) a run. Longer gaps are caught up from the stored readings (licor_start).
LICOR_LATE = timedelta(hours=3)
# A LI-COR group whose newest reading is this much older than the last fetch counts as silent (the loggers pulled for
# winter, say) and no longer moves the start back. Until then its newest reading still does, so readings a logger
# resends after losing contact for a few hours are picked up; after it, its gap is fetched once it reports again
# (catch_up), up to 14 days back.
LICOR_SILENT = timedelta(days=1)


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


def licor_start(tz, now):
    """(start, {group: its own start}) for a LI-COR run. The start is LICOR_LATE before the end of the last fetch
    whose readings were all stored, or earlier where a group's newest reading is older than that (a short gap,
    caught up as before), except a group silent for more than LICOR_SILENT. Without that exception a silent group
    dragged every run back to the 14-day limit: two 7-day requests every 10 minutes, burning millions of row ids a
    day on rows already stored. When every group is silent (the whole station offline), the fresher group's newest
    reading sets the start. Either way a run never starts more than LICOR_LATE + LICOR_SILENT ago, so the window stops
    growing while the station is offline, every record is unreadable, or ingestion was down. The groups left out
    (their own start is earlier) are returned, and once one of them reports again inject_licor fetches its gap
    (catch_up). With no fetch recorded yet, the older group's start, as before."""
    starts = {group: run_start(group, tz, now) for group in ("Weather", "Logger")}
    until = fetched_until("LI-COR")
    if until is None:
        start = min(starts.values())
    else:
        reporting = [s for s in starts.values() if s >= until - LICOR_SILENT]
        start = min([until - LICOR_LATE] + reporting) if reporting else max(starts.values())
        start = max(start, now - LICOR_LATE - LICOR_SILENT)
    start = max(start, now - RUN_LOOKBACK)
    return start, {group: s for group, s in starts.items() if s < start}


def catch_up(left_out, rows):
    """(where to fetch from again, the groups back), or (None, []): the earliest start among the left-out groups
    that this answer has readings from that are newer than their newest stored one. A logger out of contact for longer
    than LICOR_SILENT resends what it missed when it reconnects; without this, all but the last few hours of that
    would never be fetched."""
    back = []
    for group in sorted(left_out):
        newest = newest_stored(group)
        if any(r["group_type"] == group and (newest is None or r["recorded_at"] > newest) for r in rows.values()):
            back.append(group)
    return (min(left_out[g] for g in back), back) if back else (None, [])


def read_answer(source, parse, error=None):
    """Parse a vendor answer with parse(skipped) -> rows, then record the call's outcome for the alerts: `error` if
    the call failed, a failure if records came back but none could be read (the vendor changed its format, say),
    else success, noting any records skipped. Recorded only once the answer is read, so an answer we can't read is
    never reported as "vendor OK, check the sensor". Returns (rows, the error to fail the run with, or None)."""
    skipped = SkippedRecords(source)
    try:
        rows = parse(skipped)
    except Exception as e:
        record_vendor_result(source, error or UnreadableRecords(f"{source}'s answer couldn't be read "
                                                                f"({type(e).__name__})"))
        raise
    if error is None and skipped.count and not rows:
        error = UnreadableRecords(f"none of {source}'s records could be read: {skipped.summary()}")
    record_vendor_result(source, error, skipped=skipped.summary())
    return rows, error


def inject_licor(tz, now):
    # One read of LI-COR covers both the weather station and the water-level loggers.
    start, left_out = licor_start(tz, now)
    try:
        records = fetch_range(weather_service.get_page, start, now)
    except Exception as e:
        record_vendor_result("LI-COR", e)
        raise
    rows, error = read_answer("LI-COR", lambda skipped: licor_rows(
        records, {"Weather", "Logger"}, weather_service.get_logger_id(), tz, skipped))
    if error is not None:
        raise error
    gap_start, back = catch_up(left_out, rows)
    if gap_start is not None:
        # A silent group is back: fetch its gap too, before anything is stored or the mark moves.
        try:
            gap = fetch_range(weather_service.get_page, gap_start, start)
        except Exception as e:
            record_vendor_result("LI-COR", e)
            raise
        for key, row in licor_rows(gap, {"Weather", "Logger"}, weather_service.get_logger_id(), tz).items():
            rows.setdefault(key, row)
        print(f"[INFO] LI-COR: {', '.join(back)} reporting again; also fetched "
              f"{gap_start:%Y-%m-%d %H:%M} to {start:%Y-%m-%d %H:%M} UTC: {len(gap)} records")
        records = records + gap
        start = gap_start
    new = store(list(rows.values()))
    record_fetched_until("LI-COR", now)
    print(f"[INFO] LI-COR: {start:%Y-%m-%d %H:%M} to {now:%Y-%m-%d %H:%M} UTC: {len(records)} records, "
          f"{len(rows)} readings, {new} new")


def inject_quality(tz, now):
    # QualityService follows WQData's paging (until a response holds all the values it reports), so one call
    # covers the range.
    start = run_start("Quality", tz, now)
    entries = quality_service.get_quality_data(start.strftime(FMT), now.strftime(FMT))
    # get_quality_data logs a failed request or a paging stall and returns what it read
    rows, error = read_answer("WQData", lambda skipped: quality_rows(entries, Config.WQ_DEVICE_ID, tz, skipped),
                              quality_service.last_error)
    new = store(list(rows.values()))
    print(f"[INFO] WQData: {start:%Y-%m-%d %H:%M} to {now:%Y-%m-%d %H:%M} UTC: {len(entries)} points, "
          f"{len(rows)} readings, {new} new")
    if error is not None:
        # What was read is stored above; the run still fails, so the heartbeat and Sentry see the outage.
        raise RuntimeError(f"WQData request failed: {describe_vendor_error(error)[2]}")


def inject_all_new_data():
    # Fetch and store new readings from both vendors. A failure in one doesn't stop the other,
    # but the run still ends with an error so the scheduler logs it as failed.
    with app.app_context():
        tz = ZoneInfo("America/Toronto")   # recorded_at is site wall-clock time, whatever the database's TimeZone
        now = datetime.now(timezone.utc)
        failed = []
        for name, job in (("LI-COR", inject_licor), ("WQData", inject_quality)):
            try:
                job(tz, now)
            except Exception as e:
                db.session.rollback()
                failed.append(name)
                print(f"[ERROR] {name} ingestion failed: {e!r}")
                capture_job_error(e, source=name)   # a no-op unless the scheduler turned Sentry on
        if failed:
            error = RuntimeError(f"ingestion failed for: {', '.join(failed)}")
            error.already_reported = True   # each failure above went to Sentry with its own traceback
            raise error


if __name__ == "__main__":
    print("[INFO] Starting new data injection...")
    inject_all_new_data()
