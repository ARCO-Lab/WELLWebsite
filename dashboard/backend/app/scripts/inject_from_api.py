# Fetches new weather, logger and water quality readings from the vendor APIs and stores them.
# scripts/scheduler_temp.py runs this every 10 minutes; `python scripts/inject_from_api.py` runs it once.
#
# How a run works:
#  - WQData (Quality) continues from its newest stored reading minus an hour, so readings that arrive late
#    are still picked up and a short outage catches up by itself. LI-COR continues from a few hours before
#    the end of its last fully stored fetch, or from a group's newest reading after a short gap or when the
#    whole station has been silent (see licor_start), so a group silent for days doesn't widen every request.
#    Any station (the weather station or one logger) that reports again after a longer silence than that window
#    covers has its gap fetched in the same run (catch_up), even while the other loggers kept reporting.
#    A run never starts after now (minus the hour of overlap): records dated in the future are skipped, and one
#    stored before that was in place can't stop the fetches.
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
#    and noted for the alerts, and an answer none of whose records can be read counts as a failed call. So are
#    records dated more than an hour in the future and LI-COR records in an unexpected unit. LI-COR's fetch mark
#    doesn't move past the earliest unreadable record whose time is known, so it is read again by the next runs
#    (not past one in a wrong unit: a swapped sensor would pin it; licor_backfill.py refills those). A
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
from utils.fetching import FMT, OVERLAP, RUN_LOOKBACK, UnreadableRecords, fetch_range, start_from_newest
from utils.sentry import capture_job_error, capture_job_warning
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
# and costs about 600 records (one request) a run. Longer gaps are caught up from the stored readings (licor_start,
# catch_up).
LICOR_LATE = timedelta(hours=3)
# A LI-COR group whose newest reading is this much older than the last fetch counts as silent (the loggers pulled for
# winter, say) and no longer moves the start back. Until then its newest reading still does. Either way, a station
# whose newest reading is older than the start has its gap fetched once it reports again (catch_up), up to 14 days
# back: one logger out of contact for 12 hours while the others kept reporting, say.
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
    """Where this run starts for a group: its newest stored reading minus the overlap, at most RUN_LOOKBACK ago, and
    never later than now minus the overlap: a reading stored with a future time (a device clock that jumped ahead,
    before such records were skipped) would otherwise make every request start after it ends, and nothing new
    would be stored until someone deleted the row."""
    start = max(start_from_newest(newest_stored(group), tz, FIRST_START[group]), now - RUN_LOOKBACK)
    return min(start, now - OVERLAP)


def licor_start(tz, now):
    """Where a LI-COR run starts: LICOR_LATE before the end of the last fetch whose readings were all stored, or
    earlier where a group's newest reading is older than that (a short gap, caught up as before), except a group
    silent for more than LICOR_SILENT. Without that exception a silent group
    dragged every run back to the 14-day limit: two 7-day requests every 10 minutes, burning millions of row ids a
    day on rows already stored. When every group is silent (the whole station offline), the fresher group's newest
    reading sets the start. Either way a run never starts more than LICOR_LATE + LICOR_SILENT ago, so the window stops
    growing while the station is offline, every record is unreadable, or ingestion was down. A station left out
    (its newest reading is older than the start) has its gap fetched once it reports again (catch_up). With no fetch
    recorded yet, the older group's start, as before."""
    starts = {group: run_start(group, tz, now) for group in ("Weather", "Logger")}
    until = fetched_until("LI-COR")
    if until is None:
        start = min(starts.values())
    else:
        reporting = [s for s in starts.values() if s >= until - LICOR_SILENT]
        start = min([until - LICOR_LATE] + reporting) if reporting else max(starts.values())
        start = max(start, now - LICOR_LATE - LICOR_SILENT)
    return max(start, now - RUN_LOOKBACK)


def stations_newest(rows):
    """{(group, station_id): (its newest stored reading, its newest reading in rows)}, local wall-clock times, for
    each station in rows. The stored one is the newest over the station's series in rows, one lookup of the series
    index each (a station's series that sent nothing don't count). When none of those has anything stored (a sensor
    added to the station, say), the newest over all of the station's series; None for a station never stored."""
    answered = {}
    for r in rows.values():
        key = (r["group_type"], r["station_id"], r["measurement_type"])
        answered[key] = max(answered.get(key, r["recorded_at"]), r["recorded_at"])
    stations = {}
    for (group, station, measurement), newest in sorted(answered.items()):
        stored = (db.session.query(func.max(SensorMeasurement.recorded_at))
                  .filter_by(group_type=group, station_id=station, measurement_type=measurement).scalar())
        old_stored, old_answered = stations.get((group, station), (None, None))
        if old_stored is not None and (stored is None or old_stored > stored):
            stored = old_stored
        stations[(group, station)] = (stored, newest if old_answered is None else max(old_answered, newest))
    for (group, station), (stored, newest) in stations.items():
        if stored is None:
            stations[(group, station)] = (db.session.query(func.max(SensorMeasurement.recorded_at))
                                          .filter_by(group_type=group, station_id=station).scalar(), newest)
    return stations


def catch_up(start, rows, tz, now):
    """(where to fetch from again, the stations back as "Logger 2577533"), or (None, []): from the newest stored
    reading (minus the overlap, at most RUN_LOOKBACK ago) of each station that this answer, read from `start`,
    has newer readings from while its newest stored one is older than `start`. A logger out of contact resends what
    it missed when it reconnects; without this, all but the last few hours of that would never be fetched, and
    the start is set by the whole group, so one logger's silence doesn't move it while the others report."""
    gap_start, back = None, []
    for (group, station), (stored, answered) in sorted(stations_newest(rows).items()):
        if stored is not None and (answered <= stored or stored.replace(tzinfo=tz) >= start):
            continue   # nothing new, or its gap is inside this run's window
        own = max(start_from_newest(stored, tz, FIRST_START[group]), now - RUN_LOOKBACK)
        if own < start:
            back.append(f"{group} {station}")
            gap_start = own if gap_start is None else min(gap_start, own)
    return gap_start, back


def read_answer(source, parse, error=None, skipped=None):
    """Parse a vendor answer with parse(skipped) -> rows, then record the call's outcome for the alerts: `error` if
    the call failed, a failure if records came back but none could be read (the vendor changed its format, say),
    else success, noting any records skipped. Recorded only once the answer is read, so an answer we can't read is
    never reported as "vendor OK, check the sensor". Logs the skipped records in one line, also sent to Sentry as a
    warning when the call otherwise succeeded (a failed one goes there as the run's error). Returns (rows, the
    error to fail the run with, or None). `skipped` (a SkippedRecords) may be passed to keep counting into it
    afterwards."""
    skipped = SkippedRecords(source) if skipped is None else skipped
    try:
        rows = parse(skipped)
    except Exception as e:
        record_vendor_result(source, error or UnreadableRecords(f"{source}'s answer couldn't be read "
                                                                f"({type(e).__name__})"))
        raise
    skipped.report()
    if error is None and skipped.count and not rows:
        error = UnreadableRecords(f"none of {source}'s records could be read: {skipped.summary()}")
    record_vendor_result(source, error, skipped=skipped.summary())
    if error is None and skipped.count:
        capture_job_warning(f"{source}: skipped {skipped.summary()}")   # a no-op unless Sentry is on
    return rows, error


def inject_licor(tz, now):
    # One read of LI-COR covers both the weather station and the water-level loggers.
    start = licor_start(tz, now)
    try:
        records = fetch_range(weather_service.get_page, start, now)
    except Exception as e:
        record_vendor_result("LI-COR", e)
        raise
    skipped = SkippedRecords("LI-COR")
    rows, error = read_answer("LI-COR", lambda counter: licor_rows(
        records, {"Weather", "Logger"}, weather_service.get_logger_id(), tz, counter, now), skipped=skipped)
    if error is not None:
        raise error
    gap_start, back = catch_up(start, rows, tz, now)
    if gap_start is not None:
        # A silent station is back: fetch its gap too, before anything is stored or the mark moves.
        try:
            gap = fetch_range(weather_service.get_page, gap_start, start)
        except Exception as e:
            record_vendor_result("LI-COR", e)
            raise
        before = skipped.count
        gap_rows = licor_rows(gap, {"Weather", "Logger"}, weather_service.get_logger_id(), tz, skipped, now)
        if skipped.count > before:
            skipped.report()   # the run's total, now including the gap
            if not gap_rows:
                # Nothing in the gap could be read: fail as read_answer does, so nothing is stored, the mark stays
                # and the next run retries the backlog.
                error = UnreadableRecords(f"none of LI-COR's records from {gap_start:%Y-%m-%d %H:%M} to "
                                          f"{start:%Y-%m-%d %H:%M} UTC (a silent station's gap) could be read: "
                                          f"{skipped.summary()}")
                record_vendor_result("LI-COR", error)
                raise error
            record_vendor_result("LI-COR", skipped=skipped.summary())
        for key, row in gap_rows.items():
            rows.setdefault(key, row)
        print(f"[INFO] LI-COR: {', '.join(back)} reporting again; also fetched "
              f"{gap_start:%Y-%m-%d %H:%M} to {start:%Y-%m-%d %H:%M} UTC: {len(gap)} records")
        records = records + gap
        start = gap_start
    new = store(list(rows.values()))
    # Not past an unreadable record whose time is known: the next runs read it again, so it is stored once
    # utils/parsers.py is fixed, as long as that is within about a day (LICOR_LATE + LICOR_SILENT). Records in a wrong
    # unit don't hold it: a swapped sensor keeps sending them, and every run would reread about a day (9 times the
    # records, burning row ids). scripts/licor_backfill.py refills them once the unit is set.
    record_fetched_until("LI-COR", now if skipped.earliest is None else min(now, skipped.earliest))
    print(f"[INFO] LI-COR: {start:%Y-%m-%d %H:%M} to {now:%Y-%m-%d %H:%M} UTC: {len(records)} records, "
          f"{len(rows)} readings, {new} new")


def inject_quality(tz, now):
    # QualityService follows WQData's paging (until a response holds all the values it reports), so one call
    # covers the range.
    start = run_start("Quality", tz, now)
    entries = quality_service.get_quality_data(start.strftime(FMT), now.strftime(FMT))
    # get_quality_data logs a failed request or a paging stall and returns what it read
    rows, error = read_answer("WQData", lambda skipped: quality_rows(entries, Config.WQ_DEVICE_ID, tz, skipped, now),
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
