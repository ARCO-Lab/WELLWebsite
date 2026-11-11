"""The export worker makes one Flask app (and one connection pool) per process and reuses it for every task
(tasks/exports.py), instead of a new one per task whose pooled connections stayed open. Run from dashboard/backend:
python -m unittest discover -s tests -t ."""
import os
import pathlib
import sys
import shutil
import tempfile
import unittest
import uuid
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # never a real database

from config import Config  # noqa: E402

TASKS = 20


class WorkerAppTestCase(unittest.TestCase):
    database_url = None  # set by setUp

    def setUp(self):
        from tasks import exports as export_tasks
        self.tasks = export_tasks
        self.tmp = tempfile.mkdtemp(prefix="export-worker-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        patches = [
            mock.patch.object(Config, "SQLALCHEMY_DATABASE_URI", self.database_url
                              or f"sqlite:///{os.path.join(self.tmp, 'jobs.db')}"),
            mock.patch.object(Config, "EXPORTS_DIR", os.path.join(self.tmp, "exports")),
            # A fresh process: no app made yet. Restored afterwards so other tests see what they expect.
            mock.patch.object(export_tasks, "_worker_app", None),
            mock.patch.object(export_tasks, "_worker_app_pid", None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tasks.close_worker_connections)  # runs before the patches are undone
        os.makedirs(Config.EXPORTS_DIR)
        from server import create_app
        self.create_app = mock.patch.object(export_tasks, "create_app", wraps=create_app)
        self.made = self.create_app.start()
        self.addCleanup(self.create_app.stop)
        from db.database import db
        from db.models import ExportJob
        self.db = db
        with self.tasks.worker_app().app_context():
            ExportJob.__table__.create(db.engine, checkfirst=True)

    def run_tasks(self, n=TASKS):
        for _ in range(n):
            self.tasks.cleanup_expired_artifacts()


class OneAppPerProcessTests(WorkerAppTestCase):
    def test_tasks_reuse_one_app(self):
        self.run_tasks()
        self.assertEqual(self.made.call_count, 1)

    def test_a_forked_process_keeps_the_app_but_not_its_parents_connections(self):
        app = self.tasks.worker_app()
        with app.app_context():
            engine = self.db.engine
        self.tasks._worker_app_pid = -1  # as if made by the parent before this process was forked from it
        with mock.patch.object(engine, "dispose", wraps=engine.dispose) as dispose:
            self.assertIs(self.tasks.worker_app(), app)
            self.run_tasks(2)
        dispose.assert_called_once_with(close=False)  # left open for the parent, not closed under it
        self.assertEqual(self.made.call_count, 1)


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the export worker on PostgreSQL")
class PostgresConnectionTests(WorkerAppTestCase):
    """Counts the worker's connections in pg_stat_activity, by a name only this test uses."""

    def setUp(self):
        self.database_url = os.environ["TEST_POSTGRES_URL"]
        self.name = f"well-test-{uuid.uuid4().hex[:12]}"
        name = mock.patch.object(Config, "DB_APPLICATION_NAME", self.name)
        name.start()
        self.addCleanup(name.stop)
        super().setUp()

    def connections(self):
        from sqlalchemy import create_engine, text
        engine = create_engine(self.database_url)
        try:
            with engine.connect() as conn:
                return conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE application_name = :name"),
                                    {"name": self.name}).scalar()
        finally:
            engine.dispose()

    def test_many_tasks_hold_one_pools_worth_of_connections(self):
        self.run_tasks()
        held = self.connections()
        self.assertGreaterEqual(held, 1)  # the name reaches PostgreSQL, so the count means something
        self.assertLessEqual(held, 2)     # one task at a time needs one connection; a leak held one per task

    def test_a_process_closes_its_connections_when_it_exits(self):
        self.run_tasks(3)
        self.tasks.close_worker_connections()
        self.assertEqual(self.connections(), 0)


if __name__ == "__main__":
    unittest.main()
