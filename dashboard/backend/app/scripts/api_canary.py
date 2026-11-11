# Daily check that each vendor API still accepts our credentials and still answers in the shape ingestion reads.
# Run by .github/workflows/canary.yml once a day; by hand from dashboard/backend: python app/scripts/api_canary.py
#
# Makes exactly one small request per data source, so it stays far inside every quota:
#  - LI-COR (HOBOlink): the last few hours for the station's logger (weather and water-level sensors).
#  - WQData: the last few hours of one device. WQData's hourly request quota is shared with the 10-minute
#    ingestion, so this is a single request with no paging and no retries.
#  - Borealis: the metadata of each dataset (the one downloads read and the one uploads add to), with our token.
# Prints one line per source (OK or FAIL with the HTTP status and a reason) and exits 1 if any failed.
# Never prints URLs, tokens, keys or response bodies: WQData takes its key in the query string, and requests'
# error text includes the full URL, so errors are reported as exception type and HTTP status only.

import sys
import pathlib
from datetime import datetime, timedelta, timezone

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import requests

from config import Config
from api.services.quality import describe_request_error

WINDOW = timedelta(hours=6)    # recent enough to be cheap, long enough that a slow upload still shows data
TIMEOUT = (10, 60)
FMT = "%Y-%m-%d %H:%M:%S"

# Copies of the values in utils/parsers.py, which can't be imported here without the database packages
# (the workflow installs only requests). tests/test_api_canary.py checks they still match.
LOGGER_PREFIX = "2216865"                                                    # parsers.LOGGER_PREFIX
LOGGER_SERIALS = {"22168653", "22168654", "22168655", "22168656", "22168657"}  # parsers.LOGGER_CONFIG keys
WQ_PARAMETER_IDS = {125001, 125002, 125004, 125005, 125006, 125007, 125008, 125009}  # parsers.QUALITY_PARAM_ID_MAP


class ShapeError(Exception):
    """The response parsed, but not in the shape ingestion depends on."""


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


def check_licor(body):
    # inject_from_api.py reads body["data"], and per record sensor_sn; for the records it doesn't skip, it also
    # parses timestamp (ISO 8601) and value (a number), so those are only required there.
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ShapeError("no 'data' list")
    records = body["data"]
    if not records:
        raise ShapeError(f"no records in the last {WINDOW.total_seconds() / 3600:g} h")
    weather = loggers = 0
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            raise ShapeError(f"record {i} isn't an object")
        if not isinstance(r.get("sensor_sn"), str):
            raise ShapeError(f"record {i} has no sensor_sn")
        if not licor_record_used(r["sensor_sn"]):
            continue
        try:
            datetime.fromisoformat(r.get("timestamp"))
            float(r.get("value"))   # ingestion skips a reading without a number; a missing one here means the shape changed
        except (TypeError, ValueError):
            raise ShapeError(f"record {i} has a missing or unreadable timestamp or value")
        if r["sensor_sn"].startswith(LOGGER_PREFIX):
            loggers += 1
        else:
            weather += 1
    if not weather + loggers:
        raise ShapeError("only records ingestion skips (battery or unknown logger channels)")
    return f"{len(records)} records ({weather} weather, {loggers} water-level logger read by ingestion)"


def check_wqdata(body):
    # QualityService and parsers read body["data"] (points with a "%Y-%m-%d %H:%M:%S" UTC timestamp and a list of
    # values with parameterId and value) and body["info"] for paging.
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ShapeError("no 'data' list")
    if not isinstance(body.get("info"), dict):
        raise ShapeError("no 'info' object (used for paging)")
    points = body["data"]
    if not points:
        raise ShapeError(f"no data points in the last {WINDOW.total_seconds() / 3600:g} h")
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

def get_json(url, **kwargs):
    """(HTTP status, parsed body). Raises requests errors (non-2xx included) and ValueError for a non-JSON body."""
    response = requests.get(url, timeout=TIMEOUT, **kwargs)
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
    params = {"apiKey": Config.WQ_API_KEY, "from": (now - WINDOW).strftime(FMT), "to": now.strftime(FMT)}
    status, body = get_json(f"{Config.WQ_API_URL}/devices/{Config.WQ_DEVICE_ID}/parameters/data", params=params)
    return status, check_wqdata(body)


def probe_borealis(now):
    if gone := missing("DEMO_BOREALIS_URL", "BOREALIS_API_TOKEN",
                       "DEMO_BOREALIS_AW_PERSISTENT_ID", "DEMO_BOREALIS_WC_PERSISTENT_ID"):
        return None, f"not configured: {', '.join(gone)}"
    # Both datasets: downloads read the first, uploads add files to the second, so the token must work on each.
    summaries, status = [], None
    for label, pid in (("download dataset", Config.DEMO_BOREALIS_AW_PERSISTENT_ID),
                       ("upload dataset", Config.DEMO_BOREALIS_WC_PERSISTENT_ID)):
        try:
            status, body = get_json(f"{Config.DEMO_BOREALIS_URL}/api/datasets/:persistentId",
                                    params={"persistentId": pid},
                                    headers={"X-Dataverse-key": Config.BOREALIS_API_TOKEN})
            summaries.append(f"{label} {check_borealis(body)}")
        except Exception as e:
            raise ProbeError(f"{label}: {describe(e)}") from None
    return status, "; ".join(summaries)


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
