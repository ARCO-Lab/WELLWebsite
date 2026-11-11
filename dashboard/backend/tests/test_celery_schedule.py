"""The export worker's beat schedule must point at a real task. Run from dashboard/backend:
python -m unittest discover -s tests -t ."""
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # never a real database, whatever the environment says

from tasks.celery_app import celery_app  # noqa: E402
import tasks.exports  # noqa: E402,F401  (registers the export tasks)


class BeatScheduleTests(unittest.TestCase):
    def test_expired_exports_are_cleaned_up_hourly(self):
        entry = celery_app.conf.beat_schedule["cleanup-expired-exports"]
        self.assertEqual(entry["task"], "exports.cleanup_expired_artifacts")
        self.assertEqual(entry["schedule"], 3600)

    def test_every_scheduled_task_exists(self):
        for name, entry in celery_app.conf.beat_schedule.items():
            self.assertIn(entry["task"], celery_app.tasks, name)


if __name__ == "__main__":
    unittest.main()
