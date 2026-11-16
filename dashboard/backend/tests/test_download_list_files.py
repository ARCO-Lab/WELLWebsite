"""`download_data.py --list-files` must only list. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import contextlib
import datetime as dt
import io
import pathlib
import sys
from unittest import TestCase, main, mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from scripts import download_data  # noqa: E402

FILES = [{"filename": "WELLAncasterWatershed_2026-11-01.xlsx", "id": 7, "create_date": dt.datetime(2026, 11, 1)}]


def run_main(*argv):
    with mock.patch.object(sys, "argv", ["download_data.py", *argv]), \
            mock.patch.object(download_data, "load_state", return_value={"processed_files": [], "refused_files": []}), \
            mock.patch.object(download_data, "save_state"), \
            mock.patch.object(download_data, "get_files_from_dataset", return_value=FILES), \
            mock.patch.object(download_data, "process_single_file", side_effect=AssertionError("downloaded a file")) as download, \
            mock.patch.object(download_data.subprocess, "run", side_effect=AssertionError("ran an import")) as importer, \
            contextlib.redirect_stdout(io.StringIO()) as out:
        try:
            download_data.main()
            code = 0
        except SystemExit as e:
            code = e.code
    return code, download, importer, out.getvalue()


class ListFilesTests(TestCase):
    def test_list_files_lists_the_new_files_and_exits_without_downloading(self):
        code, download, importer, out = run_main("--list-files")
        self.assertEqual(code, 0)
        self.assertIn("WELLAncasterWatershed_2026-11-01.xlsx", out)
        download.assert_not_called()
        importer.assert_not_called()

    def test_a_normal_run_still_downloads_new_files(self):
        _, download, _, _ = run_main()
        download.assert_called_once()


if __name__ == "__main__":
    main()
