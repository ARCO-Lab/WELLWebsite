"""A small GitHub/HTTP client for the daily maintainer's scripts (maintainer_inputs.py, maintainer_summary.py).
Standard library only, so the workflow needs no pip install. The transport is a function argument, so the unit
tests run without a network."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "well-daily-maintainer"


class HttpError(Exception):
    def __init__(self, status, url, message=""):
        super().__init__(f"HTTP {status} from {redact_url(url)}{': ' + message if message else ''}")
        self.status = status


def redact_url(url):
    """The URL without its query string, so a token passed as a parameter never reaches an error message."""
    return url.split("?", 1)[0]


def urllib_transport(method, url, headers, body):
    """Send one request; return (status, headers dict, body bytes). Errors with a status come back as a status."""
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers or {}), error.read() or b""


def next_link(headers):
    """The rel="next" URL of a paginated response, or None."""
    link = headers.get("Link") or headers.get("link") or ""
    match = re.search(r'<([^>]+)>;\s*rel="next"', link)
    return match.group(1) if match else None


def error_message(raw):
    """The "message" of a JSON error body (GitHub and Sentry both send one), or "" when the body has none."""
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        return ""   # an HTML error page, say: the status alone says enough
    return str(data.get("message", ""))[:200] if isinstance(data, dict) else ""


class Client:
    def __init__(self, base_url, token, transport=urllib_transport, auth_scheme="Bearer"):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.transport = transport
        self.auth_scheme = auth_scheme

    def _headers(self, extra=None):
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if "api.github.com" in self.base_url or "/api/v3" in self.base_url:
            headers["Accept"] = "application/vnd.github+json"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
        if self.token:
            headers["Authorization"] = f"{self.auth_scheme} {self.token}"
        headers.update(extra or {})
        return headers

    def url(self, path, params=None):
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        return url

    def request(self, method, path, params=None, payload=None):
        """(data, headers) of a JSON request. Raises HttpError on any status of 400 or more."""
        url = self.url(path, params)
        body = json.dumps(payload).encode() if payload is not None else None
        headers = self._headers({"Content-Type": "application/json"} if body else None)
        status, response_headers, raw = self.transport(method, url, headers, body)
        if status >= 400:
            raise HttpError(status, url, error_message(raw))
        return (json.loads(raw) if raw else None), response_headers

    def get(self, path, params=None):
        return self.request("GET", path, params)[0]

    def get_all(self, path, params=None, max_pages=10, key=None):
        """Every item of a paginated list (following Link: rel="next"), up to max_pages pages.
        `key` names the list inside an object response (e.g. "workflow_runs")."""
        items, url, page = [], self.url(path, params), 0
        while url and page < max_pages:
            data, headers = self.request("GET", url)
            items.extend((data or {}).get(key, []) if key else (data or []))
            url, page = next_link(headers), page + 1
        return items

    def graphql(self, query, variables=None):
        data = self.request("POST", "graphql", payload={"query": query, "variables": variables or {}})[0] or {}
        if data.get("errors"):
            raise RuntimeError("GraphQL: " + "; ".join(str(e.get("message", e))[:200] for e in data["errors"]))
        return data.get("data") or {}


def github_client(token, transport=urllib_transport):
    return Client(os.environ.get("GITHUB_API_URL") or "https://api.github.com", token, transport)


def clip(text, limit):
    """Text cut to `limit` characters, marked when cut."""
    text = text or ""
    return text if len(text) <= limit else text[:limit] + " [...]"
