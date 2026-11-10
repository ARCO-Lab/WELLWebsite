"""Tests for the hourly export cleanup (tasks/exports.py) and DST-safe expiry times, against a throwaway
SQLite file. Run from dashboard/backend: python -m unittest discover -s tests"""
import datetime as dt
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("DATABASE_URL", "sqlite://")  # never a real database

from config import Config  # noqa: E402
from utils.timezone import est_after, est_now  # noqa: E402


class EstAfterTests(unittest.TestCase):
    def test_adds_real_time_across_the_spring_dst_jump(self):
        # 01:45 EST on 2026-03-08; clocks jump from 02:00 to 03:00, so 60 real minutes later it's 03:45
        start = dt.datetime(2026, 3, 8, 6, 45, tzinfo=dt.timezone.utc)
        self.assertEqual(est_after(60, start), dt.datetime(2026, 3, 8, 3, 45))

    def test_ordinary_day(self):
        start = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)  # 07:00 EST
        self.assertEqual(est_after(60, start), dt.datetime(2026, 11, 10, 8, 0))


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="exports-test-")
        self.exports = os.path.join(self.tmp, "exports")
        os.makedirs(self.exports)
        patches = [
            mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{os.path.join(self.tmp, 'jobs.db')}"),
            mock.patch.object(Config, "EXPORTS_DIR", self.exports),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        from server import create_app
        from db.database import db
        from db.models import ExportJob
        self.db, self.ExportJob = db, ExportJob
        self.app = create_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.db.engine.dispose()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def job(self, job_id, minutes_from_now, path):
        if path and not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            pathlib.Path(path).write_text("a,b\n")
        j = self.ExportJob(id=job_id, status="ready", domain="sensor", payload={}, artifact_path=path,
                           artifact_name="x.csv", expires_at=est_now() + dt.timedelta(minutes=minutes_from_now))
        self.db.session.add(j)
        self.db.session.commit()
        return path

    def run_cleanup(self):
        from tasks.exports import cleanup_expired_artifacts
        cleanup_expired_artifacts()
        self.db.session.expire_all()

    def get(self, job_id):
        return self.db.session.get(self.ExportJob, job_id)

    def test_deletes_files_more_than_the_grace_period_past_expiry(self):
        path = self.job("old", -90, os.path.join(self.exports, "old", "x.csv"))
        self.run_cleanup()
        self.assertFalse(os.path.exists(path))
        self.assertFalse(os.path.exists(os.path.dirname(path)))  # the per-job folder too
        self.assertEqual((self.get("old").status, self.get("old").artifact_path), ("expired", None))

    def test_keeps_files_within_the_grace_period(self):
        path = self.job("recent", -30, os.path.join(self.exports, "recent", "x.csv"))
        self.run_cleanup()
        self.assertTrue(os.path.exists(path))
        self.assertEqual(self.get("recent").status, "ready")

    def test_keeps_a_shared_file_while_another_job_still_uses_it(self):
        shared = os.path.join(self.exports, "WELL_20261101_20261101.csv")  # pre-per-job-folder layout
        self.job("older", -120, shared)
        self.job("newer", 30, shared)
        self.run_cleanup()
        self.assertTrue(os.path.exists(shared))
        self.assertEqual((self.get("older").status, self.get("older").artifact_path), ("expired", None))
        self.assertEqual(self.get("newer").artifact_path, shared)
        self.assertTrue(os.path.exists(self.exports))  # never removes EXPORTS_DIR itself

    def test_a_failed_delete_is_retried_on_the_next_run(self):
        path = self.job("stuck", -90, os.path.join(self.exports, "stuck", "x.csv"))
        with mock.patch("tasks.exports.os.remove", side_effect=OSError("busy")):
            self.run_cleanup()
        self.assertEqual((self.get("stuck").status, self.get("stuck").artifact_path), ("ready", path))
        self.run_cleanup()
        self.assertFalse(os.path.exists(path))
        self.assertIsNone(self.get("stuck").artifact_path)

    def test_download_of_an_expired_job_leaves_the_file_for_cleanup(self):
        path = self.job("late", -5, os.path.join(self.exports, "late", "x.csv"))
        r = self.app.test_client().get("/api/exports/jobs/late/download")
        self.assertEqual(r.status_code, 410)
        self.db.session.expire_all()
        self.assertEqual((self.get("late").status, self.get("late").artifact_path), ("expired", path))
        self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
