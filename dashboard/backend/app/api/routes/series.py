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
# bucket: a size from LADDER, for charts that pick their own resolution. A request with a bucket asks for whole
# tiles (see the dashboard's src/lib/seriesTiles.ts): a tile is TILE_BUCKETS buckets, and tiles start at multiples
# of their length counted on Toronto's wall clock from 1970-01-01T00:00. start must be a tile's start and end a later
# tile's start or one second before it (what the dashboard sends), as times without an offset; at most MAX_TILES
# tiles. Anything else gets a 400 (check_tiles). Without a bucket, the bucket is picked from the span (pick_bucket)
# and any range is accepted; either way a request for more than MAX_BUCKETS buckets per series is refused with a 400.
# start and end must fall in the years utils/timezone.FIRST_YEAR to LAST_YEAR.
# series, station_id, measurement_type: only these series, so one chart fetches only what it draws. `series` names
# whole series ("Logger|2577531|Water Temperature") and stands in for group_type; station_id and measurement_type
# narrow the groups asked for. Each can be repeated, up to MAX_FILTERS values; a value may not contain "," or "|"
# (no station or measurement name does, and a key is split on "|"), nor a control character (api/validation.py).
# Values that name no existing series (api/services/catalog.py) are dropped before anything else, so they cost no
# query and no cache entry; a filter left with no values matches nothing, and the answer is an empty list of series.
#
# Caching: only tile requests use Redis (utils/response_cache.py), and they store each series' part of each tile on
# its own, under (bucket, tile start, series) (tile_cache_key). A request lists the series it covers (from
# api/services/catalog.py, narrowed by its groups and filters), reads all their tile entries in one round trip,
# queries only the series and tiles that are missing, stores those, and builds the answer from the entries. So the
# number of keys is bounded by series x tiles, however the series are combined in requests: a dashboard card asks
# for its series together, and another card or a made-up combination of the same series reuses their entries. An
# entry is kept for an hour once its tile ended over a day ago, 5 minutes once it ended over an hour ago, 1 minute
# otherwise; an empty entry for a minute only. A tile that ends before its group's earliest reading or starts after
# now is answered empty with no query, no Redis read and no entry, so asking for years without data fills nothing.
# A series that is new since the catalog was last read (at most catalog.REFRESH_S ago) is missing from the answer
# until then.
# Requests without a bucket are never stored: they can be any range, shifted a few minutes at a time, so storing them
# would let anyone fill Redis. The dashboard asks for tiles only; the bucket-less form is for scripts such as the load
# test, and the dashboard's proxy counts it as a slow request (lib/rateLimit.ts). Its start is rounded up and its end
# down to a 10-minute mark, where readings fall, so it selects the same readings.
# Browsers may keep an answer for a range that ended over a day ago for BROWSER_SETTLED_AGE, and any other for a
# minute at most, and no longer than the cached copies have left (see browser_cache_control).

import hashlib
import json
from datetime import datetime, timedelta, timezone

from flask import current_app, jsonify, request
from sqlalchemy import text

from api.services.catalog import earliest_readings, known_series
from api.validation import bad_text
from db.database import db
from utils import response_cache
from utils.parsers import SENTINEL_MAX
from utils.timezone import EST_TZ, check_site_years, iso_time

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
BROWSER_SETTLED_AGE = 3 * 3600  # seconds browsers may reuse an answer for a range that ended over a day ago
BROWSER_MAX_AGE = 60  # seconds browsers may reuse an answer for any other range
MAX_BUCKETS = 4000  # the most buckets per series one request may ask for (span / bucket)
MAX_FILTERS = 40  # values per filter parameter
TILE_BUCKETS = 360  # buckets per tile (the dashboard's TILE_BUCKETS, src/lib/seriesTiles.ts)
MAX_TILES = 8  # tiles per request (the dashboard's MAX_BATCH, src/lib/seriesLoader.ts)
WALL_EPOCH = datetime(1970, 1, 1)  # tiles are counted on the wall clock from here
ONE_SECOND = timedelta(seconds=1)

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


def tile_start(t, bucket):
    """The start of the tile of `bucket` buckets that the naive wall-clock time `t` falls in."""
    tile = timedelta(seconds=TILE_BUCKETS * bucket)
    return t - (t - WALL_EPOCH) % tile


def whole_buckets(start, end, bucket):
    """A range (naive wall-clock times) widened to whole buckets: start back to its bucket's start, end on to one
    second before the next bucket's, so every range within the same buckets shares one cache key (/api/windrose)."""
    size = timedelta(seconds=bucket)
    first = start - (start - WALL_EPOCH) % size
    last = end - (end - WALL_EPOCH) % size + size - ONE_SECOND
    return first, last


def check_tiles(start, end, bucket):
    """A tile request's range (naive wall-clock times) -> (start, end), with an end on a tile's start moved to one
    second before it, so both ways of asking for the same tiles share a cache key. ValueError, with the message for
    the 400, unless start is a tile's start, end is a later tile's start or one second before it, and the range is
    at most MAX_TILES tiles."""
    tile = timedelta(seconds=TILE_BUCKETS * bucket)
    end_edge = end + ONE_SECOND if (end + ONE_SECOND - WALL_EPOCH) % tile == timedelta(0) else end
    on_edges = not (start - WALL_EPOCH) % tile and not (end_edge - WALL_EPOCH) % tile
    if not on_edges or not tile <= end_edge - start <= MAX_TILES * tile:
        raise ValueError(f"With bucket={bucket}, start and end must be the edges of 1 to {MAX_TILES} whole tiles of "
                         f"{TILE_BUCKETS} buckets (e.g. start={tile_start(start, bucket).isoformat()}).")
    return start, end_edge - ONE_SECOND


def max_age(end, now):
    """How long the shared cache keeps an answer for a range ending at `end`; both are naive local times."""
    if end < now - SETTLED:
        return MAX_AGE_SETTLED  # complete: every visitor's charts share it (e.g. the slider's daily history)
    return MAX_AGE_PAST if end < now - RECENT else MAX_AGE_RECENT


def browser_cache_control(end, now, seconds_left=None):
    """Cache-Control for a range ending at `end` (naive local times, like `now`): BROWSER_SETTLED_AGE once the range
    ended over a day ago; otherwise a minute, or what is left of the shared cache's copy if that is less.

    Readings over a day old rarely change, so a chart panning back over them can reuse what it fetched. They can
    change, though: a backfill fills a gap, or a cleanup removes bad values. So not "immutable" and not for a day: a
    few hours, after which the browser asks again (and usually gets the copy in Redis), is the trade-off between
    requests saved while someone explores the charts and how long a corrected range can look stale."""
    if end < now - SETTLED:
        return f"public, max-age={BROWSER_SETTLED_AGE}"
    age = BROWSER_MAX_AGE if seconds_left is None else min(BROWSER_MAX_AGE, seconds_left)
    return f"public, max-age={age}"


def tile_cache_key(bucket, start, series):
    """The cache key of one series' part of the tile of `bucket` buckets starting at `start` (naive wall-clock time);
    `series` is (group_type, station_id, measurement_type). A hash of their JSON: an unambiguous encoding, so no
    series can produce another's key (joining values with separators let a single value containing one stand for
    two)."""
    parts = [bucket, start.isoformat(), list(series)]
    return "series:tile:v1:" + hashlib.sha256(json.dumps(parts).encode()).hexdigest()


def _bytewise(series):
    return tuple(part.encode() for part in series)


def covered_series(groups, filters):
    """The series (group_type, station_id, measurement_type) a request covers: those in the catalog in its groups
    that every filter it has allows, in byte order of their names."""
    st, m, k = (set(filters[name]) if filters.get(name) else None for name in ("st", "m", "k"))
    return sorted((s for s in known_series() if s[0] in groups and (st is None or s[1] in st)
                   and (m is None or s[2] in m) and (k is None or "|".join(s) in k)), key=_bytewise)


def _tile_of(t_ms, bucket):
    """The start of the tile (naive wall-clock time) a row's bucket time `t` (epoch ms, as the query returns it)
    falls in. Converting the instant back to wall-clock time gives the bucket's naive start again, also inside the
    hour repeated when clocks fall back."""
    local = datetime.fromtimestamp(t_ms / 1000, timezone.utc).astimezone(EST_TZ).replace(tzinfo=None)
    return tile_start(local, bucket)


ARRAYS = ("t", "avg", "min", "max", "n")


def tile_entry(pieces):
    """One series' part of one tile, as stored: columnar()'s objects for it (one per unit, usually one), each with its
    arrays as JSON text without the brackets. Building the answer then joins text instead of parsing and writing
    every number again, which for 8 tiles of 25 series (2.7 MB) took about 0.2 s of CPU per cached request."""
    return json.dumps([{"head": {k: v for k, v in p.items() if k not in ARRAYS},
                        **{f: json.dumps(p[f], separators=(",", ":"))[1:-1] for f in ARRAYS}} for p in pieces],
                      separators=(",", ":")).encode()


def series_json(series_pieces):
    """The JSON text of one series object of the answer, from its tiles' stored pieces in time order (all of one
    unit): its head, then each array with the tiles' parts joined."""
    head = json.dumps(series_pieces[0]["head"], separators=(",", ":"))[:-1]
    arrays = ",".join(f'"{f}":[' + ",".join(p[f] for p in series_pieces if p[f]) + "]" for f in ARRAYS)
    return f"{head},{arrays}}}"


def tile_answer(bucket, start, end, series, now):
    """The JSON text of the `series` list of a tile request's answer (tiles of `bucket` from `start` to `end`, from
    check_tiles) built from the per-series tile entries (see "Caching" at the top), and the fewest seconds any entry
    read from Redis has left (None when none was)."""
    size = timedelta(seconds=TILE_BUCKETS * bucket)
    tiles = []
    t = start
    while t <= end:
        tiles.append(t)
        t += size
    # A tile that ends before its group's earliest reading, or starts after now, can hold nothing: it is answered
    # empty, with no query and no cache entry, so asking for years without data costs nothing and fills nothing.
    earliest = earliest_readings()
    parts = {(tile, s): [] for tile in tiles for s in series
             if s[0] not in earliest or tile + size - ONE_SECOND < earliest[s[0]] or tile > now}
    keys = {(tile, s): tile_cache_key(bucket, tile, s) for tile in tiles for s in series if (tile, s) not in parts}
    stored = response_cache.get_many(list(keys.values()))
    parts.update({pair: json.loads(stored[key][0]) for pair, key in keys.items() if key in stored})  # numbers: text
    left = min((hit[1] for hit in stored.values()), default=None)

    missing = [pair for pair in keys if pair not in parts]
    if missing:
        want = sorted({s for _, s in missing}, key=_bytewise)
        first = min(tile for tile, _ in missing)
        last = max(tile for tile, _ in missing) + size - ONE_SECOND
        db.session.execute(text("SET LOCAL work_mem = '64MB'"))  # keeps the GROUP BY sort in memory (~3x faster)
        rows = db.session.execute(SQL, {
            "b": bucket, "s": first, "e": last, "g": sorted({s[0] for s in want}),
            "st": sorted({s[1] for s in want}), "m": sorted({s[2] for s in want}), "k": ["|".join(s) for s in want],
        }).fetchall()
        by_pair = {}
        for row in rows:
            by_pair.setdefault((_tile_of(row[4], bucket), tuple(row[:3])), []).append(row)
        to_store = []
        for pair in missing:
            pieces = columnar(by_pair.get(pair, []))
            body = tile_entry(pieces)
            parts[pair] = json.loads(body)
            # An empty one is stored too, so it isn't asked for again, but only briefly: it is a key that real data
            # never needs, and readings may yet arrive (a backfill)
            ttl = max_age(pair[0] + size - ONE_SECOND, now) if pieces else MAX_AGE_RECENT
            to_store.append((keys[pair], body, ttl))
        response_cache.put_many(to_store)

    out = []
    for s in series:
        by_unit = {}
        for tile in tiles:
            for piece in parts[(tile, s)]:
                by_unit.setdefault(piece["head"]["unit"], []).append(piece)
        out.extend(series_json(by_unit[unit]) for unit in sorted(by_unit, key=lambda u: (u or "").encode()))
    return "[" + ",".join(out) + "]", left


def parse_filters(args):
    """A request's series filters -> ({"st", "m", "k"}: a list, or None for no filter; the groups the series keys
    name). Raises ValueError, with the message for the 400, for a malformed key or too many values, and for control
    characters in group_type too (unknown groups are dropped, but such text is refused as on every route)."""
    if any(bad_text(g) for g in args.getlist("group_type")):
        raise ValueError("group_type values may not contain control characters")
    filters = {}
    for name, param in (("st", "station_id"), ("m", "measurement_type"), ("k", "series")):
        values = [v for v in args.getlist(param) if v]
        if len(values) > MAX_FILTERS:
            raise ValueError(f"At most {MAX_FILTERS} values for {param}")
        if any(bad_text(v) for v in values):
            raise ValueError(f"{param} values may not contain control characters")
        if name != "k" and any("," in v or "|" in v for v in values):
            raise ValueError(f"{param} values may not contain ',' or '|'")
        filters[name] = values or None
    keys = [k.split("|") for k in filters["k"] or []]
    if any(len(k) != 3 or k[0] not in GROUPS or not k[1] or not k[2] or "," in k[1] + k[2] for k in keys):
        raise ValueError("series must look like Weather|<station_id>|<measurement_type>")
    if keys:
        # The stations and measurements the keys name, so the index narrows the scan to them too
        if filters["st"] is None:
            filters["st"] = sorted({k[1] for k in keys})
        if filters["m"] is None:
            filters["m"] = sorted({k[2] for k in keys})
    return filters, sorted({k[0] for k in keys})


def known_filters(filters):
    """`filters` (from parse_filters) without the values that name no existing series (api/services/catalog.py),
    and whether a filter that had values is left with none (so the request matches nothing)."""
    if not any(filters.values()):
        return filters, False
    series = known_series()
    known = {"st": {s for _, s, _ in series}, "m": {m for _, _, m in series}, "k": {"|".join(s) for s in series}}
    kept = {name: [v for v in values if v in known[name]] if values else values for name, values in filters.items()}
    return kept, any(filters[name] and not kept[name] for name in filters)


def parse_bucket(value):
    """The bucket a request asks for (seconds), or None; ValueError unless it is one of LADDER."""
    if value is None or value == "":
        return None
    bucket = int(value) if value.isascii() and value.isdigit() else None  # isdigit alone also takes "²"
    if bucket not in LADDER:
        raise ValueError(f"bucket must be one of {', '.join(str(b) for b in LADDER)} (seconds)")
    return bucket


def parse_iso(value):
    return iso_time(value)


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
        try:
            check_site_years(start_dt, end_dt)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
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

        if asked_bucket:
            try:
                start_dt, end_dt = check_tiles(start_dt, end_dt, asked_bucket)
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
            except OverflowError:  # a tile past datetime's last year; check_site_years keeps requests well short
                return jsonify({"error": "Invalid date range"}), 400
        bucket = asked_bucket or pick_bucket(span)
        if span / bucket > MAX_BUCKETS:
            return jsonify({"error": f"That is more than {MAX_BUCKETS} points per series: pick a shorter range or a "
                                     "larger bucket."}), 400
        now = datetime.now(EST_TZ).replace(tzinfo=None)
        filters, matches_nothing = known_filters(filters)
        if matches_nothing:
            # Nothing to look up, and nothing worth keeping in the cache
            response = jsonify({"bucket_seconds": bucket, "aggregated": bucket > LADDER[0], "series": []})
            response.headers["Cache-Control"] = browser_cache_control(end_dt, now, BROWSER_MAX_AGE)
            return response
        seconds_left = None
        if asked_bucket:
            series, seconds_left = tile_answer(bucket, start_dt, end_dt, covered_series(groups, filters), now)
            body = (f'{{"aggregated":{json.dumps(bucket > LADDER[0])},"bucket_seconds":{bucket},'
                    f'"series":{series}}}\n')
            response = current_app.response_class(body, mimetype="application/json")
        else:
            # Never stored (see "Caching" at the top)
            start_dt, end_dt = snap_range(start_dt, end_dt)
            db.session.execute(text("SET LOCAL work_mem = '64MB'"))  # keeps the GROUP BY sort in memory (~3x faster)
            rows = db.session.execute(SQL, {"b": bucket, "s": start_dt, "e": end_dt, "g": groups, **filters}).fetchall()
            response = jsonify({"bucket_seconds": bucket, "aggregated": bucket > LADDER[0], "series": columnar(rows)})
        response.headers["Cache-Control"] = browser_cache_control(end_dt, now, seconds_left)
        return response
