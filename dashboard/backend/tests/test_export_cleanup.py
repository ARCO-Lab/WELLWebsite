"""Tests for the hourly export cleanup (tasks/exports.py) and DST-safe expiry times, against a throwaway
SQLite file. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import shutil
import sys
import tempfile
from unittest import TestCase, main, mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # never a real database

from config import Config  # noqa: E402
from utils.timezone import est_after, est_now, est_passed  # noqa: E402

# 2026-11-01 05:30 UTC is 01:30 EDT; clocks fall back at 02:00 EDT, so 60 real minutes later it is 01:30 EST.
FALL_BACK_DONE = dt.datetime(2026, 11, 1, 5, 30, tzinfo=dt.timezone.utc)


def frozen_clock(instant_utc):
    """Patch the clock utils.timezone reads, so est_now(), est_after() and est_passed() see `instant_utc`."""
    class Frozen(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return instant_utc.astimezone(tz)
    return mock.patch("utils.timezone.datetime", Frozen)


# Job ids are UUIDs, as the job routes require (<uuid:job_id>)
LATE_ID = "00000000-0000-4000-8000-000000000001"
FRESH_ID = "00000000-0000-4000-8000-000000000002"
DST_ID = "00000000-0000-4000-8000-000000000003"
LEAKY_ID = "00000000-0000-4000-8000-000000000004"


class EstAfterTests(TestCase):
    def test_adds_real_time_across_the_spring_dst_jump(self):
        # 01:45 EST on 2026-03-08; clocks jump from 02:00 to 03:00, so 60 real minutes later it's 03:45
        start = dt.datetime(2026, 3, 8, 6, 45, tzinfo=dt.timezone.utc)
        self.assertEqual(est_after(60, start), dt.datetime(2026, 3, 8, 3, 45))

    def test_ordinary_day(self):
        start = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)  # 07:00 EST
        self.assertEqual(est_after(60, start), dt.datetime(2026, 11, 10, 8, 0))

    def test_fall_back_expiry_reads_the_same_as_the_completion_time(self):
        self.assertEqual(est_after(60, FALL_BACK_DONE), dt.datetime(2026, 11, 1, 1, 30))


class EstPassedTests(TestCase):
    def test_a_full_window_on_the_fall_back_night(self):
        expires = est_after(60, FALL_BACK_DONE)  # 01:30, meaning 01:30 EST
        self.assertFalse(est_passed(expires, FALL_BACK_DONE + dt.timedelta(seconds=3)))  # naive 01:30:03 > 01:30
        self.assertFalse(est_passed(expires, FALL_BACK_DONE + dt.timedelta(minutes=59)))
        self.assertTrue(est_passed(expires, FALL_BACK_DONE + dt.timedelta(minutes=61)))

    def test_ordinary_times(self):
        now = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)  # 07:00 EST
        self.assertTrue(est_passed(dt.datetime(2026, 11, 10, 6, 59), now))
        self.assertFalse(est_passed(dt.datetime(2026, 11, 10, 7, 1), now))


class CleanupTests(TestCase):
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

    def job(self, job_id, minutes_from_now, path, expires_at=None):
        if path and not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            pathlib.Path(path).write_text("a,b\n")
        expires_at = expires_at or est_now() + dt.timedelta(minutes=minutes_from_now)
        j = self.ExportJob(id=job_id, status="ready", domain="sensor", payload={}, artifact_path=path,
                           artifact_name="x.csv", expires_at=expires_at)
        self.db.session.add(j)
        self.db.session.commit()
        return path

    def run_cleanup(self):
        from tasks.exports import cleanup_expired_artifacts
        with mock.patch("tasks.exports.worker_app", return_value=self.app):
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
        path = self.job(LATE_ID, -5, os.path.join(self.exports, LATE_ID, "x.csv"))
        r = self.app.test_client().get(f"/api/exports/jobs/{LATE_ID}/download")
        self.assertEqual(r.status_code, 410)
        self.db.session.expire_all()
        self.assertEqual((self.get(LATE_ID).status, self.get(LATE_ID).artifact_path), ("expired", path))
        self.assertTrue(os.path.exists(path))

    def test_download_within_the_window(self):
        self.job(FRESH_ID, 30, os.path.join(self.exports, FRESH_ID, "x.csv"))
        r = self.app.test_client().get(f"/api/exports/jobs/{FRESH_ID}/download")
        self.assertEqual((r.status_code, r.data), (200, b"a,b\n"))
        r.close()

    def test_download_right_after_ready_on_the_fall_back_night(self):
        self.job(DST_ID, 0, os.path.join(self.exports, DST_ID, "x.csv"), expires_at=est_after(60, FALL_BACK_DONE))
        client = self.app.test_client()
        with frozen_clock(FALL_BACK_DONE + dt.timedelta(seconds=3)):  # when the page asks for the file
            r = client.get(f"/api/exports/jobs/{DST_ID}/download")
        self.assertEqual(r.status_code, 200)
        r.close()
        with frozen_clock(FALL_BACK_DONE + dt.timedelta(minutes=61)):
            self.assertEqual(client.get(f"/api/exports/jobs/{DST_ID}/download").status_code, 410)

    def fail_job(self, job_id, exc):
        """Runs generate_export_job with write_export_csv raising `exc`, and returns the job afterwards."""
        from tasks import exports as export_tasks
        payload = {"domain": "sampling", "start": "2026-11-01T00:00:00", "end": "2026-11-02T00:00:00"}
        self.db.session.add(self.ExportJob(id=job_id, status="queued", domain="sampling", payload=payload,
                                           estimated_rows=1))
        self.db.session.commit()
        fail = mock.patch.object(export_tasks, "write_export_csv", side_effect=exc)
        with fail, mock.patch.object(export_tasks, "worker_app", return_value=self.app):
            with self.assertRaises(type(exc)):
                export_tasks.generate_export_job(job_id)
        self.db.session.expire_all()
        return self.get(job_id)

    def test_a_failed_job_hides_the_internal_error_from_the_page(self):
        from tasks.exports import EXPORT_FAILED_MESSAGE
        leak = RuntimeError("(psycopg2.OperationalError) SELECT * FROM measurements WHERE site_id = %(p)s "
                            "(Background on this error at: https://sqlalche.me/e/20/e3q8) /app/app/db/x.py")
        job = self.fail_job(LEAKY_ID, leak)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error_message, EXPORT_FAILED_MESSAGE)
        r = self.app.test_client().get(f"/api/exports/jobs/{LEAKY_ID}")
        self.assertNotIn("SELECT", r.get_data(as_text=True))
        self.assertNotIn("sqlalche.me", r.get_data(as_text=True))

    def test_a_failed_job_keeps_a_validation_message(self):
        from api.services.exports import ExportValidationError
        job = self.fail_job("invalid", ExportValidationError("start must be before end"))
        self.assertEqual(job.error_message, "start must be before end")

    def test_a_failed_job_hides_the_drivers_value_error(self):
        # psycopg2 refuses a NUL character with a plain ValueError; its text isn't a message for the user
        from tasks.exports import EXPORT_FAILED_MESSAGE
        job = self.fail_job("nul", ValueError("A string literal cannot contain NUL (0x00) characters."))
        self.assertEqual(job.error_message, EXPORT_FAILED_MESSAGE)

    def test_a_job_stopped_by_its_size_limit_says_why_and_is_not_re_raised(self):
        from api.services.exports import ExportAborted
        from tasks import exports as export_tasks
        payload = {"domain": "sampling", "start": "2026-11-01T00:00:00", "end": "2026-11-02T00:00:00"}
        self.db.session.add(self.ExportJob(id="big", status="queued", domain="sampling", payload=payload,
                                           estimated_rows=1))
        self.db.session.commit()
        stopped = ExportAborted("This export is too large to prepare.", 413)
        with mock.patch.object(export_tasks, "write_export_csv", side_effect=stopped), \
                mock.patch.object(export_tasks, "worker_app", return_value=self.app):
            export_tasks.generate_export_job("big")   # a limit doing its job: logged, not raised to Sentry
        self.db.session.expire_all()
        job = self.get("big")
        self.assertEqual((job.status, job.error_message), ("failed", "This export is too large to prepare."))

    def test_a_failed_job_hides_a_value_error_subclass(self):
        from tasks.exports import EXPORT_FAILED_MESSAGE
        job = self.fail_job("decode", UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))
        self.assertEqual(job.error_message, EXPORT_FAILED_MESSAGE)

    def test_a_failed_export_deletes_the_file_it_wrote(self):
        from tasks import exports as export_tasks
        payload = {"domain": "sampling", "start": "2026-11-01T00:00:00", "end": "2026-11-02T00:00:00"}
        self.db.session.add(self.ExportJob(id="broken", status="queued", domain="sampling", payload=payload,
                                           estimated_rows=1))
        self.db.session.commit()

        def write_then_fail(payload, output_path, **kwargs):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            pathlib.Path(output_path).write_text("domain\n")
            raise RuntimeError("database went away")

        fail = mock.patch.object(export_tasks, "write_export_csv", side_effect=write_then_fail)
        with fail, mock.patch.object(export_tasks, "worker_app", return_value=self.app):
            with self.assertRaises(RuntimeError):
                export_tasks.generate_export_job("broken")
        self.db.session.expire_all()
        self.assertEqual(self.get("broken").status, "failed")
        self.assertEqual(os.listdir(self.exports), [])  # neither the file nor its job folder is left


if __name__ == "__main__":
    main()
