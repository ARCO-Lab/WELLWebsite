"""Tests for utils/sampling_csv.py (the standard sampling file format), scripts/check_sampling_csv.py, the template
download, and the import's idempotence on PostgreSQL. Run from dashboard/backend:
python -m unittest discover -s tests -t .  (the import tests need TEST_POSTGRES_URL, as in CI)"""
import contextlib
import datetime as dt
import io
import os
import pathlib
import sys
import tempfile
import unittest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
from utils import sampling_csv  # noqa: E402
from utils.sampling_csv import validate_csv, validate_file, validate_wide_excel  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "sampling"
TEMPLATE = APP / "sampling_template.csv"
LAB_SHEET = APP / "samplingExcel" / "WELL Creek Data 2025 (1).xlsx"   # the lab's 2025 field sheet (older layout)


def errors(result):
    """(row, column) of each problem, and the messages, for compact assertions."""
    return [(e.row, e.column) for e in result.errors], " | ".join(str(e) for e in result.errors)


class ValidFileTests(unittest.TestCase):
    def test_valid_fixture(self):
        result = validate_file(FIXTURES / "valid.csv")
        self.assertTrue(result.ok, errors(result)[1])
        self.assertEqual(len(result.records), 6)
        self.assertEqual((result.blank, result.rejected, result.below_detection), (2, 1, 1))
        first = result.records[0]
        self.assertEqual(first, {"site_id": "1", "creek_id": "20962187", "measurement_type": "E. coli", "value": 48.0,
                                 "unit": "CFU/100 mL", "recorded_at": dt.datetime(2026, 5, 6, 9, 40)})
        by_type = {r["measurement_type"]: r for r in result.records}
        self.assertEqual(by_type["Ammonia nitrogen"]["value"], 0.01)          # '<0.01' stores the limit
        self.assertEqual(by_type["Conductivity"]["unit"], "µS/cm")            # 'uS/cm' stored as the canonical unit
        self.assertEqual(by_type["Conductivity"]["recorded_at"], dt.datetime(2026, 5, 6))   # no time: midnight
        self.assertEqual(by_type["pH"]["site_id"], "2")                       # 'maple lane pk': case doesn't matter
        self.assertEqual(by_type["Total phosphorus"]["recorded_at"], dt.datetime(2026, 4, 2, 11))  # not the rejected row

    def test_template_round_trip(self):
        """The template people download is itself a valid file, with every column of the format."""
        result = validate_file(TEMPLATE)
        self.assertTrue(result.ok, errors(result)[1])
        self.assertEqual(len(result.records), 3)
        header = TEMPLATE.read_text(encoding="utf-8").splitlines()[0].split(",")
        self.assertEqual(set(header), set(sampling_csv.REQUIRED_COLUMNS) | set(sampling_csv.OPTIONAL_COLUMNS) - {"creek"})

    def test_excel_bom_and_crlf_are_fine(self):
        data = "﻿Date,Site,Parameter,Value,Unit\r\n2026-05-06,Tiffany Falls,Turbidity,2.44,NTU\r\n".encode("utf-8")
        result = validate_csv(data)
        self.assertTrue(result.ok, errors(result)[1])
        self.assertEqual(result.records[0]["creek_id"], "20962187")

    def test_creek_column_is_cross_checked(self):
        ok = validate_csv(b"date,site,creek,parameter,value,unit\n2026-05-06,Cootes Dr,Spencer Creek,pH,8.9,pH\n")
        self.assertTrue(ok.ok, errors(ok)[1])
        bad = validate_csv(b"date,site,creek,parameter,value,unit\n2026-05-06,Cootes Dr,Ancaster Creek,pH,8.9,pH\n")
        self.assertEqual(errors(bad)[0], [(2, "creek")])


class InvalidFileTests(unittest.TestCase):
    """One fixture per kind of problem. Every problem of a file is reported, and an invalid file yields no rows."""

    def check(self, name, expected, *phrases):
        result = validate_file(FIXTURES / name)
        where, text = errors(result)
        self.assertFalse(result.ok)
        self.assertEqual(where, expected, text)
        for phrase in phrases:
            self.assertIn(phrase, text)
        return result

    def test_unknown_site(self):
        self.check("unknown_site.csv", [(3, "site"), (4, "site")],
                   "unknown site 'Maple Lane Park'", "Did you mean 'Maple Lane Pk'?", "unknown site 'Unknown'")

    def test_ambiguous_and_invalid_dates(self):
        self.check("bad_dates.csv", [(2, "date"), (3, "date"), (4, "date")],
                   "'01/02/2026' is ambiguous", "'2026-02-30' is not a real date", "not a date in the form YYYY-MM-DD")

    def test_bad_times(self):
        self.check("bad_times.csv", [(2, "time"), (3, "time")],
                   "not a 24-hour time", "doesn't exist on 2026-03-08")

    def test_non_numeric_and_impossible_values(self):
        self.check("non_numeric.csv", [(2, "value"), (3, "value"), (4, "value"), (5, "value")],
                   "'many' is not a number", "no thousands separators", "values above a limit (>)",
                   "15 is impossible for pH")

    def test_unit_mismatch(self):
        self.check("unit_mismatch.csv", [(2, "unit"), (3, "unit")],
                   "'mg/L' doesn't match Total phosphorus, which must be in µg/L", "unit is empty")

    def test_missing_and_unknown_columns(self):
        self.check("missing_column.csv", [(1, "units"), (1, "parameter"), (1, "unit")],
                   "Did you mean 'unit'?", "required column is missing")

    def test_duplicate_rows(self):
        result = self.check("duplicate_rows.csv", [(3, ""), (4, "")], "repeats row 2", "average replicates")
        self.assertEqual(len(result.records), 2)   # internal only: callers check result.ok and store nothing

    def test_not_utf8_and_wrong_separator(self):
        latin1 = "date,site,parameter,value,unit\n2026-05-06,Falkirk Forest,Conductivity,833,µS/cm\n".encode("latin-1")
        self.assertIn("not UTF-8", errors(validate_csv(latin1))[1])
        self.assertIn("separated by commas", errors(validate_csv(b"date;site;parameter;value;unit\n"))[1])
        self.assertIn("file is empty", errors(validate_csv(b""))[1])

    def test_below_detection_contradiction(self):
        result = validate_csv(b"date,site,parameter,value,unit,below_detection\n"
                              b"2026-05-06,Falkirk Forest,Chloride,<0.1,mg/L,false\n"
                              b"2026-05-06,Falkirk Forest,pH,,pH,true\n")
        self.assertEqual(errors(result)[0], [(2, "below_detection"), (3, "value")])


class SiteListTests(unittest.TestCase):
    def test_sites_match_the_dashboard(self):
        """The import's site list is the dashboard's (frontend config/filters.tsx): ids, names and creeks."""
        dashboard = {"2": ("Maple Lane Pk", "ancaster"), "5": ("Sherman Falls", "ancaster"),
                     "1": ("Falkirk Forest", "tiffany"), "6": ("Tiffany Falls", "tiffany"),
                     "3": ("Jerseyville Rd", "sulphur"), "4": ("Sulphur Springs", "sulphur"),
                     "8": ("Osler Dr", "coldwater"), "9": ("McMaster Lot P", "coldwater"),
                     "10": ("Cootes Dr", "spencer")}
        self.assertEqual({s.id: (s.name, s.creek) for s in sampling_csv.SITES}, dashboard)
        self.assertNotIn("7", {s.id for s in sampling_csv.SITES})   # no catch-all "Unknown" site

    def test_site_number_must_match_name(self):
        result = validate_csv(b"date,site,parameter,value,unit\n2026-05-06,#2 Falkirk Forest,pH,7.9,pH\n")
        self.assertEqual(errors(result)[0], [(2, "site")])


class WideExcelTests(unittest.TestCase):
    def test_lab_sheet_imports_through_the_same_checks(self):
        result = validate_wide_excel(LAB_SHEET)
        self.assertTrue(result.ok, errors(result)[1])
        self.assertTrue(sampling_csv.is_excel(LAB_SHEET))
        self.assertIn("TSS (mg/L)", result.notes[0])
        self.assertEqual({r["site_id"] for r in result.records}, {s.id for s in sampling_csv.SITES})
        trip_1 = min(r["recorded_at"] for r in result.records)
        self.assertEqual(trip_1.year, 2025)
        first = [r for r in result.records if r["site_id"] == "1" and r["recorded_at"] == trip_1]
        self.assertEqual({r["measurement_type"]: r["value"] for r in first}["Conductivity"], 1295.0)
        self.assertEqual(len({r["recorded_at"] for r in result.records}), 4)   # four trips

    def test_unknown_column_and_site_are_errors(self):
        import pandas as pd
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = pathlib.Path(folder.name) / "sheet.xlsx"
        pd.DataFrame({"Date": [dt.datetime(2025, 5, 7)], "Site": ["#7 Somewhere"], "pH": [7.9],
                      "Dissolved oxygen (mg/L)": [9.1]}).to_excel(path, index=False)
        where, text = errors(validate_wide_excel(path))
        self.assertEqual(where, [(1, "Dissolved oxygen (mg/L)")], text)
        path.unlink()
        pd.DataFrame({"Date": ["05/07/2025"], "Site": ["#7 Somewhere"], "pH": [7.9]}).to_excel(path, index=False)
        self.assertEqual(errors(validate_file(path))[0], [(2, "date"), (2, "site")])


class CheckScriptTests(unittest.TestCase):
    def run_check(self, *paths):
        sys.path.insert(0, str(APP / "scripts"))
        import check_sampling_csv
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check_sampling_csv.main([str(p) for p in paths])
        return code, out.getvalue()

    def test_valid_file(self):
        code, out = self.run_check(TEMPLATE)
        self.assertEqual(code, 0)
        self.assertIn("OK, 3 readings", out)

    def test_reports_every_problem_of_every_file(self):
        code, out = self.run_check(FIXTURES / "bad_dates.csv", FIXTURES / "unknown_site.csv", FIXTURES / "nope.csv")
        self.assertEqual(code, 1)
        self.assertIn("row 2, date: '01/02/2026' is ambiguous", out)
        self.assertIn("row 4, site: unknown site 'Unknown'", out)
        self.assertIn("cannot read the file", out)
        self.assertIn("an import would store nothing", out)


class TemplateRouteTests(unittest.TestCase):
    def test_template_download(self):
        from server import create_app
        response = create_app().test_client().get("/api/samples/template.csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(response.data, TEMPLATE.read_bytes())
        response.close()


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to a disposable PostgreSQL")
class ImportIdempotenceTests(unittest.TestCase):
    """The import against PostgreSQL (ON CONFLICT is PostgreSQL's): re-importing adds nothing, a backfill adds
    exactly its missing rows, and an invalid file stores nothing."""

    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from db.models import SamplingMeasurement
        cls.model = SamplingMeasurement
        cls.engine = create_engine(os.environ["TEST_POSTGRES_URL"])
        SamplingMeasurement.__table__.drop(cls.engine, checkfirst=True)
        SamplingMeasurement.__table__.create(cls.engine)
        cls.Session = Session
        sys.path.insert(0, str(APP / "scripts"))
        import inject_sampling
        cls.inject = inject_sampling

    @classmethod
    def tearDownClass(cls):
        cls.model.__table__.drop(cls.engine, checkfirst=True)
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as conn:
            conn.execute(self.model.__table__.delete())

    def store(self, path):
        rows = self.inject.load_valid_rows(path)
        with self.Session(self.engine) as session:
            inserted = self.inject.store_rows(session, rows)
            session.commit()
        return len(inserted)

    def count(self):
        with self.Session(self.engine) as session:
            return session.query(self.model).count()

    def test_reimport_adds_nothing_and_backfill_adds_only_new_rows(self):
        quiet = contextlib.redirect_stdout(io.StringIO())
        with quiet:
            self.assertEqual(self.store(FIXTURES / "valid.csv"), 6)
            self.assertEqual(self.store(FIXTURES / "valid.csv"), 0)
            self.assertEqual(self.count(), 6)
            # The template's three readings are also in valid.csv, so a file overlapping stored data adds nothing
            self.assertEqual(self.store(TEMPLATE), 0)
            # The lab sheet (2025, older than the rows stored so far) is a backfill: all its rows are added
            self.assertEqual(self.store(LAB_SHEET), len(validate_wide_excel(LAB_SHEET).records))
            total = self.count()
            self.assertEqual(self.store(LAB_SHEET), 0)
        self.assertEqual(self.count(), total)

    def test_invalid_file_stores_nothing(self):
        with contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(self.inject.InvalidFile):
            self.store(FIXTURES / "duplicate_rows.csv")
        self.assertIn("[ERROR] row 3: repeats row 2", out.getvalue())
        self.assertEqual(self.count(), 0)


if __name__ == "__main__":
    unittest.main()
