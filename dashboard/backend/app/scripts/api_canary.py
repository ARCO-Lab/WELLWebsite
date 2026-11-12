# Daily check that each vendor API still accepts our credentials and still answers in the shape ingestion reads.
# Run by .github/workflows/canary.yml once a day; by hand from dashboard/backend: python app/scripts/api_canary.py
#
# Makes a few small requests per data source, so it stays far inside every quota:
#  - LI-COR (HOBOlink): the last few hours for the station's logger (weather and water-level sensors).
#  - WQData: the last few hours of one device. WQData's hourly request quota is shared with the 10-minute
#    ingestion, so this is a single request with no paging and no retries. Only when it holds no points does the
#    canary look further back (one day per request, at most a week) for the newest point, so the failure says
#    when the device stopped reporting.
#  - Borealis: first the token (/api/users/:me), then the metadata of each dataset (the one downloads read and the
#    one uploads add to), so a rejected token and a dataset the token can't see give different messages.
# Prints one line per source (OK or FAIL with the HTTP status and a reason) and exits 1 if any failed.
# Never prints URLs, tokens, keys or response bodies: WQData takes its key in the query string, and requests'
# error text includes the full URL, so errors are reported as exception type and HTTP status only. The one
# exception is the Borealis host name (e.g. demo.borealisdata.ca), which says which server a token was tried on.
# Persistent ids are named by their variable, not printed: in CI they are secrets, and GitHub drops a job output
# that contains a secret's value, which would leave the issue without the result lines.

import math
import sys
import pathlib
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import requests

from config import Config
from api.services.quality import describe_request_error
from utils.borealis import base_url, is_demo

WINDOW = timedelta(hours=6)    # recent enough to be cheap, long enough that a slow upload still shows data
TIMEOUT = (10, 60)
# Looking back for WQData's newest point, only after an empty window: one day per request (about 2,700 values, so
# one page of WQData's ~5,000), newest day first, stopping at the first day with points. The shorter timeout keeps
# a week of slow answers inside the workflow step's timeout.
LOOKBACK_DAYS = 7
LOOKBACK_TIMEOUT = (10, 20)
WQ_PAUSE_S = 3.5          # WQData throttles bursts of requests (as QualityService.PAGE_PAUSE_S)
sleep = time.sleep        # replaced in tests
FMT = "%Y-%m-%d %H:%M:%S"

# Copies of the values in utils/parsers.py, which can't be imported here without the database packages
# (the workflow installs only requests). tests/test_api_canary.py checks they still match.
LOGGER_PREFIX = "2216865"                                                    # parsers.LOGGER_PREFIX
LOGGER_SERIALS = {"22168653", "22168654", "22168655", "22168656", "22168657"}  # parsers.LOGGER_CONFIG keys
WQ_PARAMETER_IDS = {125001, 125002, 125004, 125005, 125006, 125007, 125008, 125009}  # parsers.QUALITY_PARAM_ID_MAP
WEATHER_UNITS = {                                                            # parsers.WEATHER_UNITS
    "Air Temperature": "°C", "Soil Temperature": "°C", "Dew Point": "°C", "Relative Humidity": "%",
    "Pressure": "mbar", "Rain": "mm", "Solar Radiation": "W/m²", "Water Content": "m³/m³",
    "Wind Speed": "m/s", "Gust Speed": "m/s", "Wind Direction": "°",
}
LOGGER_UNITS = {"1": "m", "3": "°C"}                                         # parsers.LOGGER_UNITS
SENTINEL_MAX = -99999                                                         # parsers.SENTINEL_MAX
UNIT_ALIASES = {"m": {"meters", "meter", "metres", "metre"}}                 # parsers.UNIT_ALIASES
WEATHER_SENSOR_NAMES = {"21948438-1": "Air Temperature", "21948438-2": "Relative Humidity",  # utils/sensor_names.py
                        "22154270-1": "Soil Temperature"}


class ShapeError(Exception):
    """The response parsed, but not in the shape ingestion depends on."""


class NoRecentData(ShapeError):
    """WQData answered in the expected shape, but with no points in the window."""


# ---- Shape checks: pure functions on a parsed response body. Each returns a short summary or raises ShapeError.

def licor_record_used(sensor_sn):
    """Whether ingestion (parsers.licor_rows) parses a record with this serial, rather than skipping it:
    battery channels ("-B") are skipped, and so are logger channels whose base serial isn't a known logger."""
    if sensor_sn.endswith("-B"):
        return False
    if sensor_sn.startswith(LOGGER_PREFIX):
        parts = sensor_sn.split("-")
        return len(parts) == 2 and parts[0] in LOGGER_SERIALS
    return True


def has_number(value):
    """Whether ingestion (parsers.reading_value) stores this value: a finite number, not a boolean, above the
    vendors' "no reading" sentinel."""
    if value is None or isinstance(value, bool):
        return False
    try:
        number = float(value)
        return math.isfinite(number) and number > SENTINEL_MAX
    except (TypeError, ValueError, OverflowError):
        return False


def expected_unit(record):
    """The unit ingestion requires for this record (parsers.unit_mismatch), or None when it doesn't check one."""
    sensor_sn = record["sensor_sn"]
    if sensor_sn.startswith(LOGGER_PREFIX):
        return LOGGER_UNITS.get(sensor_sn.partition("-")[2])
    return WEATHER_UNITS.get(WEATHER_SENSOR_NAMES.get(sensor_sn, record.get("sensor_measurement_type")))


def same_unit(unit, expected):
    """Whether LI-COR's unit names the expected one, as ingestion judges it (parsers.same_unit)."""
    if not isinstance(unit, str):
        return False
    unit = unit.strip()
    return unit == expected or unit.casefold() in UNIT_ALIASES.get(expected, ())


def check_licor(body):
    # inject_from_api.py reads body["data"], and per record sensor_sn; for the records it doesn't skip, it also
    # parses timestamp (ISO 8601), value and unit. Ingestion skips a reading without a number, so a few of those
    # are only counted; the check fails when none of the records has one. A sensor in another unit than
    # ingestion expects fails it, since ingestion skips that sensor's readings until the unit table is updated.
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ShapeError("no 'data' list")
    records = body["data"]
    if not records:
        raise ShapeError(f"no records in the last {WINDOW.total_seconds() / 3600:g} h")
    weather = loggers = no_number = 0
    wrong_units = set()
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            raise ShapeError(f"record {i} isn't an object")
        if not isinstance(r.get("sensor_sn"), str):
            raise ShapeError(f"record {i} has no sensor_sn")
        if not licor_record_used(r["sensor_sn"]):
            continue
        try:
            datetime.fromisoformat(r.get("timestamp"))
        except (TypeError, ValueError):
            raise ShapeError(f"record {i} has a missing or unreadable timestamp")
        expected = expected_unit(r)
        unit = r.get("unit")
        if expected is not None and not same_unit(unit, expected):
            wrong_units.add(f"{r['sensor_sn']} reports {unit!r}, not {expected!r}")
        if not has_number(r.get("value")):
            no_number += 1
            continue
        if r["sensor_sn"].startswith(LOGGER_PREFIX):
            loggers += 1
        else:
            weather += 1
    if wrong_units:
        raise ShapeError("unexpected units, so ingestion skips these sensors: " + "; ".join(sorted(wrong_units)))
    if not weather + loggers:
        if no_number:
            raise ShapeError(f"none of the {no_number} records ingestion reads has a number as its value")
        raise ShapeError("only records ingestion skips (battery or unknown logger channels)")
    summary = f"{len(records)} records ({weather} weather, {loggers} water-level logger read by ingestion)"
    return summary + (f", {no_number} without a number (skipped)" if no_number else "")


def check_wqdata(body):
    # QualityService and parsers read body["data"] (points with a "%Y-%m-%d %H:%M:%S" UTC timestamp and a list of
    # values with parameterId and value) and body["info"] for paging.
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ShapeError("no 'data' list")
    if not isinstance(body.get("info"), dict):
        raise ShapeError("no 'info' object (used for paging)")
    points = body["data"]
    if not points:
        raise NoRecentData(f"no data points in the last {WINDOW.total_seconds() / 3600:g} h")
    known = 0
    for i, p in enumerate(points):
        if not isinstance(p, dict) or not isinstance(p.get("values"), list):
            raise ShapeError(f"point {i} has no 'values' list")
        try:
            datetime.strptime(p.get("timestamp"), FMT)
        except (TypeError, ValueError):
            raise ShapeError(f"point {i} has no timestamp in the expected format")
        for v in p["values"]:
            if not isinstance(v, dict) or "parameterId" not in v or "value" not in v:
                raise ShapeError(f"point {i} has a value without parameterId or value")
            known += v["parameterId"] in WQ_PARAMETER_IDS
    if not known:
        raise ShapeError("none of the parameter IDs ingestion stores are present")
    return f"{len(points)} points, {known} values ingestion stores"


def check_borealis(body):
    # download_data.py reads data.latestVersion.versionState and files[].dataFile.{filename, id}.
    data = body.get("data") if isinstance(body, dict) else None
    latest = data.get("latestVersion") if isinstance(data, dict) else None
    if not isinstance(latest, dict):
        raise ShapeError("no data.latestVersion")
    if not isinstance(latest.get("versionState"), str):
        raise ShapeError("no latestVersion.versionState")
    files = latest.get("files")
    if not isinstance(files, list):
        raise ShapeError("no latestVersion.files list")
    for i, f in enumerate(files):
        df = f.get("dataFile") if isinstance(f, dict) else None
        if not isinstance(df, dict) or "filename" not in df or "id" not in df:
            raise ShapeError(f"file {i} has no dataFile.filename or dataFile.id")
    return f"{latest['versionState']}, {len(files)} files"


# ---- Requests

def get_json(url, timeout=TIMEOUT, **kwargs):
    """(HTTP status, parsed body). Raises requests errors (non-2xx included) and ValueError for a non-JSON body."""
    response = requests.get(url, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response.status_code, response.json()


def missing(*names):
    # Config attribute names are the environment variable names, apart from the HOBO_* ones.
    env = {"HOBO_API_URL": "HOBOLINK_API_URL", "HOBO_API_TOKEN": "HOBOLINK_API_TOKEN",
           "HOBO_LOGGERS": "HOBOLINK_LOGGERS"}
    return [env.get(n, n) for n in names if not getattr(Config, n)]


def probe_licor(now):
    if gone := missing("HOBO_API_URL", "HOBO_API_TOKEN", "HOBO_LOGGERS"):
        return None, f"not configured: {', '.join(gone)}"
    params = {"loggers": Config.HOBO_LOGGERS.split(",")[0],          # as WeatherService.get_logger_id()
              "start_date_time": (now - WINDOW).strftime(FMT), "end_date_time": now.strftime(FMT)}
    status, body = get_json(Config.HOBO_API_URL, params=params,
                            headers={"Authorization": f"Bearer {Config.HOBO_API_TOKEN}"})
    return status, check_licor(body)


def probe_wqdata(now):
    if gone := missing("WQ_API_URL", "WQ_API_KEY", "WQ_DEVICE_ID"):
        return None, f"not configured: {', '.join(gone)}"
    url = f"{Config.WQ_API_URL}/devices/{Config.WQ_DEVICE_ID}/parameters/data"
    params = {"apiKey": Config.WQ_API_KEY, "from": (now - WINDOW).strftime(FMT), "to": now.strftime(FMT)}
    status, body = get_json(url, params=params)
    try:
        return status, check_wqdata(body)
    except NoRecentData as e:
        # Still a failure (ingestion has nothing to store), but say when the device last reported, so a sonde or
        # modem that went quiet doesn't read as a rejected key or a broken API.
        raise ProbeError(f"{e}; {last_reported(url, now)}") from None


def last_reported(url, now):
    """When the device's newest point before the canary's window is from, as a phrase for the failure line."""
    end = now - WINDOW
    try:
        for _ in range(LOOKBACK_DAYS):
            start = end - timedelta(days=1)
            sleep(WQ_PAUSE_S)
            _, body = get_json(url, timeout=LOOKBACK_TIMEOUT,
                               params={"apiKey": Config.WQ_API_KEY, "from": start.strftime(FMT),
                                       "to": end.strftime(FMT)})
            newest = newest_point(body)
            if newest:
                ago = (now - newest).total_seconds() / 3600
                return (f"the device stopped reporting at {newest.strftime('%Y-%m-%d %H:%M')} UTC ({ago:.0f} h ago): "
                        f"WQData answered normally, so check the sonde and its modem, not the API key")
            end = start
    except Exception as e:   # the window's answer already showed the API works; this is only the detail
        return f"couldn't look further back ({describe(e)})"
    return (f"none in the last {LOOKBACK_DAYS} days either: WQData answered normally, so the device has stopped "
            f"reporting (check the sonde and its modem, not the API key)")


def newest_point(body):
    """The latest timestamp among a WQData answer's points (UTC), or None when it has none."""
    times = []
    for p in (body.get("data") if isinstance(body, dict) else None) or []:
        try:
            times.append(datetime.strptime(p.get("timestamp"), FMT).replace(tzinfo=timezone.utc))
        except (AttributeError, TypeError, ValueError):
            continue   # a malformed point; the shape check reports those when they are in the window
    return max(times, default=None)


def probe_borealis(now):
    if gone := missing("BOREALIS_URL", "BOREALIS_API_TOKEN",
                       "BOREALIS_SAMPLING_PERSISTENT_ID", "BOREALIS_UPLOAD_PERSISTENT_ID"):
        return None, f"not configured: {', '.join(gone)}"
    # BOREALIS_URL may be a collection page (https://borealisdata.ca/dataverse/WELL); the API is at the server root.
    try:
        server = base_url(Config.BOREALIS_URL)
    except ValueError:
        return None, "not configured: BOREALIS_URL isn't a URL such as https://borealisdata.ca"
    host = urlsplit(server).netloc
    headers = {"X-Dataverse-key": Config.BOREALIS_API_TOKEN}
    # The token on its own first. Dataverse answers 401 to a bad token on every call, so only this tells "the token
    # isn't valid here" (wrong, expired, or made on the other server: demo and production tokens are separate)
    # apart from "this dataset isn't there".
    try:
        get_json(f"{server}/api/users/:me", headers=headers)
    except Exception as e:
        if http_status(e) == 401:
            raise ProbeError(f"token not valid on {host} (HTTP 401): BOREALIS_API_TOKEN is wrong, has expired, or "
                             f"was made on another Borealis server (demo and production tokens are separate). "
                             f"Create or recreate it on {host} (your name > API Token), then update it in the "
                             f"repository secrets and the VM's .env") from None
        raise ProbeError(f"checking the token on {host}: {describe(e)}") from None
    # Both datasets: downloads read the first, uploads add files to the second, so the token must work on each.
    summaries, status = [], None
    for label, name, pid in (("download dataset", "BOREALIS_SAMPLING_PERSISTENT_ID",
                              Config.BOREALIS_SAMPLING_PERSISTENT_ID),
                             ("upload dataset", "BOREALIS_UPLOAD_PERSISTENT_ID", Config.BOREALIS_UPLOAD_PERSISTENT_ID)):
        try:
            status, body = get_json(f"{server}/api/datasets/:persistentId",
                                    params={"persistentId": pid}, headers=headers)
            summaries.append(f"{label} {check_borealis(body)}")
        except Exception as e:
            code = http_status(e)
            if code in (403, 404):
                pid_on = "demo" if is_demo(persistent_id=pid) else "production"
                other = "" if is_demo(persistent_id=pid) == is_demo(server) else (
                    f"; its id is a {pid_on}-server id, not one on {host}")
                raise ProbeError(f"token OK on {host}; the {label} ({name}) was not found or isn't shared with "
                                 f"this token (HTTP {code}){other}") from None
            raise ProbeError(f"{label}: {describe(e)}") from None
    return status, f"{host}, token OK; " + "; ".join(summaries)


def http_status(e):
    """The HTTP status of a failed request, or None (no answer, or not a request error)."""
    return getattr(getattr(e, "response", None), "status_code", None)


class ProbeError(Exception):
    """A failure whose message is already safe to print."""


def describe(e):
    """One safe line for a failed probe: no URLs, keys or bodies."""
    if isinstance(e, ProbeError):
        return str(e)
    if isinstance(e, ShapeError):
        return f"unexpected response: {e}"
    if isinstance(e, requests.exceptions.RequestException):
        return describe_request_error(e)
    if isinstance(e, ValueError):
        return "response isn't JSON"
    return type(e).__name__


PROBES = (("LI-COR", probe_licor), ("WQData", probe_wqdata), ("Borealis", probe_borealis))


def run(probes=PROBES, now=None, out=print):
    """Run each probe once; print one line each. Returns the names of the sources that failed."""
    now = now or datetime.now(timezone.utc)
    failed = []
    for name, probe in probes:
        try:
            status, summary = probe(now)
        except Exception as e:   # one source failing mustn't stop the others being checked
            failed.append(name)
            out(f"FAIL {name}: {describe(e)}")
            continue
        if status is None:
            failed.append(name)
            out(f"FAIL {name}: {summary}")
        else:
            out(f"OK   {name}: HTTP {status}, {summary}")
    return failed


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
