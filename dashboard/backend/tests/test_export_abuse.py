"""Limits that keep exports from filling the disk (api/routes/exports.py): the free-space check, the hourly quota per
visitor, reuse of an identical ready export, and 400s (not 500s) for malformed bodies. Against a throwaway SQLite
file, as test_export_limits.py. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import types
import unittest.mock

from tests.test_export_limits import SAMPLING, AppTestCase

from config import Config
from utils.timezone import est_now

MINE = "198.51.100.7"
LOW_DISK = types.SimpleNamespace(free=2**20)  # what shutil.disk_usage says: 1 MB free


class ExportTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        from tasks import exports as export_tasks
        delay = unittest.mock.patch.object(export_tasks.generate_export_job, "delay")
        self.delay = delay.start()
        self.addCleanup(delay.stop)
        self.client = self.app.test_client()

    def post(self, path, body=None, forwarded_for=MINE, **kwargs):
        if body is not None:
            kwargs["json"] = body
        return self.client.post(path, headers={"X-Forwarded-For": forwarded_for}, **kwargs)

    def mine(self):
        from api.routes.exports import _request_fingerprint
        with self.app.test_request_context(headers={"X-Forwarded-For": MINE}):
            return _request_fingerprint()


class MalformedBodyTests(ExportTestCase):
    def test_bodies_that_arent_valid_exports_are_400s(self):
        bodies = [
            ("[1]", "application/json"),
            ('"sensor"', "application/json"),
            ("17", "application/json"),
            ("not json", "application/json"),
        ]
        payloads = [
            {"domain": ["sensor"], "start": "2026-11-01", "end": "2026-11-02"},  # unhashable domain
            {"domain": "sampling", "start": 20261101, "end": 20261102},  # numbers, not strings
            {"domain": "sampling", "start": ["2026-11-01"], "end": "2026-11-02"},
            {"domain": "sampling", "start": "0001-01-01T00:00:00+05:00", "end": "2026-11-02"},  # no local time
            {"domain": "sampling", "start": "9999-12-31T23:00:00-10:00", "end": "9999-12-31T23:30:00-10:00"},
        ]
        for path in ("/api/exports/estimate", "/api/exports/sync", "/api/exports/jobs"):
            for data, content_type in bodies:
                r = self.client.post(path, data=data, content_type=content_type)
                self.assertEqual(r.status_code, 400, (path, data))
                self.assertIn("error", r.get_json())
            for payload in payloads:
                r = self.post(path, payload)
                self.assertEqual(r.status_code, 400, (path, payload, r.get_data(as_text=True)))
        self.delay.assert_not_called()

    def test_no_debug_prints_of_the_payload(self):
        with unittest.mock.patch("builtins.print") as printed:
            self.post("/api/exports/estimate", {"domain": "sensor", "group_types": "Weather\nforged line"})
            self.post("/api/exports/jobs", {**SAMPLING, "group_types": "Weather\nforged line"})
        printed.assert_not_called()


class DiskSpaceTests(ExportTestCase):
    def low_disk(self):
        return unittest.mock.patch("api.services.exports.shutil.disk_usage", return_value=LOW_DISK)

    def test_jobs_and_direct_exports_are_refused_when_the_disk_is_low(self):
        with self.low_disk(), self.assertLogs("api.routes.exports", "WARNING"):
            job = self.post("/api/exports/jobs", SAMPLING)
            sync = self.post("/api/exports/sync", SAMPLING)
        for r in (job, sync):
            self.assertEqual(r.status_code, 507)
            self.assertIn("disk space", r.get_json()["error"])
        self.delay.assert_not_called()
        self.assertEqual(self.db.session.query(self.ExportJob).count(), 0)
        self.assertEqual(os.listdir(self.exports), [])
        # The estimate writes nothing, so it is still answered
        self.assertEqual(self.post("/api/exports/estimate", SAMPLING).status_code, 200)

    def test_the_space_needed_grows_with_the_export(self):
        from api.services.exports import EXPORT_BYTES_PER_ROW, disk_space_error
        free = Config.EXPORT_MIN_FREE_MB * 2**20 + 1000 * EXPORT_BYTES_PER_ROW
        with unittest.mock.patch("api.services.exports.shutil.disk_usage", return_value=types.SimpleNamespace(free=free)):
            self.assertIsNone(disk_space_error(1000))
            self.assertIsNotNone(disk_space_error(1001))

    def test_a_missing_exports_folder_is_checked_on_its_disk(self):
        from api.services.exports import disk_space_error
        with unittest.mock.patch.object(Config, "EXPORTS_DIR", os.path.join(self.exports, "not", "made", "yet")),                 unittest.mock.patch.object(Config, "EXPORT_MIN_FREE_MB", 0):
            self.assertIsNone(disk_space_error(10))  # the test machine has room for 800 bytes

    def test_the_worker_fails_a_queued_job_if_the_disk_filled_since(self):
        from tasks import exports as export_tasks
        self.add_job("late", "queued", estimated_rows=10)
        with unittest.mock.patch.object(export_tasks, "worker_app", return_value=self.app), \
                unittest.mock.patch.object(export_tasks, "write_export_csv") as write, self.low_disk():
            export_tasks.generate_export_job("late")
        write.assert_not_called()
        job = self.get("late")
        self.assertEqual(job.status, "failed")
        self.assertIn("disk space", job.error_message)


class HourlyQuotaTests(ExportTestCase):
    def test_finished_jobs_count_for_an_hour(self):
        mine = self.mine()
        for n in range(Config.EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER):
            self.add_job(f"done{n}", "failed", minutes_ago=50, fingerprint=mine)
        r = self.post("/api/exports/jobs", SAMPLING)
        self.assertEqual(r.status_code, 429)
        self.assertIn("last hour", r.get_json()["error"])
        self.assertEqual(r.headers["Retry-After"], "600")
        self.assertEqual(self.post("/api/exports/jobs", SAMPLING, "198.51.100.8").status_code, 202)  # someone else

    def test_older_jobs_dont_count(self):
        mine = self.mine()
        for n in range(Config.EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER):
            self.add_job(f"old{n}", "failed", minutes_ago=70, fingerprint=mine)
        self.assertEqual(self.post("/api/exports/jobs", SAMPLING).status_code, 202)

    def test_jobs_that_couldnt_be_queued_dont_count(self):
        # While the queue (Redis) is down every job fails at once with EXPORT_QUEUE_DOWN_MESSAGE; a visitor who kept
        # trying mustn't find their hour used up when it is back.
        from kombu.exceptions import OperationalError
        from api.services.exports import EXPORT_QUEUE_DOWN_MESSAGE, jobs_started_since
        self.delay.side_effect = OperationalError("Error 111 connecting to redis:6379. Connection refused.")
        for _ in range(Config.EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER + 2):
            r = self.post("/api/exports/jobs", SAMPLING)
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.get_json()["error"], EXPORT_QUEUE_DOWN_MESSAGE)
        hour_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
        self.assertEqual(jobs_started_since(self.mine(), hour_ago), 0)
        self.delay.side_effect = None
        self.assertEqual(self.post("/api/exports/jobs", SAMPLING).status_code, 202)
        # Jobs that failed for any other reason still count
        self.add_job("broke", "failed", minutes_ago=5, fingerprint=self.mine(), error_message="Something else")
        self.assertEqual(jobs_started_since(self.mine(), hour_ago), 2)

    def test_the_quota_includes_jobs_just_queued(self):
        with unittest.mock.patch.object(Config, "EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER", 3), \
                unittest.mock.patch.object(Config, "EXPORT_MAX_ACTIVE_JOBS_PER_REQUESTER", 10):
            codes = [self.post("/api/exports/jobs", {**SAMPLING, "end": f"2026-11-0{n + 2}T00:00:00"}).status_code
                     for n in range(4)]
        self.assertEqual(codes, [202, 202, 202, 429])


class ReuseTests(ExportTestCase):
    def ready_job(self, job_id, payload=None, completed_minutes_ago=2, expires_in_minutes=50, file=True,
                  created_minutes_ago=5):
        from api.services.exports import normalize_export_payload
        path = os.path.join(self.exports, job_id, "export.csv")
        if file:
            os.makedirs(os.path.dirname(path))
            pathlib.Path(path).write_text("domain\n")
        now = est_now()
        job = self.add_job(job_id, "ready", minutes_ago=created_minutes_ago, estimated_rows=7,
                           artifact_path=path, artifact_name="export.csv",
                           completed_at=now - dt.timedelta(minutes=completed_minutes_ago),
                           expires_at=now + dt.timedelta(minutes=expires_in_minutes))
        job.payload = normalize_export_payload(payload or SAMPLING)
        self.db.session.commit()
        return job

    def test_an_identical_ready_export_is_handed_back(self):
        self.ready_job("ready1")
        r = self.post("/api/exports/jobs", SAMPLING, "198.51.100.99")  # anyone's: the data is public
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual((body["job_id"], body["status"], body["reused"], body["estimated_rows"]),
                         ("ready1", "ready", True, 7))
        self.delay.assert_not_called()
        self.assertEqual(self.db.session.query(self.ExportJob).count(), 1)
        # and it can be downloaded as usual
        download = self.client.get("/api/exports/jobs/ready1/download")
        self.assertEqual(download.status_code, 200)
        download.close()

    def test_a_reused_export_doesnt_use_up_the_quota(self):
        self.ready_job("ready1")
        with unittest.mock.patch.object(Config, "EXPORT_MAX_JOBS_PER_HOUR_PER_REQUESTER", 1):
            codes = [self.post("/api/exports/jobs", SAMPLING).status_code for _ in range(5)]
        self.assertEqual(codes, [200] * 5)

    def test_not_reused_when_it_differs_expires_soon_or_its_file_is_gone(self):
        self.ready_job("other", payload={**SAMPLING, "site_ids": ["3"]})
        self.ready_job("expiring", expires_in_minutes=5)
        self.ready_job("nofile", file=False)
        r = self.post("/api/exports/jobs", SAMPLING)
        self.assertEqual(r.status_code, 202)
        self.assertNotIn(r.get_json()["job_id"], ("other", "expiring", "nofile"))

    def test_a_range_still_filling_in_is_reused_only_when_just_built(self):
        today = est_now().replace(hour=0, minute=0, second=0, microsecond=0)
        recent = {**SAMPLING, "start": today.isoformat(), "end": (today + dt.timedelta(days=1)).isoformat()}
        self.ready_job("stale", payload=recent, completed_minutes_ago=30, created_minutes_ago=35)
        self.assertEqual(self.post("/api/exports/jobs", recent).status_code, 202)
        self.ready_job("fresh", payload=recent, completed_minutes_ago=1, created_minutes_ago=3)
        r = self.post("/api/exports/jobs", recent, "198.51.100.8")
        self.assertEqual((r.status_code, r.get_json()["job_id"]), (200, "fresh"))
