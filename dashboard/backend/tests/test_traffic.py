"""Request metrics (utils/traffic.py): the per-minute aggregation, the p95 estimate, the Flask hooks (no personal data
kept), the digest's "Traffic yesterday" lines, and, with TEST_POSTGRES_URL set (as in CI), the upsert that adds
rows from several workers together and the totals read back by welldash² and the digest.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import sys
import unittest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from flask import Flask, Response  # noqa: E402

from config import Config  # noqa: E402
from utils import traffic  # noqa: E402
from utils.timezone import EST_TZ  # noqa: E402

Config.SQLALCHEMY_DATABASE_URI = "sqlite://"   # another test module may have imported Config first

UTC = dt.timezone.utc
T = dt.datetime(2026, 11, 10, 15, 4, 30, tzinfo=UTC)
MIGRATION = APP / "db" / "migrations" / "0005_ops_metrics.sql"


class AggregationTests(unittest.TestCase):
    def test_buckets_and_percentile(self):
        self.assertEqual(traffic.bucket_index(0), 0)
        self.assertEqual(traffic.bucket_index(10), 0)
        self.assertEqual(traffic.bucket_index(10.1), 1)
        self.assertEqual(traffic.bucket_index(99999), traffic.BUCKETS - 1)
        buckets = [0] * traffic.BUCKETS
        buckets[0], buckets[4] = 90, 10          # 90 under 10 ms, 10 between 100 and 250 ms
        self.assertEqual(traffic.percentile_ms(buckets, 0.95), 175)   # half way into the 100-250 ms bucket
        self.assertEqual(traffic.percentile_ms(buckets, 0.95, max_ms=160), 160)   # never above the slowest
        self.assertAlmostEqual(traffic.percentile_ms(buckets, 0.5), 50 / 90 * 10)
        self.assertIsNone(traffic.percentile_ms([0] * traffic.BUCKETS))
        slow = [0] * traffic.BUCKETS
        slow[-1] = 1
        self.assertEqual(traffic.percentile_ms(slow, 0.95, max_ms=40000), 39500)   # 30-40 s, 95 % of the way
        self.assertEqual(traffic.percentile_ms(slow, 0.95), 30000)

    def test_rows_per_minute_and_key(self):
        agg = traffic.RequestAggregator()
        agg.record(T, "/api/series", "GET", 200, 40.0, 1000)
        agg.record(T + dt.timedelta(seconds=20), "/api/series", "GET", 204, 300.0, None)
        agg.record(T, "/api/series", "GET", 503, 5.0, 50)
        agg.record(T + dt.timedelta(minutes=1), "/api/latest", "GET", 200, 8.0, 10)
        rows = {(r["minute"], r["endpoint"], r["status_class"]): r for r in agg.take(before=T.replace(minute=5, second=0))}
        self.assertEqual(len(rows), 2)   # minute 15:05 isn't finished, so it stays
        ok = rows[(T.replace(second=0), "/api/series", 2)]
        self.assertEqual((ok["requests"], ok["total_ms"], ok["max_ms"], ok["bytes_out"]), (2, 340.0, 300.0, 1000))
        self.assertEqual(sum(ok["buckets"]), 2)
        self.assertEqual(ok["buckets"][traffic.bucket_index(40)], 1)
        self.assertEqual(rows[(T.replace(second=0), "/api/series", 5)]["requests"], 1)
        rest = agg.take()
        self.assertEqual([(r["endpoint"], r["requests"]) for r in rest], [("/api/latest", 1)])
        self.assertEqual(agg.take(), [])

    def test_enabled_only_for_postgresql(self):
        self.assertTrue(traffic.metrics_enabled("postgresql://u@h/db", {}))
        self.assertFalse(traffic.metrics_enabled("postgresql://u@h/db", {"REQUEST_METRICS": "0"}))
        self.assertFalse(traffic.metrics_enabled("sqlite://", {}))


class FlaskHookTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)

        @app.route("/api/exports/jobs/<job_id>/download")
        def download(job_id):
            return Response("a,b\n1,2\n", mimetype="text/csv")

        @app.route("/boom")
        def boom():
            raise RuntimeError("bug")

        app.logger.disabled = True   # /boom's traceback is expected
        self.recorder = traffic.MetricsRecorder(app, clock=lambda: T).install()
        self.recorder.thread_pid = os.getpid()   # no writer thread in tests
        self.client = app.test_client()

    def tearDown(self):
        self.recorder.aggregator.take()   # nothing left for the atexit flush

    def test_keeps_route_patterns_only(self):
        headers = {"X-Forwarded-For": "203.0.113.9", "User-Agent": "Secret-Browser/1.0"}
        self.client.get("/api/exports/jobs/1234-abcd/download?token=hunter2&email=a@b.ca", headers=headers)
        self.client.get("/api/exports/jobs/9999/download", headers=headers)
        self.client.get("/no/such/page/203.0.113.9?q=1", headers=headers)
        self.client.post("/api/exports/jobs/1/download")   # 405
        self.client.get("/boom")
        rows = self.recorder.aggregator.take()
        keys = sorted((r["endpoint"], r["method"], r["status_class"], r["requests"]) for r in rows)
        self.assertEqual(keys, [("(no route)", "GET", 4, 1), ("(no route)", "POST", 4, 1), ("/api/exports/jobs/<job_id>/download", "GET", 2, 2),
                                ("/boom", "GET", 5, 1)])
        dump = repr(rows)
        for private in ("1234-abcd", "hunter2", "a@b.ca", "203.0.113.9", "Secret-Browser", "no/such"):
            self.assertNotIn(private, dump)
        download = next(r for r in rows if r["status_class"] == 2)
        self.assertEqual(download["bytes_out"], 2 * len("a,b\n1,2\n"))


class DigestTextTests(unittest.TestCase):
    def test_lines(self):
        summary = {"requests": 1234, "errors_4xx": 7, "errors_5xx": 2, "bytes_out": 5 * 1024 * 1024, "p95_ms": 250,
                   "max_ms": 1800.0, "downloads": 3, "peak_per_minute": 41,
                   "peak_minute": dt.datetime(2026, 11, 10, 18, 7, tzinfo=UTC), "endpoints": []}
        text = "\n".join(traffic.traffic_lines(summary, EST_TZ))
        self.assertIn("requests: 1234, errors: 2 server (5xx), 7 client (4xx)", text)
        self.assertIn("p95 response time: about 250 ms; slowest 1800 ms", text)
        self.assertIn("data sent: 5.0 MB; CSV downloads: 3", text)
        self.assertIn("busiest minute: 41 requests at 13:07", text)   # Toronto time
        self.assertIn("no requests recorded", "\n".join(traffic.traffic_lines({**summary, "requests": 0}, EST_TZ)))
        self.assertIn("could not be read: ProgrammingError",
                      "\n".join(traffic.traffic_lines({"error": "ProgrammingError"}, EST_TZ)))

    def test_digest_includes_the_section(self):
        from utils.digest import build_digest
        freshness = {"stale": [], "checked_at": "2026-11-11T07:00:00-05:00", "groups": {}}
        _, body = build_digest("2026-11-11", freshness, {}, [], None, None, {"error": "ProgrammingError"})
        self.assertIn("Traffic yesterday", body)
        self.assertNotIn("Traffic yesterday", build_digest("2026-11-11", freshness, {}, [], None)[1])

    def test_yesterday_window_across_dst(self):
        start, end = traffic.yesterday_window(dt.datetime(2026, 11, 2, 12, 0, tzinfo=UTC), EST_TZ)
        self.assertEqual((start.isoformat(), end.isoformat()),
                         ("2026-11-01T00:00:00-04:00", "2026-11-02T00:00:00-05:00"))
        self.assertEqual(end.astimezone(UTC) - start.astimezone(UTC), dt.timedelta(hours=25))   # the fall-back day


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the request metrics against PostgreSQL")
class PostgresTests(unittest.TestCase):
    """The migration's table, two workers' rows added together, and the totals read back."""

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine
        cls.engine = create_engine(os.environ["TEST_POSTGRES_URL"])
        with cls.engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS request_metrics, uptime_probes")
            conn.exec_driver_sql(MIGRATION.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        with cls.engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS request_metrics, uptime_probes")
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql("TRUNCATE request_metrics")

    def summary(self, start, end):
        from sqlalchemy import text
        with self.engine.connect() as conn:
            return traffic.summarize_traffic(lambda sql, params: conn.execute(text(sql), params), start, end)

    def test_two_workers_add_up(self):
        worker_a, worker_b = traffic.RequestAggregator(), traffic.RequestAggregator()
        for _ in range(9):
            worker_a.record(T, "/api/series", "GET", 200, 20.0, 1000)
        worker_b.record(T, "/api/series", "GET", 200, 400.0, 3000)
        worker_b.record(T, "/api/exports/sync", "POST", 200, 900.0, 50000)
        worker_b.record(T + dt.timedelta(minutes=1), "/api/latest", "GET", 500, 3.0, 20)
        self.assertEqual(traffic.write_rows(self.engine, worker_a.take()), 1)
        self.assertEqual(traffic.write_rows(self.engine, worker_b.take()), 3)
        with self.engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT requests, total_ms, max_ms, latency_buckets, bytes_out FROM request_metrics "
                "WHERE endpoint = '/api/series'").one()
        self.assertEqual((row.requests, row.total_ms, row.max_ms, row.bytes_out), (10, 580.0, 400.0, 12000))
        expected = [0] * traffic.BUCKETS
        expected[traffic.bucket_index(20)] = 9
        expected[traffic.bucket_index(400)] = 1
        self.assertEqual(row.latency_buckets, expected)   # added element by element, in order

        s = self.summary(T - dt.timedelta(hours=1), T + dt.timedelta(hours=1))
        self.assertEqual((s["requests"], s["errors_5xx"], s["errors_4xx"], s["downloads"]), (12, 1, 0, 1))
        self.assertEqual(s["bytes_out"], 12000 + 50000 + 20)
        self.assertEqual(s["peak_per_minute"], 11)
        self.assertEqual(s["peak_minute"], T.replace(second=0))
        # 12 requests: the 95th percentile (the 11.4th) is 40 % into the slowest one's bucket, 500-1000 ms
        self.assertAlmostEqual(s["p95_ms"], 700)
        self.assertEqual(s["endpoints"][0]["endpoint"], "/api/series")
        self.assertAlmostEqual(s["endpoints"][0]["avg_ms"], 58.0)
        empty = self.summary(T + dt.timedelta(days=1), T + dt.timedelta(days=2))
        self.assertEqual((empty["requests"], empty["p95_ms"], empty["peak_per_minute"]), (0, None, 0))

    def test_backend_app_records_requests(self):
        """The real backend app counts a request once the metrics are on (PostgreSQL), and the row holds no
        address or query string."""
        from unittest import mock
        with mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", os.environ["TEST_POSTGRES_URL"]),                 mock.patch.dict(os.environ, {"REQUEST_METRICS": "1"}):
            from server import create_app
            app = create_app()
        recorder = app.extensions["request_metrics"]
        recorder.thread_pid = os.getpid()   # no writer thread in tests
        response = app.test_client().get("/health?key=hunter2", headers={"X-Forwarded-For": "198.51.100.7"})
        self.assertEqual(response.status_code, 200)
        recorder.flush(everything=True)
        with self.engine.connect() as conn:
            rows = conn.exec_driver_sql("SELECT endpoint, method, status_class, requests FROM request_metrics").all()
        self.assertEqual([tuple(r) for r in rows], [("/health", "GET", 2, 1)])
        self.assertNotIn("hunter2", repr(rows))
        self.assertNotIn("198.51.100.7", repr(rows))


if __name__ == "__main__":
    unittest.main()
