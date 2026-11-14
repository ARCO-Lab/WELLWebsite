"""Requests and conditions that must not become error reports: a NUL character in any value a read or export route
takes (WELL-BACKEND-6), a gunicorn worker stopped while it waited for a slow client (WELL-BACKEND-2), a client that
leaves halfway through its request body, and a migration that hasn't been applied yet (WELL-BACKEND-3), which must say
so instead of failing with an SQL error.

Events go to the real Sentry SDK with the real settings, sending to memory (tests/test_sentry.py). The routes run on
PostgreSQL when TEST_POSTGRES_URL points at a disposable database (as in CI), where the driver itself refuses a NUL,
and on a throwaway SQLite file otherwise. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import json
import logging
import os
import pathlib
import re
import shutil
import signal
import sys
import tempfile
import types
import unittest.mock

import sentry_sdk
from sqlalchemy.orm import Session

from tests.test_sentry import FAKE_DSN, MemoryTransport, stop_sentry

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))

from config import Config  # noqa: E402
from utils import sentry as well_sentry  # noqa: E402

NUL = "\x00"
START, END = "2026-11-01T00:00:00", "2026-11-02T00:00:00"

# Every query parameter each GET route reads, with a valid value; each is sent again with a NUL added.
GET_ROUTES = {
    # One tile of 360 10-minute buckets (api/routes/series.py check_tiles)
    "/api/series": {"start": "2026-10-31T12:00:00", "end": "2026-11-03T00:00:00", "group_type": "Weather",
                    "station_id": "22051538",
                    "measurement_type": "Rain", "series": "Weather|22051538|Rain", "bucket": "600"},
    "/api/data": {"start": START, "end": END, "group_type": "Weather"},
    "/api/samples": {"start": START, "end": END},
    "/api/windrose": {"start": START, "end": END, "speed": "Wind Speed"},
}
# Routes that read no parameters (and the creek flags of /api/samples, only compared with "true"): a NUL there is
# never read, so the answer just mustn't be an error.
UNREAD = [("/api/latest", {}), ("/api/recent", {}), ("/health", {}), ("/health/data", {}),
          ("/api/samples/template.csv", {}), ("/api/samples", {"start": START, "end": END, "ancaster": NUL})]
EXPORT_ROUTES = ("/api/exports/estimate", "/api/exports/sync", "/api/exports/jobs")
SENSOR = {"domain": "sensor", "start": START, "end": END, "group_types": ["Logger"], "station_ids": ["2577531"],
          "measurement_types": ["Water Level"], "group_measurement_types": {"Logger": ["Water Level"]}}
SAMPLING = {"domain": "sampling", "start": START, "end": END, "creek_ids": ["19431905"], "site_ids": ["1"],
            "measurement_types": ["pH"]}


def with_nul(value):
    """`value` with a NUL in it: in each string, and in each string of a list or dict (keys included)."""
    if isinstance(value, str):
        return value + NUL
    if isinstance(value, list):
        return [with_nul(v) for v in value]
    return {with_nul(k): v for k, v in value.items()}


def nul_bodies():
    """(field, body, refused) for every field of both export kinds, each with a NUL added to it alone. refused is
    False for a group_measurement_types key: only the group names Weather, Quality and Logger are read there, so
    "Logger" with a NUL is ignored like any other unknown key, and the NUL never reaches a query."""
    for base in (SENSOR, SAMPLING):
        for field, value in base.items():
            yield field, {**base, field: with_nul(value)}, field != "group_measurement_types"
    yield ("group_measurement_types list", {**SENSOR, "group_measurement_types": {"Logger": ["Water Level" + NUL]}},
           True)


class SentryInMemory:
    """The real SDK, set up by init_sentry as on the VM, sending to memory."""

    def start_sentry(self):
        real_init = sentry_sdk.init
        with unittest.mock.patch.dict(os.environ, {"SENTRY_DSN": FAKE_DSN}), \
                unittest.mock.patch("sentry_sdk.init", side_effect=lambda **o: real_init(transport=MemoryTransport, **o)):
            self.assertTrue(well_sentry.init_sentry("backend"))
        self.addCleanup(stop_sentry)
        self.transport = sentry_sdk.get_client().transport

    def events(self):
        sentry_sdk.flush(timeout=2)
        return self.transport.events


class AppOnTestDatabase(SentryInMemory):
    """The API on PostgreSQL (TEST_POSTGRES_URL) or a throwaway SQLite file, with Sentry sending to memory."""

    def setUp(self):
        self.start_sentry()
        url = os.getenv("TEST_POSTGRES_URL")
        if not url:
            tmp = tempfile.mkdtemp(prefix="request-errors-")
            self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
            url = f"sqlite:///{os.path.join(tmp, 'test.db')}"
            exports = unittest.mock.patch.object(Config, "EXPORTS_DIR", os.path.join(tmp, "exports"))
            exports.start()
            self.addCleanup(exports.stop)
        patch = unittest.mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", url)
        patch.start()
        self.addCleanup(patch.stop)
        from server import create_app
        from db.database import db
        from tasks import exports as export_tasks
        delay = unittest.mock.patch.object(export_tasks.generate_export_job, "delay")
        delay.start()
        self.addCleanup(delay.stop)
        self.db = db
        self.app = create_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.db.engine.dispose()
        self.ctx.pop()


class NulTests(AppOnTestDatabase, unittest.TestCase):
    def test_a_nul_in_any_parameter_is_a_400_and_no_error_report(self):
        for path, params in GET_ROUTES.items():
            # Without the NUL the request is valid: /api/series answers without a query here (no such series yet),
            # /api/windrose's SQL is PostgreSQL's
            if os.getenv("TEST_POSTGRES_URL") or path != "/api/windrose":
                self.assertEqual(self.client.get(path, query_string=params).status_code, 200, path)
            for name in params:
                r = self.client.get(path, query_string={**params, name: params[name] + NUL})
                self.assertEqual(r.status_code, 400, (path, name))
                self.assertNotIn(NUL, r.get_data(as_text=True))
        for path, params in UNREAD:
            r = self.client.get(path, query_string={"x": NUL, **params})
            # /health/data is 503 while readings are missing, as here, whatever the request says
            self.assertIn(r.status_code, (200, 503) if path == "/health/data" else (200,), path)
            r.close()
        self.assertEqual(self.events(), [])

    def test_a_nul_in_any_export_field_is_a_400_and_no_error_report(self):
        for path in EXPORT_ROUTES:
            for field, body, refused in nul_bodies():
                r = self.client.post(path, data=json.dumps(body), content_type="application/json",
                                     headers={"X-Forwarded-For": "198.51.100.7"})
                if refused:
                    self.assertEqual(r.status_code, 400, (path, field))
                else:
                    self.assertLess(r.status_code, 300, (path, field))
                r.close()
        for path in ("/api/exports/jobs/%00", "/api/exports/jobs/%00/download"):
            self.assertEqual(self.client.get(path).status_code, 404, path)
        self.assertEqual(self.events(), [])

    def test_a_client_that_leaves_during_its_body_is_a_400_and_no_error_report(self):
        body = json.dumps(SAMPLING).encode()
        for path in EXPORT_ROUTES:
            r = self.client.post(path, data=body[:20], content_type="application/json",
                                 environ_overrides={"CONTENT_LENGTH": str(len(body))})
            self.assertEqual(r.status_code, 400, path)
        self.assertEqual(self.events(), [])

    def test_the_harness_does_see_a_real_error(self):
        @self.app.route("/test-boom")
        def boom():
            raise RuntimeError("a bug")

        self.assertEqual(self.client.get("/test-boom").status_code, 500)
        self.assertEqual([e["exception"]["values"][-1]["value"] for e in self.events()], ["a bug"])


def stopped_worker_event(module="gunicorn.workers.base", function="handle_abort", kind="SystemExit"):
    """An event shaped like WELL-BACKEND-2's: the exit, innermost frame last, inside the request parser."""
    frames = [{"module": "gunicorn.http.parser", "function": "__next__"},
              {"module": "gunicorn.http.unreader", "function": "chunk"}, {"module": module, "function": function}]
    return {"level": "error", "exception": {"values": [{"type": kind, "value": "1", "stacktrace": {"frames": frames}}]}}


class GunicornWorkerExitTests(SentryInMemory, unittest.TestCase):
    def test_a_stopped_worker_is_not_sent(self):
        self.assertIsNone(well_sentry.before_send(stopped_worker_event()))
        self.assertIsNone(well_sentry.before_send(stopped_worker_event(function="handle_quit"),
                                                  {"exc_info": (SystemExit, SystemExit(0), None)}))

    def test_other_exits_and_errors_are_still_sent(self):
        for event in (stopped_worker_event(module="utils.guards", function="require_wipe_permission"),
                      stopped_worker_event(kind="RuntimeError"), stopped_worker_event(function="handle_request")):
            self.assertIsNotNone(well_sentry.before_send(event), event)
        self.assertIsNotNone(well_sentry.before_send(stopped_worker_event(),
                                                     {"exc_info": (RuntimeError, RuntimeError("x"), None)}))

    def test_a_sync_worker_logging_its_own_exit_sends_nothing(self):
        # What gunicorn's sync worker did: the arbiter's SIGABRT ran handle_abort while the worker was reading a
        # request, and the worker's handler for any exception (BaseException, so the exit too) logged it ("Error handling
        # request"), which the logging integration turns into an error event. Only the exit is caught here.
        try:
            from gunicorn.workers.base import Worker
        except ImportError:
            self.skipTest("gunicorn isn't installed")
        self.start_sentry()
        worker = types.SimpleNamespace(alive=True, cfg=types.SimpleNamespace(worker_abort=lambda w: None))
        log = logging.getLogger("gunicorn.error")
        try:
            Worker.handle_abort(worker, signal.SIGABRT, None)
        except SystemExit:
            log.exception("Error handling request (no URI read)")
        self.assertFalse(worker.alive)
        self.assertEqual(self.events(), [])
        try:
            raise RuntimeError("a real failure")
        except RuntimeError:
            log.exception("Error handling request (no URI read)")
        self.assertEqual(len(self.events()), 1, "the same log line with a real error is still sent")

    def test_the_api_runs_threaded_workers(self):
        # A sync worker reads each request in its only thread, so one slow or silent client held it until --timeout
        # stopped it (WELL-BACKEND-2). gthread waits for a new connection's first bytes for 5 s, then parks it in its
        # poller, so idle clients hold no thread, and the timeout only stops a worker that has hung altogether.
        dockerfile = pathlib.Path(__file__).resolve().parents[1] / "Dockerfile"
        cmd = re.search(r"^CMD (\[.*?\])\s*$", dockerfile.read_text().replace("\\\n", ""), re.M | re.S)
        args = json.loads(cmd.group(1))
        self.assertEqual(args[args.index("-k") + 1], "gthread")
        self.assertGreater(int(args[args.index("--threads") + 1]), 1)
        # Longer than the dashboard proxy's 5 s idle reuse (lib/proxyBackend.ts), so gunicorn never closes a
        # connection the proxy is about to reuse
        self.assertGreater(int(args[args.index("--keep-alive") + 1]), 5)


class FakePgError(Exception):
    def __init__(self, pgcode):
        super().__init__(f"pgcode {pgcode}")
        self.pgcode = pgcode


class MigrationPendingTests(unittest.TestCase):
    """The alert check, /health/data and the digest read vendor_status and alert_incidents; on a database a migration
    hasn't reached, the error says to apply it."""

    def setUp(self):
        from server import create_app
        self.app = create_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)

    def failing(self, pgcode):
        from sqlalchemy.exc import ProgrammingError
        return ProgrammingError("SELECT ... FROM vendor_status", {}, FakePgError(pgcode))

    def test_a_missing_table_or_column_says_to_run_the_migrations(self):
        from utils.alert_state import MigrationPending, open_incidents, vendor_statuses
        for pgcode in ("42P01", "42703"):
            for read, table in ((vendor_statuses, "vendor_status"), (open_incidents, "alert_incidents")):
                with unittest.mock.patch.object(Session, "execute", side_effect=self.failing(pgcode)), \
                        self.assertRaises(MigrationPending) as caught:
                    read()
                self.assertIn(f"The {table} table", str(caught.exception))
                self.assertIn("scripts/migrate.py", str(caught.exception))

    def test_other_database_errors_are_left_as_they_are(self):
        from sqlalchemy.exc import ProgrammingError
        from utils.alert_state import vendor_statuses
        with unittest.mock.patch.object(Session, "execute", side_effect=self.failing("42601")), \
                self.assertRaises(ProgrammingError):
            vendor_statuses()


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"),
                     "set TEST_POSTGRES_URL to run the pending-migration tests against PostgreSQL")
class MigrationPendingPostgresTests(AppOnTestDatabase, unittest.TestCase):
    def check_says_migration_pending(self):
        import check_alerts
        from utils.alert_state import MigrationPending
        with self.assertRaises(MigrationPending):
            check_alerts.run(env={}, send=lambda *a: None, log=lambda *a: None, dry_run=True)
        self.assertEqual(self.db.session.execute(self.db.text("SELECT 1")).scalar(), 1, "the session still works")
        alerts = self.client.get("/health/data").get_json()["alerts"]
        self.assertEqual(alerts, {"error": "could not read the alerts: MigrationPending"})

    def test_without_the_vendor_status_table(self):
        self.db.session.execute(self.db.text("DROP TABLE vendor_status"))
        self.db.session.commit()
        self.check_says_migration_pending()

    def test_without_a_vendor_status_column(self):
        self.db.session.execute(self.db.text("ALTER TABLE vendor_status DROP COLUMN fetched_until"))
        self.db.session.commit()
        self.check_says_migration_pending()

    def test_without_the_alert_incidents_table(self):
        self.db.session.execute(self.db.text("DROP TABLE alert_incidents"))
        self.db.session.commit()
        self.check_says_migration_pending()


if __name__ == "__main__":
    unittest.main()
