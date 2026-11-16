"""Uploads to a SharePoint document library through Microsoft Graph, for the sensor and sampling CSVs
(scripts/sharepoint_upload.py). Needs only requests.

It signs in as an app (client credentials: an Entra ID app registration with the Graph application permission
Sites.Selected, and a write grant on the one site), so no person's password or MFA is involved.

Settings (dashboard/backend/app/.env on the VM). The upload is off while none of the first four is set:
  SHAREPOINT_TENANT_ID      the Entra ID tenant (directory) id
  SHAREPOINT_CLIENT_ID      the app registration's application (client) id
  SHAREPOINT_CLIENT_SECRET  a client secret of that app (it expires: IT sets the date, often 6-24 months)
  SHAREPOINT_SITE           the site, e.g. https://mcmaster.sharepoint.com/sites/WELL
  SHAREPOINT_LIBRARY        the document library (default "Documents", which SharePoint shows as Documents or
                            Shared Documents)
  SHAREPOINT_FOLDER         the folder in it (default "WELL sensor data", or the library root with
                            SHAREPOINT_LAYOUT=cadence)
  SHAREPOINT_LAYOUT         unset (or "year"): monthly sensor files in <folder>/<year>/.
                            "cadence": in <folder>,
                              West Campus/Daily/<year>/<MM>/WELLWestCampus_2026-11-14.csv
                              West Campus/Weekly/<ISO year>/WELLWestCampus_2026-W46.csv
                              West Campus/Monthly/<year>/WELLWestCampus_Oct2026.csv
                              Ancaster Watershed/<year>/WELLAncasterWatershed_Oct2026.csv (creek sampling)
  SHAREPOINT_CADENCES       with the cadence layout, which of daily, weekly, monthly and sampling to upload,
                            comma-separated (default all four)
  SHAREPOINT_SENSOR_FOLDER, SHAREPOINT_SAMPLING_FOLDER
                            with the cadence layout, the names of those two folders (default "West Campus" and
                            "Ancaster Watershed")

The client secret and the access token are never logged.
"""
import base64
import os
import time
from urllib.parse import quote, urlsplit

import requests

GRAPH = "https://graph.microsoft.com/v1.0"
LOGIN = "https://login.microsoftonline.com"
TIMEOUT = (10, 120)
# Upload sessions take chunks in multiples of 320 KiB; Graph recommends 5-10 MiB.
CHUNK = 320 * 1024 * 16
RETRIES = 4            # for 429 (throttled) and 503/504, waiting as Graph's Retry-After says
MAX_RETRY_WAIT_S = 60

REQUIRED = ("SHAREPOINT_TENANT_ID", "SHAREPOINT_CLIENT_ID", "SHAREPOINT_CLIENT_SECRET", "SHAREPOINT_SITE")
DEFAULT_LIBRARY = "Documents"
DEFAULT_FOLDER = "WELL sensor data"
LAYOUTS = ("year", "cadence")
CADENCE_FOLDERS = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}
# What the cadence layout can upload, in the order the scheduler runs them: the sensor periods, then the sampling
# months
UPLOADS = (*CADENCE_FOLDERS, "sampling")
DEFAULT_SENSOR_FOLDER = "West Campus"
DEFAULT_SAMPLING_FOLDER = "Ancaster Watershed"


class SharePointError(Exception):
    """A Graph or sign-in call failed. The message says what to do; it never holds the secret or the token."""

    def __init__(self, action, status=None, message=""):
        self.action, self.status = action, status
        hint = {
            400: "",
            401: "the app's sign-in was refused: check SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID and "
                 "SHAREPOINT_CLIENT_SECRET (a client secret expires; ask IT for a new one)",
            403: "the app isn't allowed on this site: IT must grant it write access to the site (Sites.Selected, "
                 "role write), and an admin must have consented to Sites.Selected",
            404: "not found: check SHAREPOINT_SITE, SHAREPOINT_LIBRARY and SHAREPOINT_FOLDER",
        }.get(status, "")
        text = f"{action} failed" + (f" (HTTP {status})" if status else "")
        super().__init__(". ".join(p for p in (text, message and f"Microsoft says: {message[:300]}", hint) if p))


def settings(env=None):
    """The SharePoint settings from the environment, with defaults filled in."""
    env = os.environ if env is None else env
    get = lambda name, default="": (env.get(name) or "").strip() or default  # noqa: E731
    layout = get("SHAREPOINT_LAYOUT", "year").lower()
    return {
        "tenant": get("SHAREPOINT_TENANT_ID"),
        "client_id": get("SHAREPOINT_CLIENT_ID"),
        "secret": get("SHAREPOINT_CLIENT_SECRET"),
        "site": get("SHAREPOINT_SITE"),
        "library": get("SHAREPOINT_LIBRARY", DEFAULT_LIBRARY),
        "folder": get("SHAREPOINT_FOLDER", "" if layout == "cadence" else DEFAULT_FOLDER).strip("/"),
        "layout": layout,
        "cadences": get("SHAREPOINT_CADENCES").lower(),
        "sensor_folder": get("SHAREPOINT_SENSOR_FOLDER", DEFAULT_SENSOR_FOLDER).strip("/"),
        "sampling_folder": get("SHAREPOINT_SAMPLING_FOLDER", DEFAULT_SAMPLING_FOLDER).strip("/"),
    }


def cadences(config):
    """What to upload ("daily", "weekly", "monthly", "sampling", in that order) for `config` (settings()). The year
    layout has monthly sensor files only. ValueError naming the setting when SHAREPOINT_LAYOUT or SHAREPOINT_CADENCES
    isn't valid."""
    if config["layout"] not in LAYOUTS:
        raise ValueError(f"SHAREPOINT_LAYOUT must be cadence or year (or unset), got {config['layout']!r}")
    names = [name.strip() for name in config["cadences"].split(",") if name.strip()]
    unknown = [name for name in names if name not in UPLOADS]
    if unknown:
        raise ValueError(f"SHAREPOINT_CADENCES lists {', '.join(unknown)}; use daily, weekly, monthly and/or "
                         f"sampling")
    if config["layout"] != "cadence":
        if set(names) - {"monthly"}:
            raise ValueError("SHAREPOINT_CADENCES needs SHAREPOINT_LAYOUT=cadence: the year layout has monthly "
                             "files only")
        return ["monthly"]
    return [name for name in UPLOADS if not names or name in names]


def period_folder(config, period):
    """The folder (from the library root) for the sensor file of `period` (a utils.periods.Period)."""
    year = str(period.start.year)
    if config["layout"] != "cadence":
        if period.cadence != "monthly":
            raise ValueError(f"{period.cadence} files need SHAREPOINT_LAYOUT=cadence")
        parts = [config["folder"], year]
    elif period.cadence == "daily":
        parts = [config["folder"], config["sensor_folder"], CADENCE_FOLDERS["daily"], year,
                 f"{period.start.month:02d}"]
    elif period.cadence == "weekly":   # the ISO year, which for a week around New Year isn't always its Monday's
        parts = [config["folder"], config["sensor_folder"], CADENCE_FOLDERS["weekly"], period.key[:4]]
    else:
        parts = [config["folder"], config["sensor_folder"], CADENCE_FOLDERS["monthly"], year]
    return "/".join(part for part in parts if part)


def sampling_folder(config, year):
    """The folder (from the library root) for the sampling files of `year`; only the cadence layout has one."""
    if config["layout"] != "cadence":
        raise ValueError("sampling files need SHAREPOINT_LAYOUT=cadence")
    return "/".join(part for part in (config["folder"], config["sampling_folder"], str(year)) if part)


def status(env=None):
    """("off", []) when no SharePoint setting is set, ("on", []) when all are, else ("incomplete", missing names)."""
    env = os.environ if env is None else env
    missing = [name for name in REQUIRED if not (env.get(name) or "").strip()]
    if len(missing) == len(REQUIRED):
        return "off", []
    return ("incomplete", missing) if missing else ("on", [])


def site_path(site):
    """Graph's address for a site: https://contoso.sharepoint.com/sites/WELL -> contoso.sharepoint.com:/sites/WELL.
    Also accepts that form as is, or a site id."""
    site = site.strip().rstrip("/")
    if "://" in site:
        parts = urlsplit(site)
        return f"{parts.netloc}:{parts.path}" if parts.path else parts.netloc
    return site


def quick_xor_hash(content):
    """Microsoft's QuickXorHash of `content` (bytes), base64, as Graph reports it in file.hashes.quickXorHash.

    Each byte is XORed into a 160-bit value at bit (index * 11) mod 160, wrapping around, then the length is XORed
    into the top 64 bits."""
    width, shift, mask = 160, 11, (1 << 160) - 1
    value = 0
    for i, byte in enumerate(content):
        bits = byte << ((i * shift) % width)
        value ^= (bits & mask) | (bits >> width)
    value ^= len(content) << (width - 64)
    return base64.b64encode(value.to_bytes(width // 8, "little")).decode()


class SharePoint:
    """One SharePoint site's library, through Graph. `session` and `sleep` are replaceable in tests."""

    def __init__(self, config, session=None, sleep=time.sleep):
        self.config = config
        self.session = session or requests.Session()
        self.sleep = sleep
        self._token = None
        self._drive = None

    # ---- plumbing

    def token(self):
        if self._token:
            return self._token
        c = self.config
        try:
            response = self.session.request(
                "POST", f"{LOGIN}/{quote(c['tenant'])}/oauth2/v2.0/token", timeout=TIMEOUT,
                data={"client_id": c["client_id"], "client_secret": c["secret"], "grant_type": "client_credentials",
                      "scope": "https://graph.microsoft.com/.default"})
        except requests.exceptions.RequestException as e:
            raise SharePointError("Signing in to Microsoft", None, f"no answer ({type(e).__name__})") from None
        if response.status_code != 200:
            # error_description starts with an AADSTS code, e.g. AADSTS7000215 (wrong secret); keep its first line
            body = safe_json(response)
            message = (body.get("error_description") or body.get("error") or "").splitlines()[0:1]
            text = message[0] if message else ""
            if c["secret"]:
                text = text.replace(c["secret"], "[secret]")   # never echoed today; kept out of logs regardless
            raise SharePointError("Signing in to Microsoft", 401 if response.status_code in (400, 401) else
                                  response.status_code, text)
        self._token = safe_json(response).get("access_token")
        if not self._token:
            raise SharePointError("Signing in to Microsoft", None, "no access token in the answer")
        return self._token

    def call(self, method, path, action, ok=(200,), allow=(), auth=True, **kwargs):
        """The parsed JSON of a Graph call (path relative to GRAPH, or a full URL). Retries throttling; raises
        SharePointError for a status not in `ok`, except one in `allow`, which returns None."""
        url = path if path.startswith("https://") else f"{GRAPH}/{path}"
        headers = kwargs.pop("headers", {})
        if auth:
            headers["Authorization"] = f"Bearer {self.token()}"
        for attempt in range(RETRIES + 1):
            try:
                response = self.session.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
            except requests.exceptions.RequestException as e:
                raise SharePointError(action, None, f"no answer ({type(e).__name__})") from None
            if response.status_code in (429, 503, 504) and attempt < RETRIES:
                self.sleep(retry_wait(response, attempt))
                continue
            break
        if response.status_code in allow:
            return None
        if response.status_code not in ok:
            error = safe_json(response).get("error") or {}
            raise SharePointError(action, response.status_code,
                                  error.get("message", "") if isinstance(error, dict) else str(error))
        return safe_json(response) if response.content else {}

    # ---- the site, library and folders

    def site(self):
        return self.call("GET", f"sites/{site_path(self.config['site'])}", f"Finding the site {self.config['site']}")

    def drive(self):
        """The id of the document library SHAREPOINT_LIBRARY."""
        if self._drive:
            return self._drive
        site = self.site()
        drives = self.call("GET", f"sites/{site['id']}/drives", "Listing the site's document libraries")
        wanted = self.config["library"].lower()
        names = []
        for drive in drives.get("value") or []:
            names.append(drive.get("name"))
            web_url = (drive.get("webUrl") or "").rstrip("/").rsplit("/", 1)[-1]
            if wanted in ((drive.get("name") or "").lower(), web_url.lower().replace("%20", " ")):
                self._drive = drive["id"]
                return self._drive
        raise SharePointError(f"Finding the library {self.config['library']}", 404,
                              f"the site's libraries are: {', '.join(n for n in names if n) or 'none'}")

    def item(self, path):
        """The drive item at `path` (relative to the library root), or None."""
        return self.call("GET", f"drives/{self.drive()}/root:/{quote(path)}", f"Looking up {path}", allow=(404,))

    def ensure_folder(self, path):
        """Create the folder `path` and any missing parents."""
        parent = ""
        for name in [p for p in path.split("/") if p]:
            here = f"{parent}/{name}" if parent else name
            if self.item(here) is None:
                where = f"drives/{self.drive()}/root:/{quote(parent)}:/children" if parent else \
                    f"drives/{self.drive()}/root/children"
                self.call("POST", where, f"Creating the folder {here}", ok=(200, 201), allow=(409,),
                          json={"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"})
            parent = here

    # ---- uploading

    def upload(self, path, content):
        """Upload `content` (bytes) to `path`, replacing any file there (SharePoint keeps the old one as a version),
        through an upload session in chunks. Returns the new drive item."""
        if not content:
            raise SharePointError(f"Uploading {path}", None, "the file is empty")
        session = self.call("POST", f"drives/{self.drive()}/root:/{quote(path)}:/createUploadSession",
                            f"Starting the upload of {path}",
                            json={"item": {"@microsoft.graph.conflictBehavior": "replace"}})
        upload_url = session["uploadUrl"]
        total = len(content)
        start, item = 0, None
        try:
            while start < total:
                chunk = content[start:start + CHUNK]
                end = start + len(chunk) - 1
                # The upload URL carries its own authorization; Graph refuses a request that also sends the token
                item = self.call("PUT", upload_url, f"Uploading {path} (bytes {start}-{end})", ok=(200, 201, 202),
                                 auth=False, data=chunk, headers={"Content-Range": f"bytes {start}-{end}/{total}"})
                start += len(chunk)
        except SharePointError:
            try:   # don't leave a half-finished session behind
                self.call("DELETE", upload_url, "Cancelling the upload session", ok=(204,), auth=False)
            except SharePointError:
                pass   # an abandoned session expires by itself; report the upload's own error below
            raise
        if not item or "id" not in item:
            raise SharePointError(f"Uploading {path}", None, "the last chunk didn't return the file")
        if item.get("size") not in (None, total):
            raise SharePointError(f"Uploading {path}", None, f"stored {item.get('size')} bytes, sent {total}")
        return item


def retry_wait(response, attempt):
    # Seconds to wait before retrying a throttled (429) or unavailable (503/504) call: Graph's Retry-After if given,
    # else an exponential backoff; at least 1 s and at most MAX_RETRY_WAIT_S (60 s).
    try:
        wait = float(response.headers.get("Retry-After", ""))
    except (TypeError, ValueError):
        wait = 2 ** attempt * 5
    return max(1, min(wait, MAX_RETRY_WAIT_S))


def safe_json(response):
    try:
        body = response.json()
        return body if isinstance(body, dict) else {}
    except ValueError:
        return {}


def upload_month_file(client, name, content, year, log=print):
    """Put `content` at <folder>/<year>/<name> in the library (the year layout), as put_file does."""
    return put_file(client, f"{client.config['folder']}/{year}".strip("/"), name, content, log)


def put_file(client, folder, name, content, log=print):
    """Put `content` (bytes or text) at <folder>/<name> in the library, creating the folders. Safe to run again: an
    identical file (same size and QuickXorHash) is left as it is, and a different one is replaced (the old copy stays
    in the file's version history). Returns ("added" | "replaced" | "unchanged", the file's web URL)."""
    content = content.encode("utf-8") if isinstance(content, str) else content
    path = f"{folder}/{name}" if folder else name
    existing = client.item(path)
    if existing and existing.get("size") == len(content) and \
            ((existing.get("file") or {}).get("hashes") or {}).get("quickXorHash") == quick_xor_hash(content):
        log(f"{path} is already in SharePoint with the same content; not uploading it again")
        return "unchanged", existing.get("webUrl")
    client.ensure_folder(folder)
    item = client.upload(path, content)
    outcome = "replaced" if existing else "added"
    log(f"{'Replaced' if existing else 'Added'} {path} in SharePoint ({len(content):,} bytes)")
    return outcome, item.get("webUrl")
