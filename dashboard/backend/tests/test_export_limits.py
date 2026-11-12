"""Limits on queued exports (api/routes/exports.py), the worker's time and memory settings (tasks/celery_app.py), and
the hourly cleanup of stuck jobs, leftover files and old rows (tasks/exports.py), against a throwaway SQLite file.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # never a real database

from celery.exceptions import SoftTimeLimitExceeded  # noqa: E402

from config import Config  # noqa: E402
from utils.timezone import est_now  # noqa: E402

SAMPLING = {"domain": "sampling", "start": "2026-11-01T00:00:00", "end": "2026-11-02T00:00:00"}


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="export-limits-")
        self.exports = os.path.join(self.tmp, "exports")
        os.makedirs(self.exports)
        patches = [
            unittest.mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI",
                                       f"sqlite:///{os.path.join(self.tmp, 'jobs.db')}"),
            unittest.mock.patch.object(Config, "EXPORTS_DIR", self.exports),
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

    def add_job(self, job_id, status, minutes_ago=0, started_minutes_ago=None, fingerprint=None, **fields):
        now = est_now()
        job = self.ExportJob(id=job_id, status=status, domain="sampling", payload=SAMPLING,
                             created_at=now - dt.timedelta(minutes=minutes_ago), requester_fingerprint=fingerprint,
                             started_at=None if started_minutes_ago is None
                             else now - dt.timedelta(minutes=started_minutes_ago), **fields)
        self.db.session.add(job)
        self.db.session.commit()
        return job

    def get(self, job_id):
        self.db.session.expire_all()
        return self.db.session.get(self.ExportJob, job_id)


class JobLimitTests(AppTestCase):
    def setUp(self):
        super().setUp()
        from tasks import exports as export_tasks
        delay = unittest.mock.patch.object(export_tasks.generate_export_job, "delay")
        self.delay = delay.start()
        self.addCleanup(delay.stop)
        self.client = self.app.test_client()

    def queue(self, forwarded_for="198.51.100.7"):
        return self.client.post("/api/exports/jobs", json=SAMPLING, headers={"X-Forwarded-For": forwarded_for})

    def test_two_jobs_per_visitor_then_429_with_a_message(self):
        self.assertEqual(self.queue().status_code, 202)
        self.assertEqual(self.queue().status_code, 202)
        r = self.queue()
        self.assertEqual(r.status_code, 429)
        self.assertIn("already have exports being prepared", r.get_json()["error"])
        self.assertEqual(self.delay.call_count, 2)
        self.assertEqual(self.queue("198.51.100.8").status_code, 202)  # someone else is still served

    def test_a_job_that_cant_be_queued_fails_at_once_and_frees_its_place(self):
        from kombu.exceptions import OperationalError
        self.delay.side_effect = OperationalError("Error 111 connecting to redis:6379. Connection refused.")
        r = self.queue()
        self.assertEqual(r.status_code, 503)
        body = r.get_json()
        self.assertIn("unavailable right now", body["error"])
        self.assertNotIn("redis", body["error"].lower())   # no internals in what the visitor sees
        job = self.get(body["job_id"])
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error_message, body["error"])
        self.assertIsNotNone(job.completed_at)
        # Failed jobs don't count against the limits: once the queue is back, the same visitor gets two jobs again
        self.queue()
        self.delay.side_effect = None
        self.assertEqual(self.queue().status_code, 202)
        self.assertEqual(self.queue().status_code, 202)
        self.assertEqual(self.queue().status_code, 429)

    def test_the_last_forwarded_hop_identifies_the_visitor(self):
        # The browser can put anything before the address the proxy added: changing it doesn't make a new visitor.
        self.assertEqual(self.queue("10.0.0.1, 198.51.100.7").status_code, 202)
        self.assertEqual(self.queue("10.0.0.2, 198.51.100.7").status_code, 202)
        self.assertEqual(self.queue("10.0.0.3, 198.51.100.7").status_code, 429)

    def test_a_different_user_agent_is_the_same_visitor(self):
        for agent in ("a", "b"):
            self.client.post("/api/exports/jobs", json=SAMPLING,
                             headers={"X-Forwarded-For": "198.51.100.7", "User-Agent": agent})
        r = self.client.post("/api/exports/jobs", json=SAMPLING,
                             headers={"X-Forwarded-For": "198.51.100.7", "User-Agent": "c"})
        self.assertEqual(r.status_code, 429)

    def test_finished_and_stuck_jobs_dont_count(self):
        from api.routes.exports import _request_fingerprint
        with self.app.test_request_context(headers={"X-Forwarded-For": "198.51.100.7"}):
            mine = _request_fingerprint()
        self.add_job("done", "ready", fingerprint=mine)
        self.add_job("failed", "failed", fingerprint=mine)
        self.add_job("lost", "queued", minutes_ago=90, fingerprint=mine)  # never started
        self.add_job("dead", "running", minutes_ago=60, started_minutes_ago=30, fingerprint=mine)  # past the limit
        self.assertEqual(self.queue().status_code, 202)
        self.assertEqual(self.queue().status_code, 202)
        self.assertEqual(self.queue().status_code, 429)

    def test_a_running_job_counts(self):
        from api.routes.exports import _request_fingerprint
        with self.app.test_request_context(headers={"X-Forwarded-For": "198.51.100.7"}):
            mine = _request_fingerprint()
        self.add_job("busy", "running", minutes_ago=5, started_minutes_ago=4, fingerprint=mine)
        self.assertEqual(self.queue().status_code, 202)
        self.assertEqual(self.queue().status_code, 429)

    def test_total_limit(self):
        with unittest.mock.patch.object(Config, "EXPORT_MAX_ACTIVE_JOBS", 3):
            for n in range(3):
                self.assertEqual(self.queue(f"198.51.100.{n}").status_code, 202)
            r = self.queue("198.51.100.99")
        self.assertEqual(r.status_code, 429)
        self.assertIn("busy", r.get_json()["error"])

    def test_too_many_rows_is_refused_before_queueing(self):
        with unittest.mock.patch("api.routes.exports.estimate_rows", return_value=6_000_000):
            r = self.queue()
        self.assertEqual(r.status_code, 413)
        self.assertIn("too large", r.get_json()["error"])
        self.assertIn("5,000,000", r.get_json()["error"])
        self.delay.assert_not_called()
        self.assertEqual(self.db.session.query(self.ExportJob).count(), 0)

    def test_the_row_limit_comes_from_the_environment(self):
        # In a new interpreter, so this process's Config (which other modules hold) isn't replaced.
        app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
        env = dict(os.environ, EXPORT_MAX_ROWS="1234")
        out = subprocess.run([sys.executable, "-c", "from config import Config; print(Config.EXPORT_MAX_ROWS)"],
                             cwd=app_dir, env=env, capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.strip(), "1234")

    def test_without_a_forwarded_header_the_connection_address_is_used(self):
        from api.routes.exports import client_ip
        with self.app.test_request_context(environ_base={"REMOTE_ADDR": "192.0.2.5"}):
            self.assertEqual(client_ip(), "192.0.2.5")
        with self.app.test_request_context(headers={"X-Forwarded-For": " 1.1.1.1 , 192.0.2.9 "}):
            self.assertEqual(client_ip(), "192.0.2.9")


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the job limits against PostgreSQL")
class PostgresJobLimitTests(unittest.TestCase):
    """The limits on PostgreSQL, where the route takes a transaction lock before counting."""

    def setUp(self):
        patch = unittest.mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", os.environ["TEST_POSTGRES_URL"])
        patch.start()
        self.addCleanup(patch.stop)
        from server import create_app
        from db.database import db
        from db.models import ExportJob
        from tasks import exports as export_tasks
        self.db, self.ExportJob = db, ExportJob
        self.app = create_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        db.session.query(ExportJob).delete()
        db.session.commit()
        delay = unittest.mock.patch.object(export_tasks.generate_export_job, "delay")
        delay.start()
        self.addCleanup(delay.stop)

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.db.engine.dispose()
        self.ctx.pop()

    def test_two_jobs_per_visitor(self):
        client = self.app.test_client()
        codes = [client.post("/api/exports/jobs", json=SAMPLING, headers={"X-Forwarded-For": "198.51.100.7"})
                 .status_code for _ in range(3)]
        self.assertEqual(codes, [202, 202, 429])


class WorkerSettingsTests(unittest.TestCase):
    def test_time_memory_and_redelivery_settings(self):
        from tasks.celery_app import celery_app
        conf = celery_app.conf
        self.assertEqual((conf.task_soft_time_limit, conf.task_time_limit), (15 * 60, 20 * 60))
        self.assertTrue(conf.task_acks_late)
        self.assertFalse(conf.task_reject_on_worker_lost)
        self.assertGreater(conf.worker_max_memory_per_child, 0)


class TaskTests(AppTestCase):
    def run_task(self, job_id, **patches):
        from tasks import exports as export_tasks
        with unittest.mock.patch.object(export_tasks, "worker_app", return_value=self.app):
            with unittest.mock.patch.object(export_tasks, "write_export_csv", **patches) as write:
                try:
                    export_tasks.generate_export_job(job_id)
                except SoftTimeLimitExceeded:
                    pass  # re-raised by the task after marking the job failed, which is what the tests check
        return write

    def test_a_redelivered_job_that_was_running_is_failed_not_rerun(self):
        from tasks.exports import EXPORT_INTERRUPTED_MESSAGE
        self.add_job("again", "running", minutes_ago=70, started_minutes_ago=65)
        partial = os.path.join(self.exports, "again", "x.csv")
        os.makedirs(os.path.dirname(partial))
        pathlib.Path(partial).write_text("half a file")
        write = self.run_task("again", return_value=0)
        write.assert_not_called()
        job = self.get("again")
        self.assertEqual((job.status, job.error_message), ("failed", EXPORT_INTERRUPTED_MESSAGE))
        self.assertFalse(os.path.exists(os.path.dirname(partial)))

    def test_a_settled_job_is_left_alone(self):
        self.add_job("old", "failed", error_message="x")
        write = self.run_task("old", return_value=0)
        write.assert_not_called()
        self.assertEqual((self.get("old").status, self.get("old").error_message), ("failed", "x"))

    def test_a_job_past_the_soft_time_limit_is_failed_with_a_plain_message(self):
        from tasks.exports import EXPORT_TOO_SLOW_MESSAGE
        self.add_job("slow", "queued")
        self.run_task("slow", side_effect=SoftTimeLimitExceeded())
        job = self.get("slow")
        self.assertEqual((job.status, job.error_message), ("failed", EXPORT_TOO_SLOW_MESSAGE))

    def test_a_queued_job_runs(self):
        self.add_job("fine", "queued", estimated_rows=0)
        write = self.run_task("fine", return_value=0)
        write.assert_called_once()
        self.assertEqual(self.get("fine").status, "ready")

    def test_a_job_is_marked_failed_even_after_a_database_error(self):
        from sqlalchemy.exc import IntegrityError
        from tasks import exports as export_tasks
        self.add_job("dbfail", "queued")

        def break_the_session(**kwargs):
            self.db.session.add(self.ExportJob(id="dbfail", status="queued", domain="sampling", payload={}))
            self.db.session.flush()  # a duplicate key: the session's transaction is now unusable

        with unittest.mock.patch.object(export_tasks, "worker_app", return_value=self.app):
            with unittest.mock.patch.object(export_tasks, "write_export_csv", side_effect=break_the_session):
                with self.assertRaises(IntegrityError):
                    export_tasks.generate_export_job("dbfail")
        self.assertEqual(self.get("dbfail").status, "failed")

    def test_the_status_route_settles_a_job_whose_worker_died(self):
        from api.services.exports import EXPORT_TOO_SLOW_MESSAGE
        self.add_job("oom", "running", minutes_ago=40, started_minutes_ago=26)
        self.add_job("alive", "running", minutes_ago=5, started_minutes_ago=4)
        client = self.app.test_client()
        body = client.get("/api/exports/jobs/oom").get_json()
        self.assertEqual((body["status"], body["error_message"]), ("failed", EXPORT_TOO_SLOW_MESSAGE))
        self.assertEqual(self.get("oom").status, "failed")
        self.assertEqual(client.get("/api/exports/jobs/alive").get_json()["status"], "running")


class StreamCleanupTests(AppTestCase):
    def test_a_failed_write_returns_the_streaming_connection(self):
        from api.services import exports as export_service
        from db.models import SamplingMeasurement
        when = dt.datetime(2026, 11, 1, 10, 0)
        self.db.session.add_all(SamplingMeasurement(site_id=f"S{i}", creek_id="C", measurement_type="pH", unit="",
                                                    value=7.0, recorded_at=when) for i in range(3))
        self.db.session.commit()
        self.db.session.close()
        calls = []

        def fail_on_a_data_row(row):
            calls.append(row)
            if len(calls) == 2:  # the header is call 1
                raise OSError("disk full")

        with unittest.mock.patch.object(export_service._SafeCsvWriter, "writerow",
                                        side_effect=lambda row: fail_on_a_data_row(row)):
            error = None
            try:
                export_service.write_export_csv(SAMPLING, os.path.join(self.exports, "x.csv"), estimated_rows=3)
            except OSError as exc:
                error = exc
        # The error's traceback is still alive (as it is while the task logs and handles it), and with it the stack
        # the row generator was used in: the connection must be back in the pool anyway.
        self.assertIsNotNone(error.__traceback__)
        self.assertEqual(self.db.engine.pool.checkedout(), 0)


# 2026-03-08: clocks jump from 02:00 EST to 03:00 EDT. 06:50 UTC is 01:50 EST; 07:01 UTC is 03:01 EDT, 11 real
# minutes later though the wall clock moved 71.
SPRING_START = dt.datetime(2026, 3, 8, 1, 50)  # naive wall time, as est_now() stores it


def frozen_clock(instant_utc):
    """Patch the clocks the export code reads (est_now() and the job age checks) to `instant_utc`."""
    class Frozen(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return instant_utc.astimezone(tz)
    patches = [unittest.mock.patch(target, Frozen)
               for target in ("utils.timezone.datetime", "api.services.exports.datetime")]

    class Both:
        def __enter__(self):
            for p in patches:
                p.start()

        def __exit__(self, *exc):
            for p in reversed(patches):
                p.stop()
    return Both()


class JobAgeAcrossDstTests(unittest.TestCase):
    """Job ages are real elapsed time, not the difference of wall-clock readings."""

    def job(self, status, created_at, started_at=None):
        from types import SimpleNamespace
        return SimpleNamespace(status=status, created_at=created_at, started_at=started_at)

    def utc(self, hour, minute):
        return dt.datetime(2026, 3, 8, hour, minute, tzinfo=dt.timezone.utc)

    def test_a_running_job_across_the_spring_forward_jump(self):
        from api.services.exports import job_is_stuck
        running = self.job("running", SPRING_START, SPRING_START)
        self.assertFalse(job_is_stuck(running, self.utc(7, 1)))   # 11 real minutes (wall clock: 71)
        self.assertFalse(job_is_stuck(running, self.utc(7, 14)))  # 24 minutes, under the 25-minute limit
        self.assertTrue(job_is_stuck(running, self.utc(7, 16)))   # 26 minutes

    def test_a_queued_job_across_the_spring_forward_jump(self):
        from api.services.exports import job_is_stuck
        queued = self.job("queued", dt.datetime(2026, 3, 8, 1, 30))
        self.assertFalse(job_is_stuck(queued, self.utc(7, 20)))  # 50 real minutes (wall clock: 110)
        self.assertTrue(job_is_stuck(queued, self.utc(7, 31)))

    def test_the_repeated_fall_back_hour_never_makes_a_job_look_older(self):
        from api.services.exports import job_is_stuck
        # 01:50 on 2026-11-01 happens twice; read as the later one (01:50 EST = 06:50 UTC)
        running = self.job("running", dt.datetime(2026, 11, 1, 1, 50), dt.datetime(2026, 11, 1, 1, 50))
        self.assertFalse(job_is_stuck(running, dt.datetime(2026, 11, 1, 7, 10, tzinfo=dt.timezone.utc)))

    def test_settled_jobs_are_never_stuck(self):
        from api.services.exports import job_is_stuck
        self.assertFalse(job_is_stuck(self.job("ready", dt.datetime(2020, 1, 1)), self.utc(7, 0)))


class SpringForwardRouteAndCleanupTests(AppTestCase):
    def add_spring_job(self):
        job = self.ExportJob(id="spring", status="running", domain="sampling", payload=SAMPLING,
                             created_at=SPRING_START, started_at=SPRING_START,
                             requester_fingerprint="f")
        self.db.session.add(job)
        self.db.session.commit()
        folder = os.path.join(self.exports, "spring")
        os.makedirs(folder)
        pathlib.Path(folder, "x.csv").write_text("being written")
        return folder

    def test_a_live_job_isnt_settled_or_cleaned_up_after_the_jump(self):
        folder = self.add_spring_job()
        with frozen_clock(dt.datetime(2026, 3, 8, 7, 1, tzinfo=dt.timezone.utc)):  # 03:01 EDT
            body = self.app.test_client().get("/api/exports/jobs/spring").get_json()
            from tasks.exports import cleanup_expired_artifacts
            with unittest.mock.patch("tasks.exports.worker_app", return_value=self.app):
                cleanup_expired_artifacts()
        self.assertEqual(body["status"], "running")
        self.assertEqual(self.get("spring").status, "running")
        self.assertTrue(os.path.isdir(folder))

    def test_it_still_counts_against_the_limits(self):
        from api.services.exports import live_jobs
        self.add_spring_job()
        with frozen_clock(dt.datetime(2026, 3, 8, 7, 1, tzinfo=dt.timezone.utc)):
            self.assertEqual([job.id for job in live_jobs()], ["spring"])
        with frozen_clock(dt.datetime(2026, 3, 8, 7, 16, tzinfo=dt.timezone.utc)):
            self.assertEqual(live_jobs(), [])


class CleanupTests(AppTestCase):
    def run_cleanup(self):
        from tasks.exports import cleanup_expired_artifacts
        with unittest.mock.patch("tasks.exports.worker_app", return_value=self.app):
            cleanup_expired_artifacts()
        self.db.session.expire_all()

    def file(self, *parts, hours_old=0.0):
        path = os.path.join(self.exports, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pathlib.Path(path).write_text("a,b\n")
        if hours_old:
            then = time.time() - hours_old * 3600
            os.utime(path, (then, then))
            if os.path.dirname(path) != self.exports:
                os.utime(os.path.dirname(path), (then, then))
        return path

    def test_stuck_jobs_are_failed_and_their_files_deleted(self):
        from tasks.exports import EXPORT_FAILED_MESSAGE, EXPORT_TOO_SLOW_MESSAGE
        self.add_job("lost", "queued", minutes_ago=61)
        self.add_job("dead", "running", minutes_ago=40, started_minutes_ago=26)
        self.add_job("waiting", "queued", minutes_ago=30)
        self.add_job("working", "running", minutes_ago=20, started_minutes_ago=19)
        partial = self.file("dead", "x.csv")
        working = self.file("working", "x.csv", hours_old=5)  # its folder is kept, however old
        self.run_cleanup()
        self.assertEqual((self.get("lost").status, self.get("lost").error_message), ("failed", EXPORT_FAILED_MESSAGE))
        self.assertEqual((self.get("dead").status, self.get("dead").error_message),
                         ("failed", EXPORT_TOO_SLOW_MESSAGE))
        self.assertIsNotNone(self.get("dead").completed_at)
        self.assertEqual(self.get("waiting").status, "queued")
        self.assertEqual(self.get("working").status, "running")
        self.assertFalse(os.path.exists(os.path.dirname(partial)))
        self.assertTrue(os.path.exists(working))

    def test_old_files_no_job_points_at_are_deleted(self):
        sync_left = self.file("sync_export_abc.csv", hours_old=3.5)
        died = self.file("gone-job", "WELL_x.csv", hours_old=3.5)
        recent_sync = self.file("sync_export_new.csv", hours_old=0.1)  # may still be downloading
        recent = self.file("new-job", "WELL_x.csv", hours_old=2.5)  # within TTL + 2 h
        self.run_cleanup()
        self.assertFalse(os.path.exists(sync_left))
        self.assertFalse(os.path.exists(died))
        self.assertFalse(os.path.exists(os.path.dirname(died)))
        self.assertTrue(os.path.exists(recent_sync))
        self.assertTrue(os.path.exists(recent))
        self.assertTrue(os.path.isdir(self.exports))

    def test_a_file_a_job_still_points_at_is_kept(self):
        kept = self.file("ready-job", "WELL_x.csv", hours_old=4)
        self.add_job("ready-job", "ready", artifact_path=kept, artifact_name="WELL_x.csv",
                     expires_at=est_now() + dt.timedelta(minutes=30))
        self.run_cleanup()
        self.assertTrue(os.path.exists(kept))

    def test_old_rows_are_pruned(self):
        self.add_job("ancient", "expired", minutes_ago=31 * 24 * 60)
        self.add_job("ancient-failed", "failed", minutes_ago=31 * 24 * 60)
        self.add_job("recent", "expired", minutes_ago=29 * 24 * 60)
        stuck_file = self.file("ancient-file", "x.csv")
        self.add_job("ancient-file", "ready", minutes_ago=31 * 24 * 60, artifact_path=stuck_file,
                     expires_at=est_now() + dt.timedelta(minutes=30))
        self.run_cleanup()
        self.assertIsNone(self.get("ancient"))
        self.assertIsNone(self.get("ancient-failed"))
        self.assertIsNotNone(self.get("recent"))
        self.assertIsNotNone(self.get("ancient-file"))  # still points at a file

    def test_a_failed_prune_doesnt_stop_the_file_cleanup(self):
        from sqlalchemy.exc import ProgrammingError
        orphan = self.file("sync_export_abc.csv", hours_old=4)
        self.add_job("ancient", "expired", minutes_ago=31 * 24 * 60)
        denied = ProgrammingError("DELETE", {}, Exception("denied"))
        with unittest.mock.patch("sqlalchemy.orm.Query.delete", side_effect=denied):
            self.run_cleanup()
        self.assertFalse(os.path.exists(orphan))
        self.assertIsNotNone(self.get("ancient"))


if __name__ == "__main__":
    unittest.main()
