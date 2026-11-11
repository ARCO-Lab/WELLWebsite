"""Tests for /api/windrose (api/routes/windrose.py). Run from dashboard/backend: python -m unittest discover -s tests -t .

The SQL tests need PostgreSQL: set TEST_POSTGRES_URL to an empty, throwaway database (its tables are created and
dropped), e.g. a `docker run postgres:13` container. Without it they're skipped.
"""
import datetime as dt
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from api.routes.windrose import SECTORS, SPEED_EDGES, speed_classes, tabulate  # noqa: E402


class SpeedClassTests(unittest.TestCase):
    def test_classes_cover_every_speed_once(self):
        classes = speed_classes()
        self.assertEqual(len(classes), len(SPEED_EDGES) + 1)
        self.assertEqual([c["name"] for c in classes],
                         ["<0.5 m/s", "0.5-2 m/s", "2-4 m/s", "4-6 m/s", "6-8 m/s", "8-10 m/s", ">10 m/s"])
        self.assertEqual((classes[0]["from"], classes[-1]["to"]), (0, None))
        for a, b in zip(classes, classes[1:]):
            self.assertEqual(a["to"], b["from"])


class TabulateTests(unittest.TestCase):
    def test_zero_filled_counts_and_percentages(self):
        rows = [("Wind Speed", 0, 1, 3), ("Wind Speed", 4, 6, 1), ("Gust Speed", 15, 0, 2)]
        roses = tabulate(rows, ["Wind Speed", "Gust Speed"])
        wind = roses["Wind Speed"]
        self.assertEqual(wind["total"], 4)
        self.assertEqual(len(wind["counts"]), 7)
        self.assertTrue(all(len(row) == len(SECTORS) for row in wind["counts"]))
        self.assertEqual((wind["counts"][1][0], wind["counts"][6][4]), (3, 1))
        self.assertEqual((wind["percent"][1][0], wind["percent"][6][4]), (75.0, 25.0))
        self.assertEqual(roses["Gust Speed"]["percent"][0][15], 100.0)

    def test_no_readings_and_speed_types_not_asked_for(self):
        roses = tabulate([("Gust Speed", 0, 0, 5)], ["Wind Speed"])
        self.assertEqual(list(roses), ["Wind Speed"])
        self.assertEqual(roses["Wind Speed"]["total"], 0)
        self.assertEqual(sum(map(sum, roses["Wind Speed"]["percent"])), 0)


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run the SQL against PostgreSQL")
class WindroseSqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from config import Config

        saved_uri = Config.SQLALCHEMY_DATABASE_URI
        Config.SQLALCHEMY_DATABASE_URI = os.environ["TEST_POSTGRES_URL"]
        try:
            from server import create_app
            cls.app = create_app()
        finally:
            Config.SQLALCHEMY_DATABASE_URI = saved_uri
        from db.database import db
        from db.models import SensorMeasurement
        cls.db = db
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()

        def add(measurement, when, value, station="22051538", group="Weather"):
            db.session.add(SensorMeasurement(station_id=station, group_type=group, measurement_type=measurement,
                                             unit="m/s" if "Speed" in measurement else "°", value=value,
                                             recorded_at=when))

        t0 = dt.datetime(2026, 11, 1, 0, 0)  # naive Toronto wall-clock time, as ingestion stores it
        # (direction, wind speed, gust speed) every 10 minutes
        readings = [
            (0.0, 0.2, 1.0),      # N, <0.5 / 0.5-2
            (359.0, 0.5, 2.0),    # N (wraps), 0.5-2 (an edge belongs to the class above) / 2-4
            (11.25, 3.0, 12.0),   # NNE (11.25 is the edge), 2-4 / >10
            (90.0, 10.0, 15.0),   # E, >10 / >10
            (360.0, 5.0, None),   # N, 4-6 / no gust reading
            (-20.0, 7.0, 9.0),    # NNW (340), 6-8 / 8-10
        ]
        for i, (deg, speed, gust) in enumerate(readings):
            when = t0 + dt.timedelta(minutes=10 * i)
            add("Wind Direction", when, deg)
            add("Wind Speed", when, speed)
            if gust is not None:
                add("Gust Speed", when, gust)
        # Not counted: a speed with no direction at that time, a negative speed, another day, another group
        add("Wind Speed", t0 + dt.timedelta(minutes=5), 3.0)
        add("Wind Direction", t0 + dt.timedelta(hours=2), 180.0)
        add("Wind Speed", t0 + dt.timedelta(hours=2), -1.0)
        add("Wind Direction", t0 + dt.timedelta(days=3), 180.0)
        add("Wind Speed", t0 + dt.timedelta(days=3), 3.0)
        add("Wind Speed", t0, 3.0, station="2577531", group="Logger")
        db.session.commit()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.drop_all()
        cls.db.engine.dispose()
        cls.ctx.pop()

    def rose(self, query):
        r = self.client.get(f"/api/windrose?{query}")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    @staticmethod
    def cells(rose):
        """{(class, sector): count} for the non-zero cells, with names for readability."""
        out = {}
        for c, row in enumerate(rose["counts"]):
            for s, n in enumerate(row):
                if n:
                    out[(speed_classes()[c]["name"], SECTORS[s])] = n
        return out

    def test_bins_direction_and_speed(self):
        body = self.rose("start=2026-11-01T00:00:00&end=2026-11-02T00:00:00")
        self.assertEqual(body["sectors"], SECTORS)
        self.assertEqual(len(body["speed_classes"]), 7)
        wind, gust = body["roses"]["Wind Speed"], body["roses"]["Gust Speed"]
        self.assertEqual(wind["total"], 6)
        self.assertEqual(self.cells(wind), {
            ("<0.5 m/s", "N"): 1, ("0.5-2 m/s", "N"): 1, ("2-4 m/s", "NNE"): 1,
            (">10 m/s", "E"): 1, ("4-6 m/s", "N"): 1, ("6-8 m/s", "NNW"): 1,
        })
        self.assertEqual(gust["total"], 5)
        self.assertEqual(self.cells(gust), {
            ("0.5-2 m/s", "N"): 1, ("2-4 m/s", "N"): 1, (">10 m/s", "NNE"): 1, (">10 m/s", "E"): 1,
            ("8-10 m/s", "NNW"): 1,
        })
        self.assertEqual(gust["percent"][6][4], 20.0)
        self.assertAlmostEqual(sum(map(sum, wind["percent"])), 100.0, places=0)

    def test_one_speed_type_and_aware_bounds(self):
        # 04:00Z-04:25Z is 00:00-00:25 EDT: the first three readings
        body = self.rose("start=2026-11-01T04:00:00Z&end=2026-11-01T04:25:00Z&speed=Gust%20Speed")
        self.assertEqual(list(body["roses"]), ["Gust Speed"])
        self.assertEqual(body["roses"]["Gust Speed"]["total"], 3)

    def test_empty_range(self):
        body = self.rose("start=2026-12-01T00:00:00&end=2026-12-02T00:00:00")
        self.assertEqual(body["roses"]["Wind Speed"]["total"], 0)

    def test_bad_requests(self):
        for query in ("start=2026-11-01", "end=2026-11-02", "start=x&end=y",
                      "start=2026-11-02&end=2026-11-01",
                      "start=2026-11-01T06:10:00Z&end=2026-11-01T05:30:00Z",
                      "start=2026-11-01&end=2026-11-02&speed=Rain",
                      "start=2026-11-01&end=2026-11-02&speed=x';DROP TABLE sensor_measurements;--"):
            self.assertEqual(self.client.get(f"/api/windrose?{query}").status_code, 400, query)


if __name__ == "__main__":
    unittest.main()
