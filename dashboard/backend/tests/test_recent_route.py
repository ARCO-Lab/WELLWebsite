"""Tests for the /api/recent route (the dashboard's latest sampling cards), run against an in-memory SQLite
database. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from config import Config  # noqa: E402
from server import create_app  # noqa: E402
from db.database import db  # noqa: E402
from db.models import SamplingMeasurement  # noqa: E402

# Config reads DATABASE_URL once, when first imported, so a test module imported earlier may have set it already.
Config.SQLALCHEMY_DATABASE_URI = "sqlite://"


def sample(site, mtype, value, at, unit="CFU/100 mL"):
    return SamplingMeasurement(site_id=site, creek_id="20962187", measurement_type=mtype, value=value, unit=unit,
                               recorded_at=at)


class RecentRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()
        visit, earlier = dt.date(2026, 10, 6), dt.date(2026, 9, 15)

        def at(day, hour, minute=0):
            return dt.datetime.combine(day, dt.time(hour, minute))

        db.session.add_all([
            # The latest visit: the sites were sampled one after another, so each has its own time
            sample("1", "E. coli", 10.0, at(visit, 9, 40)),
            sample("2", "E. coli", 20.0, at(visit, 10, 15)),
            sample("9", "E. coli", 90.0, at(visit, 12, 5)),
            # A site sampled twice that day: the later sample is its latest
            sample("3", "E. coli", 30.0, at(visit, 9, 0)),
            sample("3", "E. coli", 33.0, at(visit, 15, 30)),
            # The visit before: site 4 wasn't sampled on the latest visit, so it has no latest E. coli result
            sample("1", "E. coli", 5.0, at(earlier, 9, 40)),
            sample("4", "E. coli", 40.0, at(earlier, 11, 0)),
            # Another parameter whose latest day is the earlier visit, also at different times, and date-only rows
            sample("1", "pH", 7.9, at(earlier, 9, 40), "pH units"),
            sample("2", "pH", 8.1, at(earlier, 10, 15), "pH units"),
            sample("1", "Conductivity", 833.0, at(earlier, 0), "µS/cm"),
            sample("2", "Conductivity", 790.0, at(earlier, 0), "µS/cm"),
        ])
        db.session.commit()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        db.drop_all()
        cls.ctx.pop()

    def test_every_site_of_the_latest_visit_is_returned_with_its_own_time(self):
        response = self.client.get("/api/recent")
        self.assertEqual(response.status_code, 200)
        got = [(r["measurement_type"], r["site_id"], r["value"], r["recorded_at"]) for r in response.get_json()]
        self.assertEqual(got, [
            ("Conductivity", "1", 833.0, "2026-09-15T00:00:00"),
            ("Conductivity", "2", 790.0, "2026-09-15T00:00:00"),
            ("E. coli", "1", 10.0, "2026-10-06T09:40:00"),
            ("E. coli", "2", 20.0, "2026-10-06T10:15:00"),
            ("E. coli", "3", 33.0, "2026-10-06T15:30:00"),
            ("E. coli", "9", 90.0, "2026-10-06T12:05:00"),
            ("pH", "1", 7.9, "2026-09-15T09:40:00"),
            ("pH", "2", 8.1, "2026-09-15T10:15:00"),
        ])

    def test_the_response_keeps_its_fields(self):
        first = self.client.get("/api/recent").get_json()[0]
        self.assertEqual(set(first), {"site_id", "creek_id", "measurement_type", "value", "unit", "recorded_at"})
        self.assertEqual((first["creek_id"], first["unit"]), ("20962187", "µS/cm"))


if __name__ == "__main__":
    unittest.main()
