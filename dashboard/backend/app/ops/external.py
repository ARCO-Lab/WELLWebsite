"""welldash²'s optional outside sources: GitHub Actions (CI of main), Sentry, Healthchecks.io and GoatCounter.

Each is read with a read-only key from the environment (ops/settings.py) and skipped when that key is unset.
Answers are cached for 5 minutes (failures for 1), so opening pages doesn't spend the services' rate limits, and a
slow or failing service costs a page at most a few seconds. Errors are reported by type and HTTP status only:
never a URL, header or key.
"""
import re
import threading
import time
from datetime import date, timedelta

import requests

CACHE_TTL_S = 300
ERROR_TTL_S = 60
TIMEOUT = (4, 8)
GOATCOUNTER_CODE = re.compile(r"^[a-z0-9-]{1,64}$")

_cache = {}
_cache_lock = threading.Lock()


def cached(key, fetch, clock=time.monotonic):
    now = clock()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    try:
        value, ttl = fetch(), CACHE_TTL_S
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        value, ttl = {"error": f"HTTP {status}"}, ERROR_TTL_S
    except (requests.exceptions.RequestException, ValueError, KeyError, TypeError) as e:
        value, ttl = {"error": type(e).__name__}, ERROR_TTL_S
    with _cache_lock:
        _cache[key] = (now + ttl, value)
    return value


def clear_cache():
    with _cache_lock:
        _cache.clear()


def get_json(url, headers=None, params=None, get=None):
    response = (get or requests.get)(url, headers=headers or {}, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def github_ci(settings, get=None):
    """The newest run of each workflow on main: [{"name", "status", "conclusion", "sha", "created_at", "url"}]. Runs
    of Dependabot's own update jobs (event "dynamic", one name per update) aren't CI and are left out."""
    def fetch():
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        body = get_json(f"https://api.github.com/repos/{settings.github_repo}/actions/runs", headers,
                        {"branch": "main", "per_page": 30, "exclude_pull_requests": "true"}, get)
        newest = {}
        for run in body.get("workflow_runs") or []:
            if run.get("event") == "dynamic":
                continue
            name = str(run.get("name") or "?")
            if name not in newest:
                newest[name] = {"name": name, "status": run.get("status"), "conclusion": run.get("conclusion"),
                                "sha": str(run.get("head_sha") or "")[:7], "created_at": run.get("created_at"),
                                "url": run.get("html_url"), "event": run.get("event")}
        return {"runs": list(newest.values())[:8]}
    return cached(("github", settings.github_repo), fetch)


def sentry_issues(settings, get=None):
    """Unresolved Sentry issues seen in the last 24 h, most frequent first (at most 10)."""
    if not (settings.sentry_token and settings.sentry_org):
        return {"configured": False}

    def fetch():
        body = get_json(f"{settings.sentry_api_url}/api/0/organizations/{settings.sentry_org}/issues/",
                        {"Authorization": f"Bearer {settings.sentry_token}"},
                        {"query": "is:unresolved", "statsPeriod": "24h", "sort": "freq", "limit": 10}, get)
        issues = [{"title": str(i.get("title") or "?")[:140], "count": i.get("count"),
                   "project": (i.get("project") or {}).get("slug"), "level": i.get("level"),
                   "last_seen": i.get("lastSeen"), "url": i.get("permalink")} for i in body or []]
        return {"configured": True, "issues": issues}
    return cached(("sentry", settings.sentry_org), fetch)


def healthchecks(settings, get=None):
    """Every Healthchecks.io check of the project the key belongs to: name, status and last ping."""
    if not settings.healthchecks_key:
        return {"configured": False}

    def fetch():
        body = get_json(f"{settings.healthchecks_api_url}/api/v3/checks/", {"X-Api-Key": settings.healthchecks_key},
                        None, get)
        checks = [{"name": c.get("name") or c.get("slug") or "?", "status": c.get("status"),
                   "last_ping": c.get("last_ping"), "next_ping": c.get("next_ping")}
                  for c in body.get("checks") or []]
        return {"configured": True, "checks": sorted(checks, key=lambda c: (c["status"] == "up", c["name"]))}
    return cached(("healthchecks",), fetch)


def goatcounter(settings, today=None, get=None):
    """Visitor totals of the last 7 and 30 days and the most visited pages, from GoatCounter's API."""
    code = settings.goatcounter_code.lower()
    if not code:
        return {"configured": False}
    if not GOATCOUNTER_CODE.match(code):
        return {"configured": True, "error": "OPS_GOATCOUNTER_CODE must be the site code only, e.g. welldash"}
    site = f"https://{code}.goatcounter.com"
    if not settings.goatcounter_token:
        return {"configured": True, "site": site, "numbers": False}

    def fetch():
        end = (today or date.today()) + timedelta(days=1)
        headers = {"Authorization": f"Bearer {settings.goatcounter_token}", "Content-Type": "application/json"}
        totals = {}
        for days in (7, 30):
            params = {"start": (end - timedelta(days=days)).isoformat(), "end": end.isoformat()}
            totals[days] = get_json(f"{site}/api/v0/stats/total", headers, params, get).get("total")
        params = {"start": (end - timedelta(days=30)).isoformat(), "end": end.isoformat(), "limit": 10}
        hits = get_json(f"{site}/api/v0/stats/hits", headers, params, get).get("hits") or []
        pages = [{"path": str(h.get("path") or "?")[:120], "title": str(h.get("title") or "")[:120],
                  "count": h.get("count")} for h in hits]
        return {"configured": True, "site": site, "numbers": True, "week": totals[7], "month": totals[30],
                "pages": pages}
    return cached(("goatcounter", code), fetch)
