"""Tests for utils/sampling_csv.py (the standard sampling file format), scripts/check_sampling_csv.py, the template
download, and the import's idempotence on PostgreSQL. Run from dashboard/backend:
python -m unittest discover -s tests -t .  (the import and --full-reload tests need TEST_POSTGRES_URL, as in CI)"""
import contextlib
import datetime as dt
import io
import os
import pathlib
import sys
import tempfile
from unittest import TestCase, main, mock, skipUnless

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


class ValidFileTests(TestCase):
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


class InvalidFileTests(TestCase):
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


class SiteListTests(TestCase):
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


class WideExcelTests(TestCase):
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

    def write_workbook(self, sheets):
        import pandas as pd
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = pathlib.Path(folder.name) / "sheet.xlsx"
        with pd.ExcelWriter(path) as writer:
            for name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=name, index=False)
        return path

    def test_two_headers_for_one_column_are_an_error(self):
        import pandas as pd
        path = self.write_workbook({"Data": pd.DataFrame({
            "Date": [dt.datetime(2025, 5, 7)], "Site": ["Falkirk Forest"],
            "E. coli (CFU/100 mL)": [2], "E.coli  (CFU/100 mL)": [3], "Stream": ["Tiffany Creek"],
            "Creek": ["Tiffany Creek"]})})
        where, text = errors(validate_wide_excel(path))
        self.assertEqual(where, [(1, "E.coli  (CFU/100 mL)"), (1, "Creek")], text)
        self.assertIn("means the same as column 'E. coli (CFU/100 mL)'", text)

    def test_one_sheet_with_data(self):
        import pandas as pd
        frame = pd.DataFrame({"Date": [dt.datetime(2025, 5, 7)], "Site": ["Falkirk Forest"], "pH": [7.9]})
        two = self.write_workbook({"Trip 1": frame, "Trip 2": frame})
        self.assertIn("data on 2 sheets (Trip 1, Trip 2)", errors(validate_wide_excel(two))[1])
        with_empty_sheet = self.write_workbook({"Data": frame, "Sheet2": pd.DataFrame()})
        result = validate_wide_excel(with_empty_sheet)
        self.assertTrue(result.ok, errors(result)[1])
        self.assertEqual(len(result.records), 1)

    def test_a_column_without_header_must_be_empty(self):
        import pandas as pd
        frame = pd.DataFrame([[dt.datetime(2025, 5, 7), "Falkirk Forest", 7.9, None]], columns=["Date", "Site", "pH", ""])
        self.assertTrue(validate_wide_excel(self.write_workbook({"Data": frame})).ok)
        frame.iloc[0, 3] = "oops"
        self.assertEqual(errors(validate_wide_excel(self.write_workbook({"Data": frame})))[0], [(1, "column D")])


class EdgeCaseTests(TestCase):
    HEADER = b"date,site,parameter,value,unit\n"

    def test_no_readings_is_an_error(self):
        result = validate_csv(self.HEADER + b"2026-05-06,Falkirk Forest,pH,NA,pH\n")
        self.assertEqual(errors(result)[0], [(0, "")])
        self.assertIn("no readings to import (1 blank values, 0 rows flagged rejected)", errors(result)[1])
        self.assertIn("no readings", errors(validate_csv(self.HEADER))[1])

    def test_a_blank_value_needs_no_unit(self):
        result = validate_csv(self.HEADER + b"2026-05-06,Falkirk Forest,Turbidity,,\n"
                                            b"2026-05-06,Falkirk Forest,pH,7.9,pH\n")
        self.assertTrue(result.ok, errors(result)[1])
        self.assertEqual((len(result.records), result.blank), (1, 1))

    def test_numbers_are_plain_ascii(self):
        rows = ["1_000", "٧", "７", "0x10", "1.5e-3", "+8.1", ".5", "7."]
        data = self.HEADER + "".join(f"2026-05-0{i + 1},Falkirk Forest,Chloride,{v},mg/L\n"
                                     for i, v in enumerate(rows)).encode("utf-8")
        result = validate_csv(data)
        self.assertEqual(errors(result)[0], [(2, "value"), (3, "value"), (4, "value"), (5, "value")])
        self.assertEqual([r["value"] for r in result.records], [0.0015, 8.1, 0.5, 7.0])

    def test_malformed_quotes_are_a_file_problem(self):
        for body in (b'2026-05-06,"Falkirk Forest,pH,7.9,pH\n2026-05-07,Falkirk Forest,pH,7.9,pH\n',
                     b'2026-05-06,"Falkirk" Forest,pH,7.9,pH\n'):
            where, text = errors(validate_csv(self.HEADER + body))
            self.assertEqual(where, [(0, "")])
            self.assertIn("can't be read as CSV near line", text)

    def test_empty_trailing_columns_and_cells_are_ignored(self):
        result = validate_csv(b"date,site,parameter,value,unit,,\n2026-05-06,Falkirk Forest,pH,7.9,pH,,\n"
                              b"2026-05-07,Falkirk Forest,pH,8.0,pH\n2026-05-08,Falkirk Forest,pH,8.1,pH,,,,\n")
        self.assertTrue(result.ok, errors(result)[1])
        self.assertEqual(len(result.records), 3)

    def test_values_without_header_or_beyond_it_are_errors(self):
        where, _ = errors(validate_csv(b"date,site,parameter,value,unit,\n2026-05-06,Falkirk Forest,pH,7.9,pH,x\n"))
        self.assertEqual(where, [(1, "column F")])
        where, text = errors(validate_csv(self.HEADER + b"2026-05-06,Falkirk Forest,pH,7,9,pH\n"))
        self.assertEqual(where, [(2, "")])
        self.assertIn("beyond the header's 5 columns", text)


class CheckScriptTests(TestCase):
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

    def test_malformed_file_is_reported_not_a_crash(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = pathlib.Path(folder.name) / "quote.csv"
        path.write_bytes(b'date,site,parameter,value,unit\n2026-05-06,"Falkirk Forest,pH,7.9,pH\n')
        code, out = self.run_check(path)
        self.assertEqual(code, 1)
        self.assertIn("can't be read as CSV", out)


class ImportLogTests(TestCase):
    def test_only_the_first_problems_are_printed(self):
        sys.path.insert(0, str(APP / "scripts"))
        import inject_sampling
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = pathlib.Path(folder.name) / "many.csv"
        path.write_text("date,site,parameter,value,unit\n" + "2026-05-06,Nowhere,pH,7.9,pH\n" * 60, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(inject_sampling.InvalidFile) as raised:
            inject_sampling.load_valid_rows(path)
        lines = out.getvalue().splitlines()
        self.assertEqual(sum("unknown site 'Nowhere'" in line for line in lines), inject_sampling.MAX_LISTED)
        self.assertIn("[ERROR] ... and 10 more problems not listed", out.getvalue())
        self.assertTrue(str(raised.exception).startswith("60 problems in "))   # download_data.py reads this count


class TemplateRouteTests(TestCase):
    def test_template_download(self):
        from server import create_app
        response = create_app().test_client().get("/api/samples/template.csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(response.data, TEMPLATE.read_bytes())
        response.close()


@skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to a disposable PostgreSQL")
class ImportIdempotenceTests(TestCase):
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

    # --full-reload (replace_all): it replaces the table in one transaction, or refuses and deletes nothing.

    def reload(self, path, allow_shrink=False):
        with mock.patch.dict(os.environ, {"ALLOW_WIPE": "1"}), contextlib.redirect_stdout(io.StringIO()), \
                self.Session(self.engine) as session:
            return self.inject.replace_all(session, path, allow_shrink=allow_shrink)

    def test_full_reload_replaces_the_data(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.store(FIXTURES / "valid.csv")
        lab_rows = len(validate_wide_excel(LAB_SHEET).records)
        self.assertEqual(self.reload(LAB_SHEET), lab_rows)
        self.assertEqual(self.count(), lab_rows)
        with self.Session(self.engine) as session:   # the 2026 fixture rows are gone
            self.assertEqual(session.query(self.model).filter(self.model.recorded_at >= dt.datetime(2026, 1, 1)).count(), 0)

    def test_full_reload_of_an_invalid_file_deletes_nothing(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.store(FIXTURES / "valid.csv")
        with self.assertRaises(self.inject.InvalidFile):
            self.reload(FIXTURES / "unknown_site.csv")
        self.assertEqual(self.count(), 6)

    def test_full_reload_needs_allow_wipe(self):
        with mock.patch.dict(os.environ, {"ALLOW_WIPE": ""}), self.Session(self.engine) as session, \
                self.assertRaises(SystemExit):
            self.inject.replace_all(session, TEMPLATE)

    def test_full_reload_refuses_to_shrink_the_table_unless_allowed(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.store(LAB_SHEET)
        stored = self.count()
        with self.assertRaises(self.inject.RefusedReload) as refused:
            self.reload(TEMPLATE)   # 3 readings instead of 294
        self.assertIn(f"the file has 3 readings but {stored} are stored", str(refused.exception))
        self.assertEqual(self.count(), stored)
        self.assertEqual(self.reload(TEMPLATE, allow_shrink=True), 3)
        self.assertEqual(self.count(), 3)

    def test_a_failed_insert_rolls_back_the_delete(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.store(FIXTURES / "valid.csv")

        def broken_insert(session, rows):
            raise RuntimeError("connection lost mid-insert")

        with mock.patch.object(self.inject, "store_rows", side_effect=broken_insert), \
                self.assertRaises(RuntimeError):
            self.reload(TEMPLATE, allow_shrink=True)
        self.assertEqual(self.count(), 6)


if __name__ == "__main__":
    main()
