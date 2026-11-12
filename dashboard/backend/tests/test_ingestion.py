"""The 10-minute ingestion (scripts/inject_from_api.py): where a LI-COR run starts (the fetch mark and silent groups),
and how a vendor answer's outcome is recorded once it is parsed. On SQLite, with the vendor calls and the
PostgreSQL-only insert replaced; tests/test_alerts.py runs the real thing against PostgreSQL in CI.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import contextlib
import datetime as dt
import importlib
import io
import os
import pathlib
import sys
import unittest
from unittest import mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from config import Config  # noqa: E402

Config.SQLALCHEMY_DATABASE_URI = "sqlite://"   # another test module may have imported Config first

from utils.fetching import BadVendorResponse, to_local  # noqa: E402
from utils.timezone import EST_TZ  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 11, 19, 0, tzinfo=UTC)
H, D = dt.timedelta(hours=1), dt.timedelta(days=1)
WEATHER, WQ = "22051538", "4501"


def licor(sn, value, ts):
    return {"logger_sn": WEATHER, "sensor_sn": sn, "sensor_measurement_type": "Temperature", "unit": "°C",
            "value": value, "timestamp": ts}


class IngestionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from server import create_app
        from db.database import db
        cls.app, cls.db = create_app(), db
        with mock.patch.object(Config, "HOBO_LOGGERS", WEATHER):   # unset in tests; the module builds its services
            cls.ingest = importlib.import_module("scripts.inject_from_api")

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db.create_all()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def add(self, group, newest):
        """One stored reading of the group at `newest` (aware), stored as site wall-clock time like ingestion does."""
        from db.models import SensorMeasurement
        self.db.session.add(SensorMeasurement(station_id=group, group_type=group, measurement_type="m", value=1.0,
                                              unit="u", recorded_at=to_local(newest, EST_TZ)))
        self.db.session.commit()

    def mark(self, until):
        """A LI-COR fetch up to `until` whose readings were all stored."""
        from utils.alert_state import record_fetched_until, record_vendor_result
        self.assertTrue(record_vendor_result("LI-COR", now=until))
        self.assertTrue(record_fetched_until("LI-COR", until))

    def status(self, source):
        from utils.alert_state import vendor_statuses
        self.db.session.remove()
        return vendor_statuses()[source]


class LicorStartTests(IngestionTestCase):
    def start(self):
        return self.ingest.licor_start(EST_TZ, NOW)

    def test_without_a_mark_the_older_group_sets_the_start_as_before(self):
        self.add("Weather", NOW - 10 * dt.timedelta(minutes=1))
        self.add("Logger", NOW - 3 * D)
        self.assertEqual(self.start(), NOW - 3 * D - H)

    def test_a_silent_group_no_longer_widens_every_run(self):
        # The loggers stopped three days ago; the weather station reports. Before, every run fetched 3 days, then
        # (once the gap passed two weeks) 14; now a few hours before the last fetch.
        self.add("Weather", NOW - 20 * dt.timedelta(minutes=1))
        self.add("Logger", NOW - 3 * D)
        self.mark(NOW - 10 * dt.timedelta(minutes=1))
        self.assertEqual(self.start(), NOW - 10 * dt.timedelta(minutes=1) - self.ingest.LICOR_LATE)
        self.assertEqual(self.ingest.LICOR_LATE, 3 * H)

    def test_a_group_that_has_never_reported_doesnt_count(self):
        self.add("Weather", NOW - 20 * dt.timedelta(minutes=1))
        self.mark(NOW - 10 * dt.timedelta(minutes=1))
        self.assertEqual(self.start(), NOW - 10 * dt.timedelta(minutes=1) - 3 * H)

    def test_a_short_gap_is_still_caught_up(self):
        # A logger out of contact for 6 hours resends what it missed: its newest reading still sets the start.
        self.add("Weather", NOW - 20 * dt.timedelta(minutes=1))
        self.add("Logger", NOW - 6 * H)
        self.mark(NOW - 10 * dt.timedelta(minutes=1))
        self.assertEqual(self.start(), NOW - 7 * H)

    def test_a_whole_station_outage_is_caught_up_from_the_fresher_group(self):
        # Nothing from the station for 3 days (the loggers report through it): what it uploads once it is back must
        # still be fetched, so the fresher group's newest reading sets the start, not the mark.
        self.add("Weather", NOW - 3 * D)
        self.add("Logger", NOW - 4 * D)
        self.mark(NOW - 10 * dt.timedelta(minutes=1))
        self.assertEqual(self.start(), NOW - 3 * D - H)

    def test_ingestion_down_for_days_starts_from_the_mark(self):
        self.add("Weather", NOW - 2 * D)
        self.add("Logger", NOW - 2 * D)
        self.mark(NOW - 2 * D)
        self.assertEqual(self.start(), NOW - 2 * D - 3 * H)

    def test_never_more_than_14_days_back(self):
        self.add("Weather", NOW - 30 * D)
        self.add("Logger", NOW - 30 * D)
        self.mark(NOW - 30 * D)
        self.assertEqual(self.start(), NOW - 14 * D)

    def test_an_unreadable_mark_falls_back_to_the_stored_readings(self):
        self.add("Weather", NOW - 20 * dt.timedelta(minutes=1))
        self.add("Logger", NOW - 3 * D)
        self.mark(NOW - 10 * dt.timedelta(minutes=1))
        with self.db.engine.begin() as conn:   # as if migration 0006 hadn't been applied
            conn.exec_driver_sql("ALTER TABLE vendor_status DROP COLUMN fetched_until")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.start(), NOW - 3 * D - H)
        self.assertEqual(out.getvalue().splitlines(),
                         ["[WARN] Couldn't read where the last LI-COR fetch ended: OperationalError"])


class LicorRunTests(IngestionTestCase):
    """inject_licor with the fetch and the insert replaced."""

    def run_with(self, records, store=None):
        out = io.StringIO()
        stored = []

        def fake_store(rows):
            stored.extend(rows)
            return len(rows)
        with mock.patch.object(self.ingest, "fetch_range", return_value=records), \
                mock.patch.object(self.ingest, "store", side_effect=store or fake_store), \
                mock.patch.object(self.ingest.weather_service, "get_logger_id", return_value=WEATHER), \
                contextlib.redirect_stdout(out):
            try:
                self.ingest.inject_licor(EST_TZ, NOW)
            finally:
                self.output = out.getvalue()
        return stored

    def test_bad_records_are_skipped_counted_and_noted(self):
        from utils.alert_state import fetched_until
        stored = self.run_with([licor("21948438-1", 5.0, "2026-11-11 18:40:00Z"),
                                licor("22154270-1", 9.0, None),
                                licor("22154270-1", 9.0, "2026-11-11 18:40:00"),     # no UTC offset
                                licor("22154270-1", 9.0, "not a time")])
        self.assertEqual([(r["measurement_type"], r["value"]) for r in stored], [("Air Temperature", 5.0)])
        warnings = [line for line in self.output.splitlines() if line.startswith("[WARN]")]
        self.assertEqual(warnings, ["[WARN] LI-COR: skipped 3 unreadable record(s), e.g. unreadable timestamp None "
                                    "from sensor '22154270-1'. If the vendor changed its format, fix utils/parsers.py "
                                    "and refill the period with the vendor's backfill script."])
        row = self.status("LI-COR")
        self.assertEqual((row["consecutive_failures"], row["last_skipped"]),
                         (0, "3 unreadable record(s), e.g. unreadable timestamp None from sensor '22154270-1'"))
        self.assertEqual(fetched_until("LI-COR"), NOW)

    def test_a_clean_answer_clears_the_note(self):
        self.run_with([licor("21948438-1", 5.0, None), licor("21948438-1", 5.0, "2026-11-11 18:40:00Z")])
        self.assertIsNotNone(self.status("LI-COR")["last_skipped"])
        self.run_with([licor("21948438-1", 5.0, "2026-11-11 18:40:00Z")])
        self.assertIsNone(self.status("LI-COR")["last_skipped"])

    def test_nothing_readable_is_a_failed_call_and_keeps_the_mark(self):
        from utils.alert_state import fetched_until
        from utils.fetching import UnreadableRecords
        self.mark(NOW - H)
        with self.assertRaises(UnreadableRecords) as caught:
            self.run_with([licor("21948438-1", 5.0, "2026-11-11 18:40:00"),
                           licor("21948438-1", 5.0, "2026-11-11 18:50:00")])
        self.assertIn("none of LI-COR's records could be read: 2 unreadable record(s)", str(caught.exception))
        row = self.status("LI-COR")
        self.assertEqual((row["consecutive_failures"], row["last_error_kind"]), (1, "unreadable"))
        self.assertEqual(fetched_until("LI-COR"), NOW - H)

    def test_an_empty_answer_is_a_success(self):
        self.assertEqual(self.run_with([]), [])
        self.assertEqual(self.status("LI-COR")["consecutive_failures"], 0)

    def test_success_is_recorded_only_once_the_answer_is_parsed(self):
        # Recorded before parsing, a parser crash left "LI-COR OK" behind, and the alerts sent people to the field.
        with mock.patch.object(self.ingest, "licor_rows", side_effect=RecursionError("parser bug")), \
                self.assertRaises(RecursionError):
            self.run_with([licor("21948438-1", 5.0, "2026-11-11 18:40:00Z")])
        row = self.status("LI-COR")
        self.assertEqual((row["consecutive_failures"], row["last_error_kind"], row["last_error"]),
                         (1, "unreadable", "LI-COR's answer couldn't be read (RecursionError)"))

    def test_a_failed_store_doesnt_move_the_mark(self):
        from utils.alert_state import fetched_until
        self.mark(NOW - H)

        def broken(rows):
            raise RuntimeError("database gone")
        with self.assertRaises(RuntimeError):
            self.run_with([licor("21948438-1", 5.0, "2026-11-11 18:40:00Z")], store=broken)
        self.assertEqual(fetched_until("LI-COR"), NOW - H)

    def test_a_failed_fetch_is_recorded_and_keeps_the_mark(self):
        from utils.alert_state import fetched_until
        self.mark(NOW - H)
        with mock.patch.object(self.ingest, "fetch_range", side_effect=BadVendorResponse("LI-COR reply has no data")), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(BadVendorResponse):
            self.ingest.inject_licor(EST_TZ, NOW)
        self.assertEqual(self.status("LI-COR")["last_error_kind"], "bad_response")
        self.assertEqual(fetched_until("LI-COR"), NOW - H)


class QualityRunTests(IngestionTestCase):
    """inject_quality with WQData and the insert replaced."""

    def run_with(self, entries, error=None):
        stored = []

        def get_quality_data(start, end):
            self.ingest.quality_service.last_error = error
            return entries
        with mock.patch.object(self.ingest.quality_service, "get_quality_data", side_effect=get_quality_data), \
                mock.patch.object(self.ingest, "store", side_effect=lambda rows: stored.extend(rows) or len(rows)), \
                mock.patch.object(self.ingest.Config, "WQ_DEVICE_ID", WQ), \
                contextlib.redirect_stdout(io.StringIO()):
            self.ingest.inject_quality(EST_TZ, NOW)
        return stored

    def test_a_paging_stall_is_a_failed_call(self):
        point = {"timestamp": "2026-11-11 18:00:00", "values": [{"parameterId": 125001, "value": "8.5"}]}
        stall = BadVendorResponse("WQData paging didn't advance past 2026-11-11 18:00:00 UTC (count 1, total 9)")
        with self.assertRaisesRegex(RuntimeError, "WQData request failed: WQData paging didn't advance"):
            self.run_with([point], error=stall)
        row = self.status("WQData")
        self.assertEqual((row["consecutive_failures"], row["last_error_kind"]), (1, "bad_response"))
        self.assertIn("paging didn't advance", row["last_error"])

    def test_the_stalled_points_are_still_stored(self):
        point = {"timestamp": "2026-11-11 18:00:00", "values": [{"parameterId": 125001, "value": "8.5"}]}
        stored = []
        stall = BadVendorResponse("WQData paging didn't advance")
        with mock.patch.object(self.ingest.quality_service, "get_quality_data", return_value=[point]), \
                mock.patch.object(self.ingest.quality_service, "last_error", stall), \
                mock.patch.object(self.ingest, "store", side_effect=lambda rows: stored.extend(rows) or len(rows)), \
                mock.patch.object(self.ingest.Config, "WQ_DEVICE_ID", WQ), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            self.ingest.inject_quality(EST_TZ, NOW)
        self.assertEqual([(r["measurement_type"], r["value"]) for r in stored], [("Water Temperature", 8.5)])

    def test_a_bad_point_is_skipped_and_the_rest_stored(self):
        good = {"timestamp": "2026-11-11 18:00:00", "values": [{"parameterId": 125001, "value": "8.5"}]}
        stored = self.run_with([{"timestamp": None, "values": []}, good])
        self.assertEqual(len(stored), 1)
        row = self.status("WQData")
        self.assertEqual(row["consecutive_failures"], 0)
        self.assertEqual(row["last_skipped"], "1 unreadable record(s), e.g. malformed record (TypeError) at None")


if __name__ == "__main__":
    unittest.main()
