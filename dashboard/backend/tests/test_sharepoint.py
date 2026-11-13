"""The SharePoint (Microsoft Graph) uploader, against a fake Graph (no network).
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import base64
import contextlib
import io
import os
import pathlib
import sys
from unittest import TestCase, main, mock
from urllib.parse import unquote, urlsplit

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils import sharepoint  # noqa: E402
from scripts import sharepoint_upload  # noqa: E402

SECRET = "CLIENT-SECRET-123"
ACCESS = "ACCESS-TOKEN-456"
UPLOAD_URL = "https://upload.example/session/1"
ENV = {"SHAREPOINT_TENANT_ID": "tenant-1", "SHAREPOINT_CLIENT_ID": "app-1", "SHAREPOINT_CLIENT_SECRET": SECRET,
       "SHAREPOINT_SITE": "https://contoso.sharepoint.com/sites/WELL"}


class Response:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self.body, self.headers = status, body, headers or {}
        self.content = b"x" if body is not None else b""

    def json(self):
        if self.body is None:
            raise ValueError("no JSON")
        return self.body


class FakeGraph:
    """Sign-in, one site with a "Documents" library, items by path, folders and upload sessions."""

    def __init__(self, items=None):
        self.items = dict(items or {})     # path -> item JSON
        self.calls, self.fail, self.received = [], {}, b""
        self.token_status = 200

    def request(self, method, url, headers=None, timeout=None, data=None, json=None, **kwargs):
        headers = dict(headers or {})
        self.calls.append((method, url, headers, data, json))
        for key, response in list(self.fail.items()):
            if key == (method, url.split("?")[0]) or (key[0] == method and url.endswith(key[1])):
                responses = response if isinstance(response, list) else [response]
                out = responses.pop(0)
                if not responses:
                    del self.fail[key]
                return out
        if url.startswith(sharepoint.LOGIN):
            if self.token_status != 200:
                return Response(self.token_status, {"error": "invalid_client",
                                                    "error_description": "AADSTS7000215: Invalid client secret provided.\nTrace ID: x"})
            assert data["client_secret"] == SECRET and data["grant_type"] == "client_credentials"
            return Response(200, {"access_token": ACCESS})
        if url.startswith(UPLOAD_URL):
            assert "Authorization" not in headers, "the upload URL must not get the token"
            if method == "DELETE":
                return Response(204)
            first, last, total = parse_range(headers["Content-Range"])
            assert first == len(self.received) and last - first + 1 == len(data)
            self.received += data
            if last + 1 < total:
                return Response(202, {"nextExpectedRanges": [f"{last + 1}-"]})
            item = {"id": "file-1", "size": total, "webUrl": "https://contoso.sharepoint.com/x.csv",
                    "file": {"hashes": {"quickXorHash": sharepoint.quick_xor_hash(self.received)}}}
            self.items[self.pending] = item
            return Response(201, item)
        assert headers.get("Authorization") == f"Bearer {ACCESS}"
        path = urlsplit(url).path[len("/v1.0/"):]
        if path == "sites/contoso.sharepoint.com:/sites/WELL":
            return Response(200, {"id": "site-1", "displayName": "WELL", "webUrl": "https://contoso.sharepoint.com/sites/WELL"})
        if path == "sites/site-1/drives":
            return Response(200, {"value": [{"id": "drive-1", "name": "Documents",
                                             "webUrl": "https://contoso.sharepoint.com/sites/WELL/Shared%20Documents"}]})
        if path.startswith("drives/drive-1/root:/") and path.endswith(":/createUploadSession"):
            self.pending = unquote(path[len("drives/drive-1/root:/"):-len(":/createUploadSession")])
            assert json["item"]["@microsoft.graph.conflictBehavior"] == "replace"
            return Response(200, {"uploadUrl": UPLOAD_URL})
        if method == "POST" and path.endswith("/children"):
            parent = unquote(path[len("drives/drive-1/root:/"):-len(":/children")]) if ":/" in path else ""
            folder = f"{parent}/{json['name']}" if parent else json["name"]
            self.items[folder] = {"id": folder, "folder": {}}
            return Response(201, self.items[folder])
        if method == "GET" and path.startswith("drives/drive-1/root:/"):
            item = self.items.get(unquote(path[len("drives/drive-1/root:/"):]))
            return Response(200, item) if item else Response(404, {"error": {"message": "itemNotFound"}})
        return Response(404, {"error": {"message": f"no route {method} {path}"}})


def parse_range(value):
    span, total = value[len("bytes "):].split("/")
    first, last = span.split("-")
    return int(first), int(last), int(total)


def make_client(graph, **env):
    slept = []
    client = sharepoint.SharePoint(sharepoint.settings({**ENV, **env}), session=graph, sleep=slept.append)
    return client, slept


CSV = b"ID,Timestamp\n" + b"1,2026-10-01T00:00:00\n" * 40000   # about 880 KB: several chunks below
NAME = "WELLWestCampus_Oct2026.csv"
PATH = f"WELL sensor data/2026/{NAME}"


class SettingsTests(TestCase):
    def test_status(self):
        self.assertEqual(sharepoint.status({}), ("off", []))
        self.assertEqual(sharepoint.status(ENV), ("on", []))
        self.assertEqual(sharepoint.status({"SHAREPOINT_SITE": "x", "SHAREPOINT_CLIENT_SECRET": " "}),
                         ("incomplete", ["SHAREPOINT_TENANT_ID", "SHAREPOINT_CLIENT_ID", "SHAREPOINT_CLIENT_SECRET"]))

    def test_defaults_and_site_path(self):
        config = sharepoint.settings(ENV)
        self.assertEqual((config["library"], config["folder"]), ("Documents", "WELL sensor data"))
        self.assertEqual(sharepoint.site_path("https://contoso.sharepoint.com/sites/WELL/"),
                         "contoso.sharepoint.com:/sites/WELL")
        self.assertEqual(sharepoint.site_path("contoso.sharepoint.com:/sites/WELL"), "contoso.sharepoint.com:/sites/WELL")

    def test_quick_xor_hash(self):
        self.assertEqual(sharepoint.quick_xor_hash(b""), "AAAAAAAAAAAAAAAAAAAAAAAAAAA=")
        # One byte sits at bit 0; the length (1) is XORed in at bit 96, i.e. byte 12
        self.assertEqual(sharepoint.quick_xor_hash(b"J"), "SgAAAAAAAAAAAAAAAQAAAAAAAAA=")
        # The 15th byte starts at bit 154 and wraps around into bit 0
        digest = base64.b64decode(sharepoint.quick_xor_hash(b"\0" * 14 + b"\xff"))
        self.assertEqual((digest[19] >> 2, digest[0] & 0b11), (0b111111, 0b11))


class UploadTests(TestCase):
    def setUp(self):
        patch = mock.patch.object(sharepoint, "CHUNK", 320 * 1024)
        patch.start()
        self.addCleanup(patch.stop)

    def upload(self, graph, content=CSV):
        client, slept = make_client(graph)
        result = sharepoint.upload_month_file(client, NAME, content, 2026, log=lambda *a: None)
        return result, slept

    def test_a_new_file_creates_the_folders_and_goes_up_in_chunks(self):
        graph = FakeGraph()
        (outcome, url), _ = self.upload(graph)
        self.assertEqual(outcome, "added")
        self.assertEqual(graph.received, CSV)
        self.assertIn("WELL sensor data", graph.items)
        self.assertIn("WELL sensor data/2026", graph.items)
        puts = [c for c in graph.calls if c[0] == "PUT"]
        self.assertEqual(len(puts), 3)
        self.assertEqual(len([c for c in graph.calls if c[1].startswith(sharepoint.LOGIN)]), 1, "one sign-in")
        for _, _, headers, data, _ in graph.calls:
            self.assertNotIn(SECRET, str(headers))

    def test_the_same_file_is_not_sent_again(self):
        graph = FakeGraph()
        self.upload(graph)
        graph.calls.clear()
        (outcome, _), _ = self.upload(graph)
        self.assertEqual(outcome, "unchanged")
        self.assertFalse([c for c in graph.calls if c[0] in ("PUT", "POST") and not c[1].startswith(sharepoint.LOGIN)])

    def test_a_changed_file_replaces_the_old_one(self):
        graph = FakeGraph({PATH: {"id": "old", "size": 3, "file": {"hashes": {"quickXorHash": "x"}}},
                           "WELL sensor data": {"folder": {}}, "WELL sensor data/2026": {"folder": {}}})
        (outcome, _), _ = self.upload(graph)
        self.assertEqual(outcome, "replaced")
        self.assertFalse([c for c in graph.calls if c[0] == "POST" and c[1].endswith("/children")])

    def test_throttling_is_retried_after_the_wait_graph_asks_for(self):
        graph = FakeGraph()
        graph.fail[("GET", "/sites/contoso.sharepoint.com:/sites/WELL")] = [Response(429, {}, {"Retry-After": "7"})]
        (outcome, _), slept = self.upload(graph)
        self.assertEqual((outcome, slept), ("added", [7.0]))

    def test_a_failed_chunk_cancels_the_session(self):
        graph = FakeGraph()
        graph.fail[("PUT", UPLOAD_URL)] = [Response(500, {"error": {"message": "boom"}})]
        with self.assertRaises(sharepoint.SharePointError):
            self.upload(graph)
        self.assertEqual(graph.calls[-1][0], "DELETE")

    def test_a_wrong_secret_is_explained_without_printing_it(self):
        graph = FakeGraph()
        graph.token_status = 401
        with self.assertRaises(sharepoint.SharePointError) as caught:
            self.upload(graph)
        message = str(caught.exception)
        self.assertIn("AADSTS7000215", message)
        self.assertIn("SHAREPOINT_CLIENT_SECRET", message)
        self.assertNotIn(SECRET, message)
        self.assertNotIn("Trace ID", message)

    def test_no_write_grant_on_the_site_is_explained(self):
        graph = FakeGraph()
        graph.fail[("POST", ":/createUploadSession")] = [Response(403, {"error": {"message": "Access denied"}})]
        with self.assertRaisesRegex(sharepoint.SharePointError, "Sites.Selected"):
            self.upload(graph)

    def test_an_unknown_library_lists_the_ones_there(self):
        client, _ = make_client(FakeGraph(), SHAREPOINT_LIBRARY="Data")
        with self.assertRaisesRegex(sharepoint.SharePointError, "libraries are: Documents"):
            client.drive()

    def test_the_library_can_be_named_as_in_its_url(self):
        client, _ = make_client(FakeGraph(), SHAREPOINT_LIBRARY="Shared Documents")
        self.assertEqual(client.drive(), "drive-1")


class ScriptTests(TestCase):
    def test_check_is_read_only(self):
        graph = FakeGraph()
        with mock.patch.dict(os.environ, ENV), contextlib.redirect_stdout(io.StringIO()) as out:
            sharepoint_upload.check(sharepoint_upload.configured_client(session=graph))
        self.assertIn("Ready", out.getvalue())
        self.assertEqual({c[0] for c in graph.calls if not c[1].startswith(sharepoint.LOGIN)}, {"GET"})

    def test_off_and_incomplete_settings_exit_1(self):
        for env in ({}, {"SHAREPOINT_SITE": "x"}):
            clean = {k: v for k, v in os.environ.items() if not k.startswith("SHAREPOINT_")}
            with mock.patch.dict(os.environ, {**clean, **env}, clear=True), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
                sharepoint_upload.configured_client()
            self.assertEqual(caught.exception.code, 1)


if __name__ == "__main__":
    main()
