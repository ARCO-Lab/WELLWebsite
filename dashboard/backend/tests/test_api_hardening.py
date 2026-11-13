"""Tests for what keeps the API responsive under load: the statement timeout and its clean 504, the database
error handler, Cache-Control headers, the /api/series response cache and its range rounding. Run from
dashboard/backend: python -m unittest discover -s tests -t .

The statement-timeout tests need PostgreSQL (TEST_POSTGRES_URL, a throwaway database); without it they're skipped.
"""
import datetime as dt
import os
import pathlib
import sys
import time
from unittest import TestCase, main, mock, skipUnless

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from config import Config, parse_timeout_ms  # noqa: E402
import server  # noqa: E402
from db.database import CONNECT_ARGS as CONNECT, db, engine_options  # noqa: E402
from api.routes.series import MAX_AGE_PAST, MAX_AGE_RECENT, MAX_AGE_SETTLED, max_age, snap_range  # noqa: E402
from utils import response_cache  # noqa: E402

# Config reads DATABASE_URL once, when first imported; another test module may have imported it first.
Config.SQLALCHEMY_DATABASE_URI = "sqlite://"


class TimeoutSettingTests(TestCase):
    def test_unset_empty_or_zero_means_no_timeout(self):
        for value in (None, "", "  ", "0"):
            self.assertEqual(parse_timeout_ms("X", value), 0, value)

    def test_a_whole_number_is_used(self):
        self.assertEqual(parse_timeout_ms("X", "25000"), 25000)
        self.assertEqual(parse_timeout_ms("X", " 500 "), 500)

    def test_anything_else_warns_and_means_no_timeout(self):
        for value in ("25s", "-1", "1.5"):
            with self.assertLogs("config", "WARNING") as logs:
                self.assertEqual(parse_timeout_ms("DB_STATEMENT_TIMEOUT_MS", value), 0)
            self.assertIn("DB_STATEMENT_TIMEOUT_MS", logs.output[0])


class EngineOptionsTests(TestCase):
    def test_postgres_gets_the_timeout_at_connect(self):
        self.assertEqual(engine_options("postgresql://u:p@h/db", 25000),
                         {"pool_pre_ping": True, "connect_args": {**CONNECT, "options": "-c statement_timeout=25000"}})

    def test_no_timeout_when_zero(self):
        self.assertEqual(engine_options("postgresql://u:p@h/db", 0), {"pool_pre_ping": True, "connect_args": CONNECT})

    def test_postgres_connections_fail_fast_and_are_kept_alive(self):
        # An unreachable database (packets dropped) fails a connection attempt in 5 s instead of about two minutes,
        # and a connection whose server stopped answering is dropped by TCP keepalives.
        args = engine_options("postgresql+psycopg2://u:p@h/db")["connect_args"]
        self.assertEqual((args["connect_timeout"], args["keepalives"]), (5, 1))
        self.assertLessEqual(args["keepalives_idle"] + args["keepalives_interval"] * args["keepalives_count"], 120)
        args["connect_timeout"] = 99   # each engine gets its own copy
        self.assertEqual(CONNECT["connect_timeout"], 5)

    def test_sqlite_never_gets_postgres_options(self):
        self.assertEqual(engine_options("sqlite://", 25000), {"pool_pre_ping": True})

    def test_postgres_connections_are_named(self):
        self.assertEqual(engine_options("postgresql://u:p@h/db", 0, "well-export_worker"),
                         {"pool_pre_ping": True, "connect_args": {**CONNECT, "application_name": "well-export_worker"}})
        self.assertEqual(engine_options("sqlite://", 0, "well-backend"), {"pool_pre_ping": True})

    def test_the_app_uses_them(self):
        with mock.patch.object(Config, "DB_STATEMENT_TIMEOUT_MS", 1234), \
                mock.patch.object(Config, "DB_APPLICATION_NAME", "well-test"), \
                mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", "postgresql://u:p@h/db"):
            app = server.create_app()
        self.assertEqual(app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"],
                         {**CONNECT, "options": "-c statement_timeout=1234", "application_name": "well-test"})


class FakePgError(Exception):
    def __init__(self, pgcode):
        super().__init__("boom")
        self.pgcode = None if pgcode == "none" else pgcode


class DatabaseErrorHandlerTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = server.create_app()

        @cls.app.route("/_test/fail/<code>")
        def fail(code):
            raise OperationalError("SELECT 1", {}, FakePgError(code))

        cls.client = cls.app.test_client()

    def test_no_cors_headers_for_other_sites(self):
        # Only the dashboard's server calls the backend, so no browser on another site may read its answers.
        r = self.client.get("/health", headers={"Origin": "https://example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", r.headers)
        r = self.client.open("/health", method="OPTIONS", headers={
            "Origin": "https://example.com", "Access-Control-Request-Method": "GET"})
        self.assertNotIn("Access-Control-Allow-Origin", r.headers)

    def test_a_cancelled_query_is_a_504_with_a_message(self):
        with self.assertLogs(self.app.logger, "WARNING"):
            r = self.client.get("/_test/fail/57014")
        self.assertEqual(r.status_code, 504)
        self.assertIn("took too long", r.get_json()["error"])

    def test_connection_errors_are_a_503_that_says_so_and_skip_sentry(self):
        for code in ("08006", "53300", "none"):  # lost connection, too many connections, no code (refused)
            with self.subTest(code=code), mock.patch.object(server, "capture_job_error") as capture:
                with self.assertLogs(self.app.logger, "WARNING"):
                    r = self.client.get(f"/_test/fail/{code}")
                self.assertEqual(r.status_code, 503)
                self.assertIn("can't reach its database", r.get_json()["error"])
                self.assertNotIn("boom", r.get_data(as_text=True))  # no driver details
                capture.assert_not_called()

    def test_other_database_errors_are_a_generic_503_and_go_to_sentry(self):
        for code in ("40P01", "55P03", "53100", "53200"):  # deadlock, lock not available, disk full, out of memory
            with self.subTest(code=code), mock.patch.object(server, "capture_job_error") as capture:
                with self.assertLogs(self.app.logger, "ERROR"):
                    r = self.client.get(f"/_test/fail/{code}")
                self.assertEqual(r.status_code, 503)
                self.assertIn("hit a database error", r.get_json()["error"])
                self.assertNotIn("boom", r.get_data(as_text=True))
                capture.assert_called_once()
                self.assertEqual(capture.call_args.kwargs, {"source": "api"})


class LatestCacheControlTests(TestCase):
    def test_latest_may_be_reused_for_a_minute(self):
        app = server.create_app()
        with app.app_context():
            db.create_all()
            try:
                r = app.test_client().get("/api/latest")
            finally:
                db.drop_all()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Cache-Control"], "public, max-age=60")


class SeriesCacheRulesTests(TestCase):
    def test_snap_narrows_to_ten_minute_marks(self):
        start, end = snap_range(dt.datetime(2026, 11, 1, 0, 7, 30, 5), dt.datetime(2026, 11, 2, 12, 31, 0, 1))
        self.assertEqual((start, end), (dt.datetime(2026, 11, 1, 0, 10), dt.datetime(2026, 11, 2, 12, 30)))

    def test_an_end_just_before_midnight_adds_no_bucket(self):
        # Charts ask for [start, end - 1 ms]; rounding that end up would add the next day's first reading.
        self.assertEqual(snap_range(dt.datetime(2026, 11, 1), dt.datetime(2026, 11, 1, 23, 59, 59, 999000)),
                         (dt.datetime(2026, 11, 1), dt.datetime(2026, 11, 1, 23, 50)))

    def test_a_range_with_no_mark_inside_matches_nothing(self):
        start, end = snap_range(dt.datetime(2026, 11, 1, 0, 3), dt.datetime(2026, 11, 1, 0, 7))
        self.assertGreater(start, end)

    def test_snap_keeps_times_already_on_a_mark(self):
        t0, t1 = dt.datetime(2026, 11, 1, 0, 20), dt.datetime(2026, 11, 1, 1, 0)
        self.assertEqual(snap_range(t0, t1), (t0, t1))

    def test_snap_near_the_end_of_time(self):
        start = dt.datetime.max - dt.timedelta(minutes=1)
        self.assertEqual(snap_range(start, dt.datetime.max)[0], start)

    def test_requests_minutes_apart_select_the_same_readings(self):
        a = snap_range(dt.datetime(2026, 10, 1, 9, 1), dt.datetime(2026, 11, 1, 9, 1))
        b = snap_range(dt.datetime(2026, 10, 1, 9, 8), dt.datetime(2026, 11, 1, 9, 8))
        self.assertEqual(a, b)

    def test_max_age_is_short_until_the_range_has_been_over_for_an_hour(self):
        now = dt.datetime(2026, 11, 11, 12, 0)
        self.assertEqual(max_age(now + dt.timedelta(days=1), now), MAX_AGE_RECENT)
        self.assertEqual(max_age(now, now), MAX_AGE_RECENT)
        self.assertEqual(max_age(now - dt.timedelta(minutes=59), now), MAX_AGE_RECENT)
        self.assertEqual(max_age(now - dt.timedelta(minutes=61), now), MAX_AGE_PAST)
        self.assertEqual(max_age(now - dt.timedelta(hours=23), now), MAX_AGE_PAST)
        self.assertEqual(max_age(now - dt.timedelta(hours=25), now), MAX_AGE_SETTLED)
        self.assertEqual((MAX_AGE_RECENT, MAX_AGE_PAST), (60, 300))


class FakeRedis:
    """Enough of redis.Redis for response_cache: set with a TTL, and a pipeline of get and ttl."""
    def __init__(self):
        self.store, self.ttl = {}, {}
        self.round_trips = 0

    def set(self, key, value, ex=None):
        self.store[key], self.ttl[key] = value, ex

    def pipeline(self, transaction=True):
        fake, results = self, []

        class Pipeline:
            def get(self, key):
                results.append(fake.store.get(key))
                return self

            def ttl(self, key):
                results.append(fake.ttl.get(key, -2))
                return self

            def set(self, key, value, ex=None):
                fake.set(key, value, ex)
                results.append(True)
                return self

            def execute(self):
                fake.round_trips += 1
                return results
        return Pipeline()


class BrokenRedis:
    calls = 0

    def pipeline(self, transaction=True):
        BrokenRedis.calls += 1
        raise response_cache.redis.ConnectionError("down")

    def set(self, key, value, ex=None):
        BrokenRedis.calls += 1
        raise response_cache.redis.ConnectionError("down")


class ResponseCacheTests(TestCase):
    def setUp(self):
        response_cache._client, response_cache._down_until = None, 0.0
        self.addCleanup(setattr, response_cache, "_client", None)
        self.addCleanup(setattr, response_cache, "_down_until", 0.0)

    def test_off_when_no_url(self):
        with mock.patch.object(Config, "API_CACHE_REDIS_URL", ""), \
                mock.patch.object(response_cache.redis.Redis, "from_url") as from_url:
            response_cache.put("k", b"v", 60)
            self.assertIsNone(response_cache.get("k"))
        from_url.assert_not_called()

    def test_stores_with_the_ttl(self):
        fake = FakeRedis()
        with mock.patch.object(Config, "API_CACHE_REDIS_URL", "redis://cache/2"), \
                mock.patch.object(response_cache.redis.Redis, "from_url", return_value=fake):
            response_cache.put("k", b"v", 300)
            self.assertEqual(response_cache.get("k"), (b"v", 300))  # the body and the seconds it has left
            self.assertIsNone(response_cache.get("other"))
        self.assertEqual(fake.ttl["k"], 300)

    def test_large_bodies_are_not_stored(self):
        fake = FakeRedis()
        with mock.patch.object(Config, "API_CACHE_REDIS_URL", "redis://cache/2"), \
                mock.patch.object(response_cache.redis.Redis, "from_url", return_value=fake):
            response_cache.put("k", b"x" * (response_cache.MAX_BYTES + 1), 60)
        self.assertEqual(fake.store, {})

    def test_fails_open_and_backs_off(self):
        BrokenRedis.calls = 0
        with mock.patch.object(Config, "API_CACHE_REDIS_URL", "redis://cache/2"), \
                mock.patch.object(response_cache.redis.Redis, "from_url", return_value=BrokenRedis()):
            with self.assertLogs(response_cache.log, "WARNING"):
                self.assertIsNone(response_cache.get("k"))
            response_cache.put("k", b"v", 60)  # within RETRY_AFTER_S: Redis isn't tried
            self.assertIsNone(response_cache.get("k"))
            self.assertEqual(BrokenRedis.calls, 1)
            response_cache._down_until = time.monotonic() - 1  # the back-off is over
            with self.assertLogs(response_cache.log, "WARNING"):
                self.assertIsNone(response_cache.get("k"))
            self.assertEqual(BrokenRedis.calls, 2)

    def test_an_unreachable_redis_answers_quickly(self):
        # A real client against a closed port: the request must not wait long for the cache.
        with mock.patch.object(Config, "API_CACHE_REDIS_URL", "redis://127.0.0.1:1/2"):
            started = time.monotonic()
            with self.assertLogs(response_cache.log, "WARNING"):
                self.assertIsNone(response_cache.get("k"))
            self.assertLess(time.monotonic() - started, 1)

    def test_a_hung_redis_costs_one_socket_timeout(self):
        # A server that accepts connections but never answers: one 0.3 s read timeout, no retries.
        import socket
        hung = socket.socket()
        hung.bind(("127.0.0.1", 0))
        hung.listen(8)
        self.addCleanup(hung.close)
        with mock.patch.object(Config, "API_CACHE_REDIS_URL", f"redis://127.0.0.1:{hung.getsockname()[1]}/2"):
            started = time.monotonic()
            with self.assertLogs(response_cache.log, "WARNING"):
                self.assertIsNone(response_cache.get("k"))
            self.assertLess(time.monotonic() - started, 0.9)  # a retry would take at least 0.6 s

    def test_many_entries_in_one_round_trip(self):
        fake = FakeRedis()
        with mock.patch.object(Config, "API_CACHE_REDIS_URL", "redis://cache/2"), \
                mock.patch.object(response_cache.redis.Redis, "from_url", return_value=fake):
            big = b"x" * (response_cache.MAX_BYTES + 1)
            response_cache.put_many([("a", b"1", 60), ("b", b"2", 3600), ("big", big, 60)])
            self.assertEqual(fake.round_trips, 1)
            self.assertEqual(response_cache.get_many(["a", "b", "c", "big"]), {"a": (b"1", 60), "b": (b"2", 3600)})
            self.assertEqual(fake.round_trips, 2)
            self.assertEqual(response_cache.get_many([]), {})
            self.assertEqual(fake.round_trips, 2, "nothing to read: no round trip")

    def test_many_fails_open(self):
        with mock.patch.object(Config, "API_CACHE_REDIS_URL", "redis://cache/2"), \
                mock.patch.object(response_cache.redis.Redis, "from_url", return_value=BrokenRedis()):
            with self.assertLogs(response_cache.log, "WARNING"):
                self.assertEqual(response_cache.get_many(["a"]), {})
            response_cache.put_many([("a", b"1", 60)])  # within the back-off: not tried, and no error

    def test_the_client_never_retries(self):
        with mock.patch.object(Config, "API_CACHE_REDIS_URL", "redis://127.0.0.1:1/2"):
            client = response_cache._get_client()
        retry = client.connection_pool.connection_kwargs["retry"]
        self.assertEqual(retry.get_retries(), 0)
        self.assertEqual(client.connection_pool.connection_kwargs.get("retry_on_error"), [])


@skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the statement-timeout tests")
class StatementTimeoutTests(TestCase):
    @staticmethod
    def make_app(timeout_ms):
        with mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", os.environ["TEST_POSTGRES_URL"]), \
                mock.patch.object(Config, "DB_STATEMENT_TIMEOUT_MS", timeout_ms):
            app = server.create_app()

        @app.route("/_test/sleep/<seconds>")
        def sleep(seconds):
            db.session.execute(text("SELECT pg_sleep(:s)"), {"s": float(seconds)})
            return {"slept": True}

        @app.route("/_test/setting")
        def setting():
            return {"statement_timeout": db.session.execute(text("SHOW statement_timeout")).scalar()}

        return app

    def tearDown(self):
        for app in getattr(self, "apps", []):
            with app.app_context():
                db.engine.dispose()

    def client(self, timeout_ms):
        app = self.make_app(timeout_ms)
        self.apps = getattr(self, "apps", []) + [app]
        return app, app.test_client()

    def test_a_query_past_the_timeout_is_a_clean_504(self):
        app, client = self.client(300)
        self.assertEqual(client.get("/_test/setting").get_json(), {"statement_timeout": "300ms"})
        started = time.monotonic()
        with self.assertLogs(app.logger, "WARNING") as logs:
            r = client.get("/_test/sleep/5")
        self.assertLess(time.monotonic() - started, 3)  # cancelled, not waited out
        self.assertEqual(r.status_code, 504)
        self.assertEqual(r.content_type, "application/json")
        self.assertIn("took too long", r.get_json()["error"])
        self.assertNotIn("Traceback", r.get_data(as_text=True))
        self.assertIn("statement timeout", logs.output[0])
        # The connection went back to the pool usable: the next request works.
        self.assertEqual(client.get("/_test/sleep/0").status_code, 200)

    def test_a_query_within_the_timeout_succeeds(self):
        _, client = self.client(5000)
        self.assertEqual(client.get("/_test/sleep/0.2").status_code, 200)

    def test_no_timeout_without_the_setting(self):
        # As the worker and export_worker run: ingestion, backfills and exports are never cut off.
        _, client = self.client(0)
        self.assertEqual(client.get("/_test/setting").get_json(), {"statement_timeout": "0"})
        self.assertEqual(client.get("/_test/sleep/0.5").status_code, 200)

    def test_migrate_never_gets_the_timeout(self):
        # migrate.py builds its engine from DATABASE_URL alone, so CREATE INDEX CONCURRENTLY is never cut off,
        # even in the backend container where DB_STATEMENT_TIMEOUT_MS is set.
        from sqlalchemy import create_engine
        from scripts import migrate
        with mock.patch.dict(os.environ, {"DB_STATEMENT_TIMEOUT_MS": "300",
                                          "DATABASE_URL": os.environ["TEST_POSTGRES_URL"]}), \
                mock.patch.object(migrate, "create_engine", wraps=create_engine) as made, \
                mock.patch.object(sys, "argv", ["migrate.py", "--status"]):
            with mock.patch("builtins.print"):
                migrate.main()
        engine = create_engine(*made.call_args.args, **made.call_args.kwargs)
        try:
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text("SHOW statement_timeout")).scalar(), "0")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
