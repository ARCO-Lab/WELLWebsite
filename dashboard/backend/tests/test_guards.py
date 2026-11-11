"""Tests for utils/guards.py. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils.guards import require_wipe_permission  # noqa: E402


class RequireWipePermissionTests(unittest.TestCase):
    def test_refuses_without_the_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            require_wipe_permission("every sensor measurement", env={})
        self.assertIn("ALLOW_WIPE=1", str(ctx.exception))
        self.assertIn("backup", str(ctx.exception))

    def test_only_exactly_1_counts(self):
        for value in ("0", "yes", "true", " 1", ""):
            with self.assertRaises(SystemExit):
                require_wipe_permission("x", env={"ALLOW_WIPE": value})

    def test_allows_with_the_flag(self):
        self.assertIsNone(require_wipe_permission("x", env={"ALLOW_WIPE": "1"}))

    def test_own_advice_replaces_the_backup_advice(self):
        with self.assertRaises(SystemExit) as ctx:
            require_wipe_permission("x", env={}, advice="Use the backfill instead.")
        message = str(ctx.exception)
        self.assertIn("Refusing to delete x", message)
        self.assertTrue(message.endswith("Use the backfill instead."))
        self.assertNotIn("pg_dump", message)

    def test_own_advice_keeps_the_gate(self):
        with self.assertRaises(SystemExit):
            require_wipe_permission("x", env={"ALLOW_WIPE": "yes"}, advice="a")
        self.assertIsNone(require_wipe_permission("x", env={"ALLOW_WIPE": "1"}, advice="a"))


if __name__ == "__main__":
    unittest.main()
