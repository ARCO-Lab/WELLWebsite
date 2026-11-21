"""Tests for the /api/samples/validate and /api/samples/format routes, run against an in-memory SQLite database
(the routes themselves touch no database). Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from config import Config  # noqa: E402
from server import create_app  # noqa: E402
from utils import sampling_csv  # noqa: E402
import api.routes.samples as samples_route  # noqa: E402

Config.SQLALCHEMY_DATABASE_URI = "sqlite://"

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "sampling"


class SamplingValidateRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def post_json(self, text):
        return self.client.post("/api/samples/validate", json={"csv": text})

    def test_valid_file_passes_and_reports_counts(self):
        text = (FIXTURES / "valid.csv").read_text(encoding="utf-8")
        r = self.post_json(text)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["problems"], [])
        self.assertIsInstance(body["summary"], str)
        self.assertGreater(body["counts"]["readings"], 0)

    def test_route_problems_match_the_validator_itself(self):
        # The route must say exactly what the real import validator says: same rows, columns and messages, so the
        # checker can never drift from the format spec.
        text = (FIXTURES / "unknown_site.csv").read_text(encoding="utf-8")
        r = self.post_json(text)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertFalse(body["ok"])
        expected = [{"row": e.row, "column": e.column, "message": e.message}
                    for e in sampling_csv.validate_csv(text.encode("utf-8")).errors]
        self.assertEqual(body["problems"], expected)
        self.assertTrue(any("unknown site" in p["message"] for p in body["problems"]))

    def test_missing_required_column_is_reported(self):
        text = (FIXTURES / "missing_column.csv").read_text(encoding="utf-8")
        body = self.post_json(text).get_json()
        self.assertFalse(body["ok"])
        self.assertTrue(any(p["column"] == "parameter" and "missing" in p["message"]
                            for p in body["problems"]))

    def test_ambiguous_date_is_refused_not_guessed(self):
        text = (FIXTURES / "bad_dates.csv").read_text(encoding="utf-8")
        body = self.post_json(text).get_json()
        self.assertFalse(body["ok"])
        self.assertTrue(any("YYYY-MM-DD" in p["message"] or "ambiguous" in p["message"]
                            for p in body["problems"]))

    def test_raw_body_is_accepted_too(self):
        text = (FIXTURES / "valid.csv").read_text(encoding="utf-8")
        r = self.client.post("/api/samples/validate", data=text.encode("utf-8"),
                             content_type="text/csv")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])

    def test_wrong_format_sensor_file_returns_problems_not_an_error(self):
        # Sentry #172: a West Campus sensor monthly file (columns ID, Timestamp, Group, ..., not the sampling format)
        # was pasted into the checker. The validator must RUN and list the format problems as a normal 200 answer,
        # never crash into a 500: the checker expects a JSON verdict, not an error page.
        path = (pathlib.Path(__file__).resolve().parent / "golden" / "monthly"
                / "2026-10_WELLWestCampus.csv")
        text = path.read_text(encoding="utf-8")
        r = self.post_json(text)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertFalse(body["ok"])
        self.assertTrue(any("unknown column" in p["message"] for p in body["problems"]))
        self.assertTrue(any(p["column"] == "date" and "missing" in p["message"] for p in body["problems"]))

    def test_non_string_csv_is_a_400(self):
        r = self.client.post("/api/samples/validate", json={"csv": 123})
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.get_json())

    def test_malformed_json_body_is_a_json_400(self):
        # A body that claims to be JSON but isn't must still get a JSON error, never Flask's HTML 400 page.
        r = self.client.post("/api/samples/validate", data='{"csv": "a,b', content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type.split(";")[0], "application/json")
        self.assertIn("error", r.get_json())

    def test_oversize_body_is_refused_with_413(self):
        big = ("x" * 1000 + "\n") * 2100  # > MAX_VALIDATE_BYTES (2 MB)
        self.assertGreater(len(big.encode("utf-8")), samples_route.MAX_VALIDATE_BYTES)
        r = self.client.post("/api/samples/validate", data=big.encode("utf-8"),
                             content_type="text/csv")
        self.assertEqual(r.status_code, 413)

    def test_validate_never_persists(self):
        # A valid file must leave nothing behind: the route must not write to the sampling table.
        from db.database import db
        from db.models import SamplingMeasurement
        text = (FIXTURES / "valid.csv").read_text(encoding="utf-8")
        with self.app.app_context():
            db.create_all()
            self.post_json(text)
            self.assertEqual(db.session.query(SamplingMeasurement).count(), 0)
            db.drop_all()


class SamplingFormatRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_format_lists_come_from_the_validator(self):
        body = self.client.get("/api/samples/format").get_json()
        self.assertEqual(body["required_columns"], list(sampling_csv.REQUIRED_COLUMNS))
        self.assertEqual(body["optional_columns"], list(sampling_csv.OPTIONAL_COLUMNS))
        self.assertEqual([s["number"] for s in body["sites"]], [s.id for s in sampling_csv.SITES])
        self.assertEqual([p["name"] for p in body["parameters"]], [p.name for p in sampling_csv.PARAMETERS])
        # Every parameter carries the one unit values must be in.
        units = {p["name"]: p["unit"] for p in body["parameters"]}
        self.assertEqual(units["E. coli"], "CFU/100 mL")


if __name__ == "__main__":
    unittest.main()
