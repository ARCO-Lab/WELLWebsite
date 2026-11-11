"""Runs the dashboard's real 10-minute ingestion (scripts/inject_from_api.py) against the vendor stub, at the times
listed in fixtures/expected.json ("ingestion_runs_utc"), with the clock frozen at each one.

Run it from the backend's app folder (dashboard/backend/app, /app/app in the image), with the backend's usual
environment (DATABASE_URL, HOBOLINK_*, WQ_*) pointing at the test database and the stub:

    python /path/to/dashboard/e2e/ingest.py

Only the clock and WQData's pause between pages are replaced; requests, parsing, time zone conversion and the
INSERT ... ON CONFLICT DO NOTHING are the production code. Fails if any run fails, if the first run stores nothing,
or if the last run (a repeat of the one before) stores anything: re-reading data already stored must add nothing.
"""
import datetime as dt
import json
import os
import pathlib
import sys

sys.path.insert(0, os.getcwd())   # the backend's app folder, where server.py and scripts/ live

from sqlalchemy import func  # noqa: E402

from scripts import inject_from_api as ingest  # noqa: E402
from db.models import SensorMeasurement  # noqa: E402

EXPECTED = json.loads((pathlib.Path(__file__).resolve().parent / "fixtures" / "expected.json").read_text("utf-8"))


class FrozenClock(dt.datetime):
    """datetime, except now() returns `at` (inject_from_api reads the time once per run, with datetime.now(utc))."""
    at = None

    @classmethod
    def now(cls, tz=None):
        return cls.at.astimezone(tz) if tz else cls.at.replace(tzinfo=None)


def stored():
    with ingest.app.app_context():
        return ingest.db.session.query(func.count(SensorMeasurement.id)).scalar()


def main():
    ingest.datetime = FrozenClock
    ingest.quality_service.sleep = lambda seconds: None   # WQData's 3.5 s between pages; the stub doesn't throttle
    runs = [dt.datetime.fromisoformat(t.replace("Z", "+00:00")) for t in EXPECTED["ingestion_runs_utc"]]
    added = []
    for at in runs:
        FrozenClock.at = at
        before = stored()
        print(f"[e2e] ingestion run at {at:%Y-%m-%d %H:%M} UTC", flush=True)
        ingest.inject_all_new_data()   # raises if either source failed
        added.append(stored() - before)
        print(f"[e2e] {added[-1]} new rows, {stored()} stored", flush=True)
    if added[0] == 0:
        sys.exit("[e2e] FAIL: the first ingestion run stored nothing")
    if added[-1] != 0:
        sys.exit(f"[e2e] FAIL: repeating the last run stored {added[-1]} more rows; re-reads must add nothing")


if __name__ == "__main__":
    main()
