"""The sensor series that exist: (group_type, station_id, measurement_type) for every series with a reading.

Requests name series, stations and measurements as free text. Checked against this set, a value that matches nothing
can be dropped before it does any work: /api/series leaves it out of the query and its cache keys (so made-up values
can't mint new cache entries), and an export leaves it out of its columns (so a list of made-up station ids can't
make every CSV row megabytes wide). /api/series also uses it to list the series a tile request covers, so it can
cache each one on its own.

The set comes from /api/latest's walk of the series index (one or two index probes per series) and is kept per
process. At most every REFRESH_S it checks sensor_measurements' newest id, one index probe, and works the set out
again if that changed, i.e. after ingestion has added readings. A new series is therefore known within REFRESH_S of
its first reading. If the check fails (the database is down), the last set is kept, so requests the cache can answer
still work; only a process that never read the set has to fail. A series whose readings were all deleted stays known
until the next reading arrives anywhere, which only means a value is checked and not dropped.
"""
import logging
import threading
import time

from sqlalchemy import func

from db.database import db
from db.models import SensorMeasurement

log = logging.getLogger(__name__)

REFRESH_S = 30
_lock = threading.Lock()
# database (URL without the password) -> (newest id when worked out, frozenset of series, time.monotonic() checked)
_cached = {}


def known_series():
    """frozenset of (group_type, station_id, measurement_type) of every series with at least one reading."""
    from api.routes.latest import query_latest_per_series  # here, so importing this module doesn't load the routes

    where = db.engine.url.render_as_string(hide_password=True)
    hit = _cached.get(where)
    now = time.monotonic()
    if hit is not None and now - hit[2] < REFRESH_S:
        return hit[1]
    try:
        newest = db.session.query(func.max(SensorMeasurement.id)).scalar()
        if hit is not None and hit[0] == newest:
            series = hit[1]
        else:
            series = frozenset((row["group_type"], str(row["station_id"]), row["measurement_type"])
                               for row in query_latest_per_series())
    except Exception as exc:
        if hit is None:
            raise
        db.session.rollback()  # the failed query may have left the session's transaction unusable
        log.warning("series catalog not refreshed (%s); using the last known set", type(exc).__name__)
        with _lock:
            _cached[where] = (hit[0], hit[1], now)  # don't try again on every request while the database is down
        return hit[1]
    with _lock:
        _cached[where] = (newest, series, now)
    return series


def forget():
    """Drops what is kept, so the next call reads the database again (for tests)."""
    with _lock:
        _cached.clear()
