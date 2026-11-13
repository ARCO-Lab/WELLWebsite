"""The sensor series that exist: (group_type, station_id, measurement_type) for every series with a reading.

Requests name series, stations and measurements as free text. Checked against this set, a value that matches nothing
can be dropped before it does any work: /api/series leaves it out of the query and its cache key (so made-up values
can't mint new cache entries), and an export leaves it out of its columns (so a list of made-up station ids can't
make every CSV row megabytes wide).

The set comes from /api/latest's walk of the series index (one or two index probes per series), kept per process
and worked out again when sensor_measurements' newest id has changed, i.e. after ingestion has added readings. A
new series is therefore known as soon as its first reading is stored. A series whose readings were all deleted
stays known until the next reading arrives anywhere, which only means a value is checked and not dropped.
"""
import threading

from sqlalchemy import func

from db.database import db
from db.models import SensorMeasurement

_lock = threading.Lock()
_cached = {}  # database (URL without the password) -> (newest id when worked out, frozenset of series)


def known_series():
    """frozenset of (group_type, station_id, measurement_type) of every series with at least one reading."""
    from api.routes.latest import query_latest_per_series  # here, so importing this module doesn't load the routes

    newest = db.session.query(func.max(SensorMeasurement.id)).scalar()
    where = db.engine.url.render_as_string(hide_password=True)
    hit = _cached.get(where)
    if hit is not None and hit[0] == newest:
        return hit[1]
    series = frozenset((row["group_type"], str(row["station_id"]), row["measurement_type"])
                       for row in query_latest_per_series())
    with _lock:
        _cached[where] = (newest, series)
    return series


def forget():
    """Drops what is kept, so the next call reads the database again (for tests)."""
    with _lock:
        _cached.clear()
