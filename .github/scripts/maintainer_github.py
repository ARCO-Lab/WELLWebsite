"""A small GitHub/HTTP client for the daily maintainer's scripts (maintainer_inputs.py, maintainer_summary.py,
maintainer_publish.py), and the cleaning of text the model wrote before a person reads it. Standard library only, so
the workflow needs no pip install. The transport is a function argument, so the unit tests run without a network."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from sentry_issues import scrub

USER_AGENT = "well-daily-maintainer"
# A "#" before a number links an issue, and "Fixes #12" in a pull request body closes it when the PR is merged
ISSUE_REF_RE = re.compile(r"#(?=\d)")


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


def is_maintainer_pr(pr, repo, login):
    """Whether a pull request is the maintainer's own: from a maint/* branch of this repository, opened by its
    account. All three are needed: with a personal token the account is the owner's own, who opens other pull
    requests too, so the maint/* branch is what tells the maintainer's apart. A label alone never counts."""
    head = pr.get("head") or {}
    return (bool(login) and (head.get("ref") or "").startswith("maint/")
            and (pr.get("user") or {}).get("login") == login
            and (head.get("repo") or {}).get("full_name") == repo)


# The publish job comments on each pull request it pushes to, with the commit it pushed in this hidden line, and the
# summary compares it with the pull request's head: a commit someone else added since then makes it "Needs your
# review". Only an unedited comment by the maintainer's own account counts (anyone with write access can edit a
# comment, but that changes its updated_at).
PUBLISHED_MARKER = "<!-- maintainer-published: {} -->"
PUBLISHED_RE = re.compile(r"<!-- maintainer-published: ([0-9a-f]{40}(?:[0-9a-f]{24})?) -->")


def published_comment(sha):
    return (f"The daily maintainer pushed commit {sha} to this branch. A commit added after it means this pull "
            f"request needs a person's review in the maintainer's email.\n\n{PUBLISHED_MARKER.format(sha)}")


def published_commit(comments, login):
    """The commit in the newest unedited publish comment by `login` (comments oldest first), or None."""
    found = None
    for comment in comments or []:
        if not login or (comment.get("user") or {}).get("login") != login:
            continue
        if comment.get("updated_at") != comment.get("created_at"):
            continue
        match = PUBLISHED_RE.search(comment.get("body") or "")
        if match:
            found = match.group(1)
    return found


def clip(text, limit):
    """Text cut to `limit` characters, marked when cut."""
    text = text or ""
    return text if len(text) <= limit else text[:limit] + " [...]"


def model_lines(text, line_limit=2000, max_lines=400):
    """Free text the model wrote (its summary, a pull request body), as lines that are safe to show where a person
    trusts what they read: a fooled run could otherwise slip in a convincing link, notify everyone with @mentions or
    close an issue with "Fixes #n". Each line goes through sentry_issues.scrub(), the same cleaning as Sentry text in
    public issues (no invisible characters, e-mail or IP addresses, query strings or credentials; backticks and angle
    brackets replaced, so the text can't end a code block or open a tag; @ followed by a zero-width space, so no one
    is notified), and the same zero-width space goes after a # before a number. Line breaks are kept."""
    lines = str(text or "").splitlines()[:max_lines]
    return [ISSUE_REF_RE.sub("#​", scrub(line, line_limit)) for line in lines]


def fenced(text, **limits):
    """model_lines() as a markdown code block, so none of it renders as a link, a mention or markup."""
    return "```text\n" + "\n".join(model_lines(text, **limits)) + "\n```"

