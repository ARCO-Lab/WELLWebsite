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
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

import config  # noqa: E402
from config import Config  # noqa: E402
from server import create_app  # noqa: E402
from db.database import db, engine_options  # noqa: E402
from api.routes.series import MAX_AGE_PAST, MAX_AGE_RECENT, cache_key, max_age, snap_range  # noqa: E402
from utils import response_cache  # noqa: E402

# Config reads DATABASE_URL once, when first imported; another test module may have imported it first.
Config.SQLALCHEMY_DATABASE_URI = "sqlite://"


class TimeoutSettingTests(unittest.TestCase):
    def test_unset_empty_or_zero_means_no_timeout(self):
        for value in (None, "", "  ", "0"):
            self.assertEqual(config.parse_timeout_ms("X", value), 0, value)

    def test_a_whole_number_is_used(self):
        self.assertEqual(config.parse_timeout_ms("X", "25000"), 25000)
        self.assertEqual(config.parse_timeout_ms("X", " 500 "), 500)

    def test_anything_else_warns_and_means_no_timeout(self):
        for value in ("25s", "-1", "1.5"):
            with self.assertLogs("config", "WARNING") as logs:
                self.assertEqual(config.parse_timeout_ms("DB_STATEMENT_TIMEOUT_MS", value), 0)
            self.assertIn("DB_STATEMENT_TIMEOUT_MS", logs.output[0])


class EngineOptionsTests(unittest.TestCase):
    def test_postgres_gets_the_timeout_at_connect(self):
        self.assertEqual(engine_options("postgresql://u:p@h/db", 25000),
                         {"pool_pre_ping": True, "connect_args": {"options": "-c statement_timeout=25000"}})

    def test_no_timeout_when_zero(self):
        self.assertEqual(engine_options("postgresql://u:p@h/db", 0), {"pool_pre_ping": True})

    def test_sqlite_never_gets_postgres_options(self):
        self.assertEqual(engine_options("sqlite://", 25000), {"pool_pre_ping": True})

    def test_the_app_uses_them(self):
        with mock.patch.object(Config, "DB_STATEMENT_TIMEOUT_MS", 1234), \
                mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", "postgresql://u:p@h/db"):
            app = create_app()
        self.assertEqual(app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"],
                         {"options": "-c statement_timeout=1234"})


class FakePgError(Exception):
    def __init__(self, pgcode):
        super().__init__("boom")
        self.pgcode = pgcode


class DatabaseErrorHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

        @cls.app.route("/_test/fail/<code>")
        def fail(code):
            raise OperationalError("SELECT 1", {}, FakePgError(code))

        cls.client = cls.app.test_client()

    def test_a_cancelled_query_is_a_504_with_a_message(self):
        with self.assertLogs(self.app.logger, "WARNING"):
            r = self.client.get("/_test/fail/57014")
        self.assertEqual(r.status_code, 504)
        self.assertIn("took too long", r.get_json()["error"])

    def test_other_database_errors_are_a_503_with_a_message(self):
        with self.assertLogs(self.app.logger, "WARNING"):
            r = self.client.get("/_test/fail/08006")
        self.assertEqual(r.status_code, 503)
        self.assertIn("can't reach its database", r.get_json()["error"])
        self.assertNotIn("boom", r.get_data(as_text=True))  # no driver details


class LatestCacheControlTests(unittest.TestCase):
    def test_latest_may_be_reused_for_a_minute(self):
        app = create_app()
        with app.app_context():
            db.create_all()
            try:
                r = app.test_client().get("/api/latest")
            finally:
                db.drop_all()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Cache-Control"], "public, max-age=60")


class SeriesCacheRulesTests(unittest.TestCase):
    def test_snap_widens_to_ten_minute_marks(self):
        start, end = snap_range(dt.datetime(2026, 11, 1, 0, 7, 30, 5), dt.datetime(2026, 11, 2, 12, 31, 0, 1))
        self.assertEqual((start, end), (dt.datetime(2026, 11, 1, 0, 0), dt.datetime(2026, 11, 2, 12, 40)))

    def test_snap_keeps_times_already_on_a_mark(self):
        t0, t1 = dt.datetime(2026, 11, 1, 0, 20), dt.datetime(2026, 11, 1, 1, 0)
        self.assertEqual(snap_range(t0, t1), (t0, t1))

    def test_snap_near_the_end_of_time(self):
        end = dt.datetime.max - dt.timedelta(minutes=1)
        self.assertEqual(snap_range(end, end)[1], end)

    def test_requests_minutes_apart_share_a_key(self):
        a = snap_range(dt.datetime(2026, 10, 1, 9, 1), dt.datetime(2026, 11, 1, 9, 1))
        b = snap_range(dt.datetime(2026, 10, 1, 9, 8), dt.datetime(2026, 11, 1, 9, 8))
        self.assertEqual(cache_key(1800, *a, ["Weather", "Logger"]), cache_key(1800, *b, ["Logger", "Weather"]))
        self.assertNotEqual(cache_key(1800, *a, ["Weather"]), cache_key(3600, *a, ["Weather"]))
        self.assertNotEqual(cache_key(1800, *a, ["Weather"]), cache_key(1800, *a, ["Weather", "Logger"]))

    def test_max_age_is_short_until_the_range_has_been_over_for_an_hour(self):
        now = dt.datetime(2026, 11, 11, 12, 0)
        self.assertEqual(max_age(now + dt.timedelta(days=1), now), MAX_AGE_RECENT)
        self.assertEqual(max_age(now, now), MAX_AGE_RECENT)
        self.assertEqual(max_age(now - dt.timedelta(minutes=59), now), MAX_AGE_RECENT)
        self.assertEqual(max_age(now - dt.timedelta(minutes=61), now), MAX_AGE_PAST)
        self.assertEqual((MAX_AGE_RECENT, MAX_AGE_PAST), (60, 300))


class FakeRedis:
    def __init__(self):
        self.store, self.ttl = {}, {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key], self.ttl[key] = value, ex


class BrokenRedis:
    calls = 0

    def get(self, key):
        BrokenRedis.calls += 1
        raise response_cache.redis.ConnectionError("down")

    def set(self, key, value, ex=None):
        BrokenRedis.calls += 1
        raise response_cache.redis.ConnectionError("down")


class ResponseCacheTests(unittest.TestCase):
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
            self.assertEqual(response_cache.get("k"), b"v")
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
            self.assertLess(time.monotonic() - started, 2)


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the statement-timeout tests")
class StatementTimeoutTests(unittest.TestCase):
    @staticmethod
    def make_app(timeout_ms):
        with mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", os.environ["TEST_POSTGRES_URL"]), \
                mock.patch.object(Config, "DB_STATEMENT_TIMEOUT_MS", timeout_ms):
            app = create_app()

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
    unittest.main()
