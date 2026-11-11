# This file defines the /api/series route: sensor readings for charts, aggregated in PostgreSQL to about two
# thousand points per series, so any date range (even the whole history) loads in about a second.
#
# GET /api/series?start=<ISO>&end=<ISO>&group_type=Weather&group_type=Logger...
#     [&bucket=<seconds>] [&series=<group>|<station_id>|<measurement_type> ...]
#     [&station_id=<id> ...] [&measurement_type=<name> ...]
# -> {"bucket_seconds": 43200, "aggregated": true,
#     "series": [{"group_type", "station_id", "measurement_type", "unit", "agg",
#                 "t": [epoch ms, UTC], "avg": [...], "min": [...], "max": [...], "n": [...]}, ...]}
#
# start/end: an ISO time with an offset (e.g. ...Z) is a real instant; one without is local wall-clock time.
# recorded_at is stored as naive America/Toronto wall-clock time (utils/timezone.py), so buckets follow local time
# (daily buckets are local days) and `t` is each bucket start converted to a real instant. The zone is named in the
# SQL, so the result doesn't depend on the database session's TimeZone setting.
#
# `agg` says what each series' `avg` holds:
#   "mean"        the mean of the readings in the bucket; min/max are the smallest and largest reading.
#   "sum"         (Rain) the bucket's total, since the gauge reports mm per interval; min/max are still the
#                 smallest and largest single reading, not totals.
#   "vector_mean" (Wind Direction) the mean of the directions as unit vectors, so 350° and 10° give 0°, not 180°;
#                 min/max are null, because a linear min/max of angles (10° and 350° for a northerly) means nothing.
# `n` is how many readings each bucket holds (sensors report every 10 minutes, so a full 1-hour bucket has 6); charts
# use it to mark buckets that are mostly gaps. Readings at or below the vendors' "no reading" sentinel (-100000,
# utils/parsers.SENTINEL_MAX) or not finite are left out: older rows were stored before ingestion skipped them.
#
# bucket: a size from LADDER, for charts that pick their own resolution (each chart loads fixed tiles of a few
# hundred buckets; see the dashboard's src/lib/seriesLoader.ts). Without it the bucket is picked from the span
# (pick_bucket). Either way a request for more than MAX_BUCKETS buckets per series is refused with a 400.
# series, station_id, measurement_type: only these series, so one chart fetches only what it draws. `series` names
# whole series ("Logger|2577531|Water Temperature") and stands in for group_type; station_id and measurement_type
# narrow the groups asked for. Each can be repeated, up to MAX_FILTERS values.
#
# Caching: start is rounded up and end down to a 10-minute mark. Readings fall on those marks, so this selects the
# same readings as the request (no bucket is added at either edge), while visitors who open the same view a few
# minutes apart share one cache key. (A chart's tiles start and end on bucket edges, so for them this changes
# nothing.) The answer is kept in Redis (utils/response_cache.py) for an hour for a range that ended over a day ago,
# 5 minutes for one that ended over an hour ago, 1 minute otherwise. Browsers may keep an answer for a range that ended over a day ago for a day, as
# "immutable" (readings that old don't change, so a chart scrolling back over them asks for nothing), and any other
# for a minute at most, and no longer than the cached copy has left.

from datetime import datetime, timedelta

from flask import current_app, jsonify, request
from sqlalchemy import text

from db.database import db
from utils import response_cache
from utils.parsers import SENTINEL_MAX
from utils.timezone import EST_TZ

# Bucket sizes, smallest first. Every sensor reports every 10 minutes, so 600 s is the raw resolution.
LADDER = (600, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 24 * 3600)
MAX_POINTS = 2000
GROUPS = {"Weather", "Quality", "Logger"}
AGG = {"Rain": "sum", "Wind Direction": "vector_mean"}  # every other measurement: "mean"
LOCAL_ZONE = EST_TZ.key  # 'America/Toronto', the zone recorded_at is stored in
SNAP = timedelta(minutes=10)
RECENT = timedelta(hours=1)  # a range ending less long ago than this is still filling in, so reuse it briefly
MAX_AGE_RECENT, MAX_AGE_PAST, MAX_AGE_SETTLED = 60, 300, 3600  # seconds the shared cache keeps a response
SETTLED = timedelta(days=1)  # a range that ended longer ago than this is complete
BROWSER_SETTLED = "public, max-age=86400, immutable"
BROWSER_MAX_AGE = 60  # seconds browsers may reuse an answer for any other range
MAX_BUCKETS = 4000  # the most buckets per series one request may ask for (span / bucket)
MAX_FILTERS = 40  # values per filter parameter

SQL = text(f"""
WITH b AS (
  SELECT group_type, station_id, measurement_type, unit, value,
         to_timestamp(floor(extract(epoch FROM recorded_at) / :b) * :b) AT TIME ZONE 'UTC' AS bucket_local
  FROM sensor_measurements
  WHERE recorded_at BETWEEN :s AND :e AND group_type = ANY(:g) AND value IS NOT NULL
        AND value > {SENTINEL_MAX} AND value < 'Infinity'::float8  -- PostgreSQL sorts NaN above Infinity
        -- Optional filters (NULL: all). The two lists let the index on (group_type, station_id, measurement_type,
        -- recorded_at) narrow the scan; the key list then keeps only the exact series asked for.
        AND (CAST(:st AS text[]) IS NULL OR station_id = ANY(CAST(:st AS text[])))
        AND (CAST(:m AS text[]) IS NULL OR measurement_type = ANY(CAST(:m AS text[])))
        AND (CAST(:k AS text[]) IS NULL
             OR group_type || '|' || station_id || '|' || measurement_type = ANY(CAST(:k AS text[])))
)
SELECT group_type, station_id, measurement_type, unit,
       (extract(epoch FROM (bucket_local AT TIME ZONE '{LOCAL_ZONE}')) * 1000)::bigint AS t,
       CASE WHEN measurement_type = 'Rain' THEN sum(value)
            WHEN measurement_type = 'Wind Direction'
              THEN mod((degrees(atan2(avg(sin(radians(value))), avg(cos(radians(value))))) + 360)::numeric, 360)::float
            ELSE avg(value) END AS v,
       CASE WHEN measurement_type = 'Wind Direction' THEN NULL ELSE min(value) END AS lo,
       CASE WHEN measurement_type = 'Wind Direction' THEN NULL ELSE max(value) END AS hi,
       count(value) AS n
FROM b
GROUP BY group_type, station_id, measurement_type, unit, bucket_local
ORDER BY group_type, station_id, measurement_type, unit, bucket_local
""")


def pick_bucket(span_seconds, max_points=MAX_POINTS):
    """The smallest bucket that gives a series of this span about max_points points or fewer.

    Bucket edges don't line up with the range, so a series can get one point more than span / bucket. Spans
    longer than max_points days (about 5.5 years for 2,000) get daily buckets, the coarsest, and more points.
    """
    for bucket in LADDER:
        if span_seconds / bucket <= max_points:
            return bucket
    return LADDER[-1]


def floor_mark(t):
    """`t` rounded down to a 10-minute mark."""
    return t - timedelta(minutes=t.minute % 10, seconds=t.second, microseconds=t.microsecond)


def snap_range(start, end):
    """The range narrowed to 10-minute marks: start rounded up, end rounded down (unchanged if already on one).
    A range with no mark inside comes out with start after end, which matches nothing, as the request would."""
    start_up = floor_mark(start)
    if start_up != start:
        try:
            start_up += SNAP
        except OverflowError:  # within 10 minutes of datetime.max
            start_up = start
    return start_up, floor_mark(end)


def max_age(end, now):
    """How long the shared cache keeps an answer for a range ending at `end`; both are naive local times."""
    if end < now - SETTLED:
        return MAX_AGE_SETTLED  # complete: every visitor's charts share it (e.g. the slider's daily history)
    return MAX_AGE_PAST if end < now - RECENT else MAX_AGE_RECENT


def browser_cache_control(end, now, seconds_left=None):
    """Cache-Control for a range ending at `end` (naive local times, like `now`): a day, immutable, once the range
    ended over a day ago; otherwise a minute, or what is left of the shared cache's copy if that is less."""
    if end < now - SETTLED:
        return BROWSER_SETTLED
    age = BROWSER_MAX_AGE if seconds_left is None else min(BROWSER_MAX_AGE, seconds_left)
    return f"public, max-age={age}"


def cache_key(bucket, start, end, groups, filters=None):
    """Everything the answer depends on: the query's parameters, after snap_range."""
    parts = [f"series:v3:{bucket}:{start.isoformat()}:{end.isoformat()}:{','.join(sorted(set(groups)))}"]
    for name in ("st", "m", "k"):
        values = (filters or {}).get(name)
        parts.append(",".join(sorted(set(values))) if values else "*")
    return "|".join(parts)


def parse_filters(args):
    """A request's series filters -> ({"st", "m", "k"}: a list, or None for no filter; the groups the series keys
    name). Raises ValueError, with the message for the 400, for a malformed key or too many values."""
    filters = {}
    for name, param in (("st", "station_id"), ("m", "measurement_type"), ("k", "series")):
        values = [v for v in args.getlist(param) if v]
        if len(values) > MAX_FILTERS:
            raise ValueError(f"At most {MAX_FILTERS} values for {param}")
        filters[name] = values or None
    keys = [k.split("|") for k in filters["k"] or []]
    if any(len(k) != 3 or k[0] not in GROUPS or not k[1] or not k[2] for k in keys):
        raise ValueError("series must look like Weather|<station_id>|<measurement_type>")
    if keys:
        # The stations and measurements the keys name, so the index narrows the scan to them too
        if filters["st"] is None:
            filters["st"] = sorted({k[1] for k in keys})
        if filters["m"] is None:
            filters["m"] = sorted({k[2] for k in keys})
    return filters, sorted({k[0] for k in keys})


def parse_bucket(value):
    """The bucket a request asks for (seconds), or None; ValueError unless it is one of LADDER."""
    if value is None or value == "":
        return None
    bucket = int(value) if value.isdigit() else None
    if bucket not in LADDER:
        raise ValueError(f"bucket must be one of {', '.join(str(b) for b in LADDER)} (seconds)")
    return bucket


def parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def local_naive(parsed):
    """A parsed time as naive local wall-clock time, to compare with recorded_at: aware times are converted to
    America/Toronto, naive ones are taken as local already."""
    return parsed.astimezone(EST_TZ).replace(tzinfo=None) if parsed.tzinfo else parsed


def to_local_naive(value):
    return local_naive(parse_iso(value))


def _num(x):
    return None if x is None else round(float(x), 4)


def columnar(rows):
    """Query rows -> one {metadata, agg, t, avg, min, max, n} object per series, in row order."""
    series, out = {}, []
    for g, station, measurement, unit, t, v, lo, hi, n in rows:
        key = (g, station, measurement, unit)
        s = series.get(key)
        if s is None:
            s = series[key] = {"group_type": g, "station_id": station, "measurement_type": measurement,
                               "unit": unit, "agg": AGG.get(measurement, "mean"),
                               "t": [], "avg": [], "min": [], "max": [], "n": []}
            out.append(s)
        s["t"].append(int(t))
        s["avg"].append(_num(v))
        s["min"].append(_num(lo))
        s["max"].append(_num(hi))
        s["n"].append(int(n))
    return out


def register_series_route(app):
    @app.route("/api/series", methods=["GET"])
    def get_series():
        start, end = request.args.get("start"), request.args.get("end")
        try:
            filters, key_groups = parse_filters(request.args)
            asked_bucket = parse_bucket(request.args.get("bucket"))
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        groups = sorted({g for g in request.args.getlist("group_type") if g in GROUPS} | set(key_groups))
        if not start or not end or not groups:
            return jsonify({"error": "Missing required parameters: start, end and at least one group_type"}), 400
        try:
            start_in, end_in = parse_iso(start), parse_iso(end)
            start_dt, end_dt = local_naive(start_in), local_naive(end_in)
        except (ValueError, OverflowError):  # OverflowError: e.g. 0001-01-01T00:00+05:00 has no local time
            return jsonify({"error": "Invalid date format"}), 400
        if start_in.tzinfo and end_in.tzinfo:
            # Two real instants: compare those. Their wall-clock times can run backwards inside the hour repeated
            # when clocks fall back (05:30Z -> 01:30 EDT, 06:10Z -> 01:10 EST), so the naive bounds are put in
            # order for the query. recorded_at keeps one naive 01:xx per reading, so that hour is approximate.
            if end_in <= start_in:
                return jsonify({"error": "end must be after start"}), 400
            span = (end_in - start_in).total_seconds()
            start_dt, end_dt = min(start_dt, end_dt), max(start_dt, end_dt)
        else:
            if end_dt <= start_dt:
                return jsonify({"error": "end must be after start"}), 400
            span = (end_dt - start_dt).total_seconds()

        bucket = asked_bucket or pick_bucket(span)
        if span / bucket > MAX_BUCKETS:
            return jsonify({"error": f"That is more than {MAX_BUCKETS} points per series: pick a shorter range or a "
                                     "larger bucket."}), 400
        now = datetime.now(EST_TZ).replace(tzinfo=None)
        age = max_age(end_dt, now)
        start_dt, end_dt = snap_range(start_dt, end_dt)
        key = cache_key(bucket, start_dt, end_dt, groups, filters)
        hit = response_cache.get(key)
        seconds_left = None
        if hit is not None:
            body, seconds_left = hit
            response = current_app.response_class(body, mimetype="application/json")
        else:
            db.session.execute(text("SET LOCAL work_mem = '64MB'"))  # keeps the GROUP BY sort in memory (~3x faster)
            rows = db.session.execute(SQL, {"b": bucket, "s": start_dt, "e": end_dt, "g": groups, **filters}).fetchall()
            response = jsonify({"bucket_seconds": bucket, "aggregated": bucket > LADDER[0], "series": columnar(rows)})
            response_cache.put(key, response.get_data(), age)
        response.headers["Cache-Control"] = browser_cache_control(end_dt, now, seconds_left)
        return response
