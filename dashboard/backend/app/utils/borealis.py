"""A small client for the Dataverse API of Borealis (borealisdata.ca), used by the monthly sensor upload
(scripts/upload_data.py), the weekly sampling download (scripts/download_data.py) and the preflight check
(scripts/borealis_check.py). Needs only requests.

Settings (dashboard/backend/app/.env on the VM; config.py reads them):
  BOREALIS_URL                     the server, e.g. https://borealisdata.ca. A collection page such as
                                   https://borealisdata.ca/dataverse/WELL also works: only its scheme and host are
                                   used, and its alias (WELL) is the parent collection the preflight checks.
  BOREALIS_API_TOKEN               the API token of the account that uploads and publishes
  BOREALIS_UPLOAD_PERSISTENT_ID    the sensor dataset the monthly upload adds files to, e.g. doi:10.5683/SP3/ABCDEF
  BOREALIS_SAMPLING_PERSISTENT_ID  the sampling dataset the weekly download imports from
  BOREALIS_UPLOAD_DATAVERSE, BOREALIS_SAMPLING_DATAVERSE   the aliases of the collections holding them (preflight only).
                                   They don't default to BOREALIS_URL's alias: the datasets sit in sub-collections of
                                   it, and the preflight already checks that alias as the parent collection.
The older DEMO_BOREALIS_URL, DEMO_BOREALIS_WC_PERSISTENT_ID and DEMO_BOREALIS_AW_PERSISTENT_ID are still read when
the new names are unset.

Dataverse rules this module follows:
- Adding or replacing a file changes the dataset's draft version, which only the dataset's editors can see. The
  file is public (and counts as an off-VM copy that anyone can cite) only once that draft is published.
- A version that changes files must be published as a major version (1.0, 2.0, ...): Dataverse refuses a minor
  version then. Publishing the first version also needs the collection above it to be published.
- A tabular file (CSV, Excel) is normally "ingested": converted to a .tab file, with the original kept. Uploads
  here turn that off (tabIngest false), so the CSV is stored as sent, its checksum matches ours, and no ingest lock
  holds up publishing.
- The token goes in the X-Dataverse-key header, never in a URL (requests prints URLs in its errors).
"""
import hashlib
import json
import os
import time
from urllib.parse import urlsplit

import requests

TIMEOUT = (10, 120)
UPLOAD_TIMEOUT = (10, 600)
# Waiting for a dataset lock (e.g. the one held while a published version's DOI is registered) to clear.
LOCK_WAIT_S = 10 * 60
LOCK_POLL_S = 5

# The demo server and its test DOI shoulder: data there is not a backup (the demo server is reset from time to time).
DEMO_HOSTS = ("demo.borealisdata.ca",)
DEMO_DOI_PREFIX = "doi:10.80240/"


class DataverseError(Exception):
    """A Dataverse API call failed. The message says what to do; it never includes the token or a full URL."""

    def __init__(self, action, status=None, message="", with_token=True):
        self.action, self.status, self.server_message = action, status, (message or "").strip()
        super().__init__(describe_failure(action, status, self.server_message, with_token))


def describe_failure(action, status, message, with_token=True):
    if status in (401, 403) and not with_token:
        hint = ("without BOREALIS_API_TOKEN only published datasets and collections can be read: publish it on "
                "Borealis, or set the token")
        return ". ".join(p for p in (f"{action} failed (HTTP {status})",
                                     message and f"Borealis says: {message[:300]}", hint) if p)
    hint = {
        401: "Borealis rejected the API token: it is wrong or has expired. Create a new one (Borealis: your name > "
             "API Token) and put it in BOREALIS_API_TOKEN.",
        403: "the token's account isn't allowed to do this: it needs the Curator role (add files and publish) on "
             "the dataset or its collection. Run scripts/borealis_check.py to see which permission is missing.",
        404: "not found: check the persistent id (doi:...) and BOREALIS_URL. A doi:10.80240/FK2/... id is on the "
             "demo server (demo.borealisdata.ca), not on borealisdata.ca.",
        409: "Dataverse refused the change in the dataset's current state (e.g. it is locked, or its collection "
             "isn't published yet).",
    }.get(status, "")
    parts = [f"{action} failed"]
    if status:
        parts[0] += f" (HTTP {status})"
    if message:
        parts.append(f"Borealis says: {message[:300]}")
    if hint:
        parts.append(hint)
    return ". ".join(parts)


def base_url(url):
    """The server part of BOREALIS_URL: https://borealisdata.ca/dataverse/WELL -> https://borealisdata.ca."""
    parts = urlsplit((url or "").strip())
    if not parts.scheme or not parts.netloc:
        raise ValueError(f"BOREALIS_URL must be a URL such as https://borealisdata.ca, got {url!r}")
    return f"{parts.scheme}://{parts.netloc}"


_logged_servers = set()


def api_base(url, log=print):
    """base_url(url), and the first time each server is used in this process, a log line naming it (and saying when
    a collection page's path was dropped), so a job's log shows which Borealis host its calls go to."""
    server = base_url(url)
    if server not in _logged_servers:
        _logged_servers.add(server)
        alias = collection_alias(url)
        note = f" (BOREALIS_URL is the page of collection {alias}; the API is at the server root)" if alias else ""
        log(f"Borealis: using the API at {server}{note}")
    return server


def collection_alias(url):
    """The collection alias in a BOREALIS_URL like https://borealisdata.ca/dataverse/WELL ("WELL"), else None."""
    segments = [s for s in urlsplit((url or "").strip()).path.split("/") if s]
    if len(segments) >= 2 and segments[0] == "dataverse":
        return segments[1]
    return None


def upload_on(env=None):
    """Whether the monthly upload is set up: a dataset is named for it in BOREALIS_UPLOAD_PERSISTENT_ID (or the
    older DEMO_BOREALIS_WC_PERSISTENT_ID). Without one it is off on purpose, so the scheduler skips it quietly;
    with one, scripts/upload_data.py says which other setting is missing."""
    env = os.environ if env is None else env
    return any((env.get(name) or "").strip()
               for name in ("BOREALIS_UPLOAD_PERSISTENT_ID", "DEMO_BOREALIS_WC_PERSISTENT_ID"))


def is_demo(url=None, persistent_id=None):
    """True if the server or the persistent id is the demo one."""
    host = urlsplit(url or "").netloc.lower()
    return host in DEMO_HOSTS or (persistent_id or "").startswith(DEMO_DOI_PREFIX)


def file_checksum(content, algorithm):
    """The checksum of `content` (bytes) in Dataverse's notation for `algorithm` ("MD5", "SHA-1", "SHA-256")."""
    return hashlib.new(algorithm.replace("-", "").lower(), content).hexdigest()


class Dataverse:
    """One Dataverse server. `session` is a requests.Session or anything with the same request() method (tests
    pass a fake). `sleep` is time.sleep, replaceable in tests."""

    def __init__(self, url, token=None, session=None, sleep=time.sleep):
        self.url = base_url(url)
        self.token = (token or "").strip() or None
        self.session = session or requests.Session()
        self.sleep = sleep

    # ---- plumbing

    def call(self, method, path, action, ok=(200,), timeout=TIMEOUT, allow=(), **kwargs):
        """The response's parsed JSON for an API call. Raises DataverseError for a status not in `ok`, except one in
        `allow`, which returns None (e.g. 404 for "not published yet")."""
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["X-Dataverse-key"] = self.token
        try:
            response = self.session.request(method, f"{self.url}/api/{path}", headers=headers, timeout=timeout,
                                            **kwargs)
        except requests.exceptions.RequestException as e:
            raise DataverseError(action, None, f"no answer ({type(e).__name__})") from None
        if response.status_code in allow:
            return None
        if response.status_code not in ok:
            raise DataverseError(action, response.status_code, server_message(response, self.redact),
                                 self.token is not None)
        try:
            return response.json()
        except ValueError:
            raise DataverseError(action, response.status_code, "the answer isn't JSON") from None

    def redact(self, text):
        """`text` with the token replaced, for anything the server says that is printed or raised: some answers
        repeat the token (e.g. GET /api/users/token says "Token <token> expires on ...")."""
        text = text or ""
        return text.replace(self.token, "[token]") if self.token else text

    def pid_call(self, method, path, persistent_id, action, **kwargs):
        params = {**kwargs.pop("params", {}), "persistentId": persistent_id}
        return self.call(method, f"datasets/:persistentId{path}", action, params=params, **kwargs)

    # ---- reading

    def version(self):
        return self.call("GET", "info/version", "Reading the Borealis version")["data"]["version"]

    def me(self):
        """The token's account (identifier, email, ...). Raises DataverseError with 401 for a bad token."""
        return self.call("GET", "users/:me", "Checking the API token")["data"]

    def token_expiry(self):
        """When the token expires, e.g. "The token expires on 2027-11-01 10:00:00.0". Dataverse answers
        "Token <the token itself> expires on <date>", so only the date is kept."""
        body = self.call("GET", "users/token", "Reading the token's expiry date")
        message = (body.get("data") or {}).get("message", "") or ""
        if " expires on " in message:
            return "The token expires on " + message.split(" expires on ", 1)[1].strip()
        return self.redact(message)

    def collection(self, alias):
        return self.call("GET", f"dataverses/{alias}", f"Reading collection {alias}")["data"]

    def collection_permissions(self, alias):
        return self.call("GET", f"dataverses/{alias}/userPermissions",
                         f"Reading your permissions on collection {alias}")["data"]

    def dataset(self, persistent_id):
        """The dataset with its latest version: the draft if there is one and the token may see it."""
        return self.pid_call("GET", "", persistent_id, f"Reading dataset {persistent_id}")["data"]

    def published_version(self, persistent_id):
        """The latest published version (with its files), or None if the dataset was never published."""
        body = self.pid_call("GET", "/versions/:latest-published", persistent_id,
                             f"Reading the published version of {persistent_id}", allow=(404,))
        return body["data"] if body else None

    def dataset_permissions(self, persistent_id):
        return self.pid_call("GET", "/userPermissions", persistent_id,
                             f"Reading your permissions on dataset {persistent_id}")["data"]

    def locks(self, persistent_id):
        return self.pid_call("GET", "/locks", persistent_id, f"Reading the locks on {persistent_id}")["data"] or []

    def wait_unlocked(self, persistent_id, timeout_s=LOCK_WAIT_S):
        """Wait until the dataset has no lock (Dataverse refuses changes to a locked dataset)."""
        waited = 0
        while True:
            locks = self.locks(persistent_id)
            if not locks:
                return
            if waited >= timeout_s:
                kinds = ", ".join(sorted({str(lock.get("lockType")) for lock in locks}))
                raise DataverseError(f"Waiting for {persistent_id} to unlock", None,
                                     f"still locked ({kinds}) after {timeout_s // 60} min")
            self.sleep(LOCK_POLL_S)
            waited += LOCK_POLL_S

    # ---- changing

    def add_file(self, persistent_id, name, content, description, directory=None):
        """Add a CSV file to the dataset's draft (made if there is none). Returns Dataverse's dataFile record."""
        meta = file_metadata(description, directory)
        body = self.pid_call("POST", "/add", persistent_id, f"Adding {name} to {persistent_id}",
                             files={"file": (name, content, "text/csv")}, data={"jsonData": json.dumps(meta)},
                             timeout=UPLOAD_TIMEOUT)
        return body["data"]["files"][0]["dataFile"]

    def replace_file(self, file_id, name, content, description, directory=None):
        """Replace a published file with a new copy (the old one stays in the earlier versions)."""
        meta = {**file_metadata(description, directory), "forceReplace": True}
        body = self.call("POST", f"files/{file_id}/replace", f"Replacing {name} (file {file_id})",
                         files={"file": (name, content, "text/csv")}, data={"jsonData": json.dumps(meta)},
                         timeout=UPLOAD_TIMEOUT)
        return body["data"]["files"][0]["dataFile"]

    def delete_file(self, file_id, name):
        """Delete a file that is only in the draft (never published), so a new copy can take its place."""
        self.call("DELETE", f"files/{file_id}", f"Deleting the unpublished {name} (file {file_id})", ok=(200, 204))

    def publish(self, persistent_id):
        """Publish the draft as a major version (needed whenever files changed) and wait until it is finished."""
        self.wait_unlocked(persistent_id)
        self.pid_call("POST", "/actions/:publish", persistent_id, f"Publishing {persistent_id}",
                      params={"type": "major"}, ok=(200, 202))
        self.wait_unlocked(persistent_id)   # 202: publishing goes on in the background (DOI registration)
        latest = self.dataset(persistent_id)["latestVersion"]
        if latest.get("versionState") != "RELEASED":
            raise DataverseError(f"Publishing {persistent_id}", None,
                                 f"the latest version is still {latest.get('versionState')}")
        return f"{latest.get('versionNumber')}.{latest.get('versionMinorNumber')}"


def file_metadata(description, directory):
    # tabIngest "false": keep the CSV as uploaded, instead of Dataverse converting it to its own tabular format.
    meta = {"description": description, "categories": ["Data"], "tabIngest": "false"}
    if directory:
        meta["directoryLabel"] = directory
    return meta


def server_message(response, redact=lambda text: text):
    """Dataverse's error message ({"status": "ERROR", "message": ...}), or the start of a non-JSON body, with
    `redact` applied to the whole text before it is shortened (so no part of a token can be left at the cut)."""
    try:
        body = response.json()
        if isinstance(body, dict) and body.get("message"):
            return redact(str(body["message"]))
    except ValueError:
        pass   # not JSON (e.g. a proxy's HTML error page): fall back to the start of the body
    return redact(getattr(response, "text", "") or "")[:200]


def find_file(version, name):
    """The file entry of `version` (a dataset version's JSON) named `name`, or None. A file ingested earlier is
    listed as .tab, with its original name kept in originalFileName, so that counts too."""
    for f in version.get("files") or []:
        datafile = f.get("dataFile") or {}
        if name in (f.get("label"), datafile.get("filename"), datafile.get("originalFileName")):
            return f
    return None


def same_content(entry, content):
    """True if the file entry's checksum matches `content` (bytes)."""
    checksum = (entry.get("dataFile") or {}).get("checksum") or {}
    if not checksum.get("type") or not checksum.get("value"):
        return False
    try:
        return file_checksum(content, checksum["type"]) == checksum["value"].lower()
    except ValueError:  # an algorithm hashlib doesn't know
        return False


def upload_file(client, persistent_id, name, content, description, directory=None, publish=True, log=print):
    """Put `content` (bytes) into the dataset as `name` and publish it. Safe to run again after any failure.

    - The same file (same name and checksum) already there: nothing is uploaded.
    - A file of that name with other content: a published one is replaced (Dataverse keeps the old copy in the
      earlier version); one only in the draft (say, from a run that failed before publishing) is deleted and added
      again, since Dataverse can't replace an unpublished file.
    - Otherwise it is added.
    Then, with `publish`, the draft is published as a major version, but only if it holds this month's file
    unpublished: added or replaced by this run, or left by an earlier run that failed before publishing. A draft
    that holds only someone else's changes (say, a curator's metadata edit in progress) is left alone. Dataverse
    has a single draft, though: when a draft was already open before this run (a curator's edit, or an earlier
    run's file), publishing it publishes everything in it, and a warning is logged.

    Returns (what happened, the published version or None). What happened is "added", "replaced" or "unchanged";
    or "pending" with publish off: the identical file is already there but only in the draft (an earlier run's),
    still to be published.
    """
    dataset = client.dataset(persistent_id)
    latest = dataset.get("latestVersion") or {}
    entry = find_file(latest, name)
    content = content.encode("utf-8") if isinstance(content, str) else content

    if entry and same_content(entry, content):
        outcome = "unchanged"
        log(f"{name} is already in {persistent_id} with the same content; not uploading it again")
        if latest.get("versionState") == "DRAFT":
            published = client.published_version(persistent_id)
            published_ids = {(f.get("dataFile") or {}).get("id") for f in (published or {}).get("files") or []}
            if entry["dataFile"].get("id") not in published_ids:
                outcome = "pending"   # an earlier run added it but didn't get to publish
    elif entry:
        datafile = entry["dataFile"]
        published = client.published_version(persistent_id) if latest.get("versionState") == "DRAFT" else latest
        published_ids = {(f.get("dataFile") or {}).get("id") for f in (published or {}).get("files") or []}
        client.wait_unlocked(persistent_id)
        if datafile.get("id") in published_ids:
            client.replace_file(datafile["id"], name, content, description, directory)
            outcome = "replaced"
            log(f"Replaced {name} in {persistent_id} (its content had changed)")
        else:
            client.delete_file(datafile["id"], name)
            client.add_file(persistent_id, name, content, description, directory)
            outcome = "replaced"
            log(f"Replaced the unpublished {name} in {persistent_id}")
    else:
        client.wait_unlocked(persistent_id)
        client.add_file(persistent_id, name, content, description, directory)
        outcome = "added"
        log(f"Added {name} to {persistent_id}")

    if not publish:
        log(f"Not publishing {persistent_id} (BOREALIS_PUBLISH is off): a curator publishes the draft")
        return outcome, None
    if outcome == "unchanged":
        if latest.get("versionState") == "DRAFT":
            log(f"{persistent_id} has a draft that this upload didn't make; leaving it for a curator to publish")
        return outcome, None
    if latest.get("versionState") == "DRAFT":
        log(f"WARNING: {persistent_id} already had a draft before this upload; publishing that existing draft, "
            f"including any other changes in it")
    version = client.publish(persistent_id)
    log(f"Published {persistent_id} as version {version}")
    return ("unchanged" if outcome == "pending" else outcome), version


def published_files(client, persistent_id, log=print):
    """The files of the dataset's latest published version, or [] if it was never published. Logs it when there is
    also an unpublished draft (files there are imported once it is published)."""
    dataset = client.dataset(persistent_id)
    latest = dataset.get("latestVersion") or {}
    if latest.get("versionState") == "RELEASED":
        return latest.get("files") or []
    if latest.get("versionState") == "DRAFT":
        names = [(f.get("dataFile") or {}).get("filename") for f in latest.get("files") or []]
        log(f"WARNING: {persistent_id} has an unpublished draft ({len(names)} files). Files are imported only once "
            f"the dataset is published: publish the draft on Borealis.")
    published = client.published_version(persistent_id)
    if published is None:
        log(f"WARNING: {persistent_id} has never been published, so there is nothing to import yet")
        return []
    return published.get("files") or []
