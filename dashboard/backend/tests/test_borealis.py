"""The Borealis (Dataverse) client, the monthly upload's use of it and the preflight check, against a fake Dataverse
server (no network). Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import contextlib
import hashlib
import io
import json
import os
import pathlib
import sys
from unittest import TestCase, main, mock
from urllib.parse import urlsplit

os.environ["DATABASE_URL"] = "sqlite://"  # config is read once on first import; never a real database
APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
from utils import borealis  # noqa: E402
from scripts import borealis_check, download_data, upload_data  # noqa: E402
from utils.jobs import SETTINGS_ERROR_EXIT  # noqa: E402

TOKEN = "SECRET-TOKEN-123"
PID = "doi:10.5683/SP3/WELLUP"
SERVER = "https://borealis.example"


class Response:
    def __init__(self, status, body=None):
        self.status_code, self.body = status, body
        self.text = json.dumps(body) if body is not None else ""

    def json(self):
        if self.body is None:
            raise ValueError("no JSON")
        return self.body


def file_entry(file_id, name, content, directory=None):
    return {"label": name, "directoryLabel": directory, "restricted": False,
            "dataFile": {"id": file_id, "filename": name, "createDate": "2026-11-01",
                         "checksum": {"type": "MD5", "value": hashlib.md5(content).hexdigest()}}}


class FakeDataverse:
    """A Dataverse server for one dataset: a published version (or none) and maybe a draft, with the API calls the
    client makes. `fail` maps (method, path suffix) to a status to return once."""

    def __init__(self, published=None, draft=None, perms=None, released_collection=True):
        self.published = published          # list of file entries, or None if never published
        self.draft = draft                  # list of file entries, or None if no draft
        self.version = 1 if published is not None else 0
        self.next_id = 100
        self.calls = []
        self.fail = {}
        self.locks = []
        self.perms = perms or {"canEditDataset": True, "canPublishDataset": True, "canViewUnpublishedDataset": True}
        self.released_collection = released_collection

    def version_json(self, state, files):
        return {"versionState": state, "versionNumber": self.version if state == "RELEASED" else None,
                "versionMinorNumber": 0, "files": files, "license": {"name": "CC BY 4.0"},
                "metadataBlocks": {"citation": {"fields": [{"typeName": "title", "value": "WELL sensors"}]}}}

    def request(self, method, url, headers=None, timeout=None, params=None, files=None, data=None, **kwargs):
        parts = urlsplit(url)
        path = parts.path[len("/api/"):]
        self.calls.append({"method": method, "path": path, "headers": dict(headers or {}), "params": dict(params or {}),
                           "files": files, "data": data, "url": url})
        assert TOKEN not in url and TOKEN not in json.dumps(params or {}), "the token must stay out of URLs"
        for (m, suffix), status in list(self.fail.items()):
            if m == method and path.endswith(suffix):
                del self.fail[(m, suffix)]
                return Response(status, {"status": "ERROR", "message": getattr(self, "route_message", "nope")})
        token = (headers or {}).get("X-Dataverse-key")
        if token is not None and token != TOKEN:
            return Response(401, {"status": "ERROR", "message": "Bad api key "})
        return self.route(method, path, params or {}, files, data, token)

    def route(self, method, path, params, files, data, token):
        ok = lambda body: Response(200, {"status": "OK", "data": body})  # noqa: E731
        if path == "info/version":
            return ok({"version": "v6.12"})
        if path == "users/:me":
            return ok({"identifier": "@well-bot"}) if token else Response(401, {"message": "User with token null not found."})
        if path == "users/token":
            # As Dataverse answers: the token itself, then the date
            return ok({"message": f"Token {token} expires on 2027-11-01 10:00:00.0"})
        if path.startswith("dataverses/"):
            alias = path.split("/")[1]
            if path.endswith("/userPermissions"):
                return ok({"canAddDataset": bool(token), "canPublishDataverse": False})
            return ok({"alias": alias, "name": alias, "isReleased": self.released_collection})
        if path == "datasets/:persistentId":
            if self.draft is not None and token:
                return ok({"latestVersion": self.version_json("DRAFT", self.draft)})
            if self.published is None:
                return Response(401 if not token else 404, {"message": "not permitted"})
            return ok({"latestVersion": self.version_json("RELEASED", self.published)})
        if path == "datasets/:persistentId/versions/:latest-published":
            if self.published is None:
                return Response(404, {"message": "no published version"})
            return ok(self.version_json("RELEASED", self.published))
        if path == "datasets/:persistentId/userPermissions":
            return ok(self.perms)
        if path == "datasets/:persistentId/locks":
            return ok(self.locks.pop(0) if self.locks else [])
        if path == "datasets/:persistentId/add":
            name, content, _ = files["file"]
            meta = json.loads(data["jsonData"])
            entry = file_entry(self.next_id, name, content, meta.get("directoryLabel"))
            self.next_id += 1
            self.draft = list(self.draft if self.draft is not None else self.published or []) + [entry]
            return ok({"files": [entry]})
        if path.startswith("files/") and path.endswith("/replace"):
            file_id = int(path.split("/")[1])
            name, content, _ = files["file"]
            entry = file_entry(self.next_id, name, content)
            self.next_id += 1
            base = self.draft if self.draft is not None else self.published
            self.draft = [e for e in base if e["dataFile"]["id"] != file_id] + [entry]
            return ok({"files": [entry]})
        if path.startswith("files/") and method == "DELETE":
            file_id = int(path.split("/")[1])
            self.draft = [e for e in self.draft if e["dataFile"]["id"] != file_id]
            return Response(200, {"status": "OK", "data": {"message": "deleted"}})
        if path == "datasets/:persistentId/actions/:publish":
            if not self.released_collection:
                return Response(409, {"message": "the dataverse is not published"})
            if params.get("type") != "major":
                return Response(400, {"message": "Cannot publish as minor version. Re-try as major release."})
            self.published, self.draft = self.draft, None
            self.version += 1
            return ok({})
        return Response(404, {"message": f"no route {method} {path}"})

    def posts(self):
        return [(c["method"], c["path"]) for c in self.calls if c["method"] != "GET"]


def client(server):
    return borealis.Dataverse(SERVER, TOKEN, session=server, sleep=lambda s: None)


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        result = fn(*args, **kwargs)
    return result, out.getvalue()


CSV = b"ID,Timestamp\n1,2026-10-01T00:00:00\n"
NAME = "WELLWestCampus_Oct2026.csv"


class UploadFileTests(TestCase):
    def upload(self, server, content=CSV, publish=True):
        return borealis.upload_file(client(server), PID, NAME, content, "October", directory="2026", publish=publish,
                                    log=lambda *a: None)

    def test_adds_without_ingest_and_publishes_a_major_version(self):
        server = FakeDataverse(published=[])
        self.assertEqual(self.upload(server), ("added", "2.0"))
        add = next(c for c in server.calls if c["path"].endswith("/add"))
        meta = json.loads(add["data"]["jsonData"])
        self.assertEqual(meta["tabIngest"], "false")
        self.assertEqual(meta["directoryLabel"], "2026")
        self.assertEqual(add["headers"]["X-Dataverse-key"], TOKEN)
        publish = next(c for c in server.calls if c["path"].endswith(":publish"))
        self.assertEqual(publish["params"]["type"], "major")
        self.assertEqual([e["label"] for e in server.published], [NAME])

    def test_the_first_version_of_a_never_published_dataset(self):
        server = FakeDataverse(published=None, draft=[])
        self.assertEqual(self.upload(server), ("added", "1.0"))

    def test_running_again_sends_nothing(self):
        server = FakeDataverse(published=[file_entry(5, NAME, CSV, "2026")])
        self.assertEqual(self.upload(server), ("unchanged", None))
        self.assertEqual(server.posts(), [])

    def test_an_existing_draft_published_with_the_new_file_is_warned_about(self):
        server = FakeDataverse(published=[])
        server.draft = []   # e.g. a curator's metadata edit, open when the month's file goes up
        logs = []
        borealis.upload_file(client(server), PID, NAME, CSV, "October", log=logs.append)
        self.assertTrue(any("already had a draft" in line for line in logs), logs)
        logs.clear()
        borealis.upload_file(client(FakeDataverse(published=[])), PID, "WELLWestCampus_Nov2026.csv", CSV, "Nov",
                             log=logs.append)
        self.assertFalse(any("already had a draft" in line for line in logs), logs)

    def test_a_pending_file_with_publish_off_is_reported_as_pending(self):
        server = FakeDataverse(published=[], draft=[file_entry(7, NAME, CSV, "2026")])
        self.assertEqual(self.upload(server, publish=False), ("pending", None))

    def test_a_token_at_the_cut_of_a_long_non_json_body_is_still_redacted(self):
        class Html(Response):
            def json(self):
                raise ValueError("not JSON")
        response = Html(502)
        response.text = "x" * 190 + TOKEN + "y" * 50
        dv = client(FakeDataverse(published=[]))
        message = borealis.server_message(response, dv.redact)
        self.assertNotIn(TOKEN[:10], message)
        self.assertLessEqual(len(message), 200)

    def test_a_draft_this_upload_did_not_make_is_not_published(self):
        server = FakeDataverse(published=[file_entry(5, NAME, CSV, "2026")])
        server.draft = list(server.published)   # e.g. a curator editing the metadata
        self.assertEqual(self.upload(server), ("unchanged", None))
        self.assertEqual(server.posts(), [])
        self.assertIsNotNone(server.draft)

    def test_server_messages_that_repeat_the_token_are_redacted(self):
        server = FakeDataverse(published=[])
        server.fail[("POST", "/add")] = 400
        server.route_message = f"bad request for key {TOKEN}"
        with self.assertRaises(borealis.DataverseError) as caught:
            self.upload(server)
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertIn("[token]", str(caught.exception))
        expiry = client(FakeDataverse(published=[])).token_expiry()
        self.assertEqual(expiry, "The token expires on 2027-11-01 10:00:00.0")

    def test_a_publish_that_failed_is_finished_by_the_next_run_without_a_second_copy(self):
        server = FakeDataverse(published=[])
        server.fail[("POST", ":publish")] = 500
        with self.assertRaises(borealis.DataverseError):
            self.upload(server)
        self.assertEqual(len(server.draft), 1)
        self.assertEqual(self.upload(server), ("unchanged", "2.0"))
        self.assertEqual(len(server.published), 1)
        self.assertEqual(len([c for c in server.calls if c["path"].endswith("/add")]), 1)

    def test_a_changed_published_file_is_replaced(self):
        server = FakeDataverse(published=[file_entry(5, NAME, b"old", "2026")])
        self.assertEqual(self.upload(server), ("replaced", "2.0"))
        replace = next(c for c in server.calls if c["path"].endswith("/replace"))
        self.assertEqual(replace["path"], "files/5/replace")
        self.assertTrue(json.loads(replace["data"]["jsonData"])["forceReplace"])
        self.assertEqual(len(server.published), 1)

    def test_a_changed_unpublished_file_is_deleted_and_added_again(self):
        server = FakeDataverse(published=[], draft=[file_entry(7, NAME, b"half", "2026")])
        self.assertEqual(self.upload(server), ("replaced", "2.0"))
        self.assertIn(("DELETE", "files/7"), server.posts())
        self.assertEqual(len(server.published), 1)

    def test_a_file_ingested_earlier_is_found_by_its_original_name(self):
        entry = file_entry(5, "WELLWestCampus_Oct2026.tab", b"tab")
        entry["dataFile"]["originalFileName"] = NAME
        server = FakeDataverse(published=[entry])
        self.assertEqual(self.upload(server)[0], "replaced")

    def test_publish_off_leaves_the_draft(self):
        server = FakeDataverse(published=[])
        self.assertEqual(self.upload(server, publish=False), ("added", None))
        self.assertIsNotNone(server.draft)
        self.assertFalse(any(c["path"].endswith(":publish") for c in server.calls))

    def test_waits_for_a_lock_before_changing_the_dataset(self):
        server = FakeDataverse(published=[])
        server.locks = [[{"lockType": "Ingest"}], [{"lockType": "Ingest"}]]
        slept = []
        dv = borealis.Dataverse(SERVER, TOKEN, session=server, sleep=slept.append)
        borealis.upload_file(dv, PID, NAME, CSV, "October", log=lambda *a: None)
        self.assertEqual(slept, [borealis.LOCK_POLL_S] * 2)

    def test_a_lock_that_never_clears_fails_with_its_type(self):
        server = FakeDataverse(published=[])
        server.locks = [[{"lockType": "Workflow"}]] * 1000
        with self.assertRaisesRegex(borealis.DataverseError, "Workflow"):
            client(server).wait_unlocked(PID, timeout_s=10)

    def test_an_expired_token_says_so_without_printing_it(self):
        server = FakeDataverse(published=[])
        dv = borealis.Dataverse(SERVER, "expired", session=server)
        with self.assertRaises(borealis.DataverseError) as caught:
            borealis.upload_file(dv, PID, NAME, CSV, "October", log=lambda *a: None)
        self.assertEqual(caught.exception.status, 401)
        self.assertIn("expired", str(caught.exception))
        self.assertNotIn("expired\"", str(caught.exception))
        self.assertNotIn(SERVER, str(caught.exception))

    def test_no_permission_to_publish_names_the_role(self):
        server = FakeDataverse(published=[])
        server.fail[("POST", ":publish")] = 403
        with self.assertRaisesRegex(borealis.DataverseError, "Curator"):
            self.upload(server)

    def test_an_unpublished_collection_is_explained(self):
        server = FakeDataverse(published=None, draft=[], released_collection=False)
        with self.assertRaisesRegex(borealis.DataverseError, "HTTP 409.*collection isn't published"):
            self.upload(server)


class PublishedFilesTests(TestCase):
    def test_reads_only_the_published_version_and_mentions_a_waiting_draft(self):
        published = [file_entry(1, "WELLAncasterWatershed_May2026.csv", b"a")]
        server = FakeDataverse(published=published, draft=published + [file_entry(2, "WELLAncasterWatershed_Jun2026.csv", b"b")])
        logs = []
        files = borealis.published_files(client(server), PID, log=logs.append)
        self.assertEqual([f["dataFile"]["id"] for f in files], [1])
        self.assertIn("unpublished draft", logs[0])

    def test_never_published_is_empty(self):
        logs = []
        self.assertEqual(borealis.published_files(client(FakeDataverse(published=None, draft=[])), PID, log=logs.append), [])
        self.assertIn("never been published", logs[-1])

    def test_a_guest_can_read_a_published_dataset_and_gets_a_useful_401_otherwise(self):
        guest = borealis.Dataverse(SERVER, None, session=FakeDataverse(published=[file_entry(1, "x.csv", b"a")]))
        self.assertEqual(len(borealis.published_files(guest, PID, log=lambda *a: None)), 1)
        guest = borealis.Dataverse(SERVER, None, session=FakeDataverse(published=None))
        with self.assertRaisesRegex(borealis.DataverseError, "only published datasets"):
            borealis.published_files(guest, PID, log=lambda *a: None)


class DownloadTests(TestCase):
    def test_the_download_lists_only_published_sampling_files(self):
        published = [file_entry(1, "WELLAncasterWatershed_May2026.csv", b"a"),
                     file_entry(2, "WELLAncasterWatershed_SAMPLE.csv", b"t"), file_entry(3, "README.md", b"r")]
        server = FakeDataverse(published=published,
                               draft=published + [file_entry(4, "WELLAncasterWatershed_Jun2026.csv", b"b")])
        with mock.patch.multiple(download_data, BOREALIS_URL=SERVER, BOREALIS_API_TOKEN=TOKEN,
                                 BOREALIS_AW_PERSISTENT_ID=PID):
            files, out = quiet(download_data.get_files_from_dataset, client=client(server))
        self.assertEqual([f["id"] for f in files], [1])
        self.assertIn("unpublished draft", out)

    def test_a_demo_dataset_with_the_production_server_is_refused(self):
        with mock.patch.multiple(download_data, BOREALIS_URL="https://borealisdata.ca/dataverse/WELL",
                                 BOREALIS_API_TOKEN=None, BOREALIS_AW_PERSISTENT_ID="doi:10.80240/FK2/JER05H"), \
                self.assertRaisesRegex(ValueError, "BOREALIS_SAMPLING_PERSISTENT_ID"):
            quiet(download_data.get_files_from_dataset, client=client(FakeDataverse(published=[])))

    def test_a_rejected_token_fails_the_download_with_the_reason(self):
        server = FakeDataverse(published=[])
        with mock.patch.multiple(download_data, BOREALIS_URL=SERVER, BOREALIS_API_TOKEN="old",
                                 BOREALIS_AW_PERSISTENT_ID=PID), self.assertRaises(borealis.DataverseError):
            _, out = quiet(download_data.get_files_from_dataset,
                           client=borealis.Dataverse(SERVER, "old", session=server))


class SettingsTests(TestCase):
    def test_urls(self):
        self.assertEqual(borealis.base_url("https://borealisdata.ca/dataverse/WELL"), "https://borealisdata.ca")
        self.assertEqual(borealis.collection_alias("https://borealisdata.ca/dataverse/WELL/"), "WELL")
        self.assertIsNone(borealis.collection_alias("https://borealisdata.ca"))
        with self.assertRaises(ValueError):
            borealis.base_url("borealisdata.ca")

    def test_the_server_used_is_logged_once(self):
        logged = []
        with mock.patch.object(borealis, "_logged_servers", set()):
            for url in ("https://borealisdata.ca/dataverse/WELL", "https://borealisdata.ca/",
                        "https://demo.borealisdata.ca"):
                self.assertEqual(borealis.api_base(url, log=logged.append), borealis.base_url(url))
            borealis.api_base("https://borealisdata.ca/dataverse/WELL", log=logged.append)
        self.assertEqual(logged, [
            ("Borealis: using the API at https://borealisdata.ca (BOREALIS_URL is the page of collection WELL; "
             "the API is at the server root)"),
            "Borealis: using the API at https://demo.borealisdata.ca",
        ])

    def test_the_upload_uses_the_server_root_of_a_collection_url(self):
        with mock.patch.multiple(upload_data.Config, BOREALIS_URL="https://borealis.example/dataverse/WELL",
                                 BOREALIS_API_TOKEN=TOKEN, BOREALIS_UPLOAD_PERSISTENT_ID=PID), \
                mock.patch.object(borealis, "_logged_servers", set()), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            url, _, _ = upload_data.borealis_settings()
        self.assertEqual(url, SERVER)
        self.assertIn(f"Borealis: using the API at {SERVER}", out.getvalue())
        self.assertNotIn(TOKEN, out.getvalue())

    def test_demo(self):
        self.assertTrue(borealis.is_demo("https://demo.borealisdata.ca"))
        self.assertTrue(borealis.is_demo(persistent_id="doi:10.80240/FK2/WHEXLR"))
        self.assertFalse(borealis.is_demo("https://borealisdata.ca", "doi:10.5683/SP3/ABC"))


class UploadScriptTests(TestCase):
    def settings(self, **overrides):
        values = {"BOREALIS_URL": "https://borealis.example/dataverse/WELL", "BOREALIS_API_TOKEN": TOKEN,
                  "BOREALIS_UPLOAD_PERSISTENT_ID": PID, "BOREALIS_PUBLISH": True, **overrides}
        return mock.patch.multiple(upload_data.Config, **values)

    def test_reports_success_for_the_scheduler(self):
        server = FakeDataverse(published=[])
        with self.settings():
            _, out = quiet(upload_data.upload_to_borealis, CSV.decode(), NAME, 2026, client=client(server))
        self.assertIn(f"Successfully uploaded {NAME} to Borealis (added, published as version 2.0)", out)
        self.assertNotIn(TOKEN, out)

    def test_a_failure_exits_1_without_reporting_success(self):
        server = FakeDataverse(published=[])
        server.fail[("POST", "/add")] = 503
        with self.settings(), contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as caught:
            upload_data.upload_to_borealis(CSV.decode(), NAME, 2026, client=client(server))
        self.assertEqual(caught.exception.code, 1)
        self.assertNotIn("Successfully uploaded", out.getvalue())

    def upload_refused(self, status):
        """The exit code and output of an upload that Borealis answers with `status`."""
        server = FakeDataverse(published=[])
        server.fail[("POST", "/add")] = status
        with self.settings(), contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as caught:
            upload_data.upload_to_borealis(CSV.decode(), NAME, 2026, client=client(server))
        return caught.exception.code, out.getvalue()

    def test_a_rejected_token_stops_with_one_actionable_line(self):
        code, out = self.upload_refused(401)
        self.assertEqual(code, SETTINGS_ERROR_EXIT)
        errors = [line for line in out.splitlines() if line.startswith("ERROR:")]
        self.assertEqual(errors, [f"ERROR: Borealis token rejected (HTTP 401): make a new token on {SERVER} (your "
                                  f"name > API Token) and put it in BOREALIS_API_TOKEN."])
        self.assertNotIn(TOKEN, out)
        self.assertNotIn("Successfully uploaded", out)

    def test_a_missing_permission_is_a_settings_problem(self):
        code, out = self.upload_refused(403)
        self.assertEqual(code, SETTINGS_ERROR_EXIT)
        self.assertIn("Curator role", out)

    def test_a_demo_dataset_on_the_production_server_is_refused(self):
        with self.settings(BOREALIS_UPLOAD_PERSISTENT_ID="doi:10.80240/FK2/WHEXLR"), \
                contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as caught:
            upload_data.borealis_settings()
        self.assertIn("demo server", out.getvalue())
        self.assertEqual(caught.exception.code, SETTINGS_ERROR_EXIT)

    def test_missing_settings_are_named(self):
        with self.settings(BOREALIS_API_TOKEN=None), contextlib.redirect_stdout(io.StringIO()) as out, \
                self.assertRaises(SystemExit) as caught:
            upload_data.borealis_settings()
        self.assertIn("BOREALIS_API_TOKEN", out.getvalue())
        self.assertEqual(caught.exception.code, SETTINGS_ERROR_EXIT)

    def test_the_upload_is_on_only_with_a_dataset(self):
        self.assertFalse(borealis.upload_on({}))
        self.assertFalse(borealis.upload_on({"BOREALIS_URL": "https://borealisdata.ca", "BOREALIS_API_TOKEN": "t",
                                             "BOREALIS_UPLOAD_PERSISTENT_ID": " "}))
        self.assertTrue(borealis.upload_on({"BOREALIS_UPLOAD_PERSISTENT_ID": PID}))
        self.assertTrue(borealis.upload_on({"DEMO_BOREALIS_WC_PERSISTENT_ID": "doi:10.80240/FK2/WHEXLR"}))

    def test_month_file_name(self):
        import datetime as dt
        self.assertEqual(upload_data.month_file_name(dt.datetime(2026, 10, 1)), NAME)

    def test_csv_layout(self):
        rows = [
            {"station_id": "Weather Station", "group_type": "Weather", "measurement_type": "Rain", "value": 1.5,
             "unit": "mm", "recorded_at": "2026-10-01T00:00:00"},
            {"station_id": "2577531", "group_type": "Logger", "measurement_type": "Water Temperature", "value": 8.25,
             "unit": "C", "recorded_at": "2026-10-01T00:00:00"},
            {"station_id": "2577532", "group_type": "Logger", "measurement_type": "Water Temperature", "value": 9.0,
             "unit": "C", "recorded_at": "2026-10-01T00:10:00"},
            {"station_id": "2577532", "group_type": "Logger", "measurement_type": "Water Temperature", "value": 99.0,
             "unit": "C", "recorded_at": "2026-10-01T00:10:00"},   # a second reading: the first one is kept
        ]
        out = io.StringIO()
        quiet(upload_data.build_csv_frontend_style, rows, out)
        header = ("ID,Timestamp (America/Toronto),Group,Latitude,Longitude,Rain: mm,,Group,Sensor,Latitude,"
                  "Longitude,Water Temperature: C,Sensor,Latitude,Longitude,Water Temperature: C")
        row1 = ("1,2026-10-01T00:00:00,Weather,43.26611,-79.92866,1.5,,Logger,Logger 1,43.2671,-79.92883,8.25,"
                "Logger 2,43.26639,-79.9294,")
        row2 = ("2,2026-10-01T00:10:00,Weather,43.26611,-79.92866,,,Logger,Logger 1,43.2671,-79.92883,,"
                "Logger 2,43.26639,-79.9294,9.0")
        self.assertEqual(out.getvalue().splitlines(), [header, row1, row2])

    def test_csv_has_no_nan_and_neutralizes_formulas(self):
        # A missing value (None from the database, NaN once in pandas) is an empty field, not "nan", and text a
        # spreadsheet would run gets a leading apostrophe, as in the dashboard download
        rows = [
            {"station_id": "Weather Station", "group_type": "Weather", "measurement_type": "Rain", "value": None,
             "unit": "mm", "recorded_at": "2026-10-01T00:00:00"},
            {"station_id": "Weather Station", "group_type": "Weather", "measurement_type": "Rain", "value": 0.5,
             "unit": "mm", "recorded_at": "2026-10-01T00:10:00"},
            {"station_id": "Weather Station", "group_type": "Weather", "measurement_type": "=1+2",
             "value": float("nan"), "unit": "", "recorded_at": "2026-10-01T00:10:00"},
            {"station_id": "Weather Station", "group_type": "Weather", "measurement_type": "-Wind", "value": -3.0,
             "unit": "", "recorded_at": "2026-10-01T00:10:00"},
        ]
        out = io.StringIO()
        quiet(upload_data.build_csv_frontend_style, rows, out)
        self.assertNotIn("nan", out.getvalue().lower())
        self.assertEqual(out.getvalue().splitlines(), [
            "ID,Timestamp (America/Toronto),Group,Latitude,Longitude,'-Wind,'=1+2,Rain: mm",
            "1,2026-10-01T00:00:00,Weather,43.26611,-79.92866,,,",
            "2,2026-10-01T00:10:00,Weather,43.26611,-79.92866,-3.0,,0.5",
        ])


class PreflightTests(TestCase):
    SETTINGS = {"url": "https://borealis.example/dataverse/WELL", "token": TOKEN, "upload_pid": PID,
                "sampling_pid": "doi:10.5683/SP3/WELLSAMPLE", "upload_alias": "WELL-sensors",
                "sampling_alias": "WELL-sampling"}

    def run_checks(self, server, **settings):
        lines = []
        merged = {**self.SETTINGS, **settings}
        dv = borealis.Dataverse(SERVER, merged["token"], session=server, sleep=lambda s: None)
        missing = borealis_check.run_checks(merged, client=dv, out=lines.append)
        self.assertFalse(any(TOKEN in line for line in lines))
        self.assertEqual([c["method"] for c in server.calls], ["GET"] * len(server.calls), "read-only")
        return missing, "\n".join(lines)

    def test_ready(self):
        files = [file_entry(1, "WELLAncasterWatershed_SAMPLE.csv", b"t"), file_entry(2, "README.md", b"r")]
        missing, text = self.run_checks(FakeDataverse(published=files))
        self.assertEqual(missing, [], text)
        self.assertIn("Ready", text)

    def test_what_is_missing_is_listed(self):
        server = FakeDataverse(published=None, draft=[], released_collection=False,
                               perms={"canEditDataset": True, "canPublishDataset": False})
        missing, text = self.run_checks(server)
        self.assertTrue(any("publish the parent collection WELL" in m for m in missing), text)
        self.assertTrue(any("lacks canPublishDataset" in m for m in missing), text)
        self.assertTrue(any("publish the sampling dataset" in m for m in missing), text)
        self.assertIn("Not ready", text)

    def test_a_rejected_token_is_the_first_thing_missing(self):
        missing, text = self.run_checks(FakeDataverse(published=[]), token="old-token")
        self.assertIn("rejected", missing[0])

    def test_demo_settings_are_flagged(self):
        missing, _ = self.run_checks(FakeDataverse(published=[]), url="https://demo.borealisdata.ca",
                                     upload_pid="doi:10.80240/FK2/WHEXLR")
        self.assertTrue(any("demo server" in m for m in missing))


if __name__ == "__main__":
    main()
