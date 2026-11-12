"""welldash²'s login: one shared password, a signed session cookie, CSRF tokens and a failed-login limit.

- The password is checked against OPS_PASSWORD_HASH with werkzeug's check_password_hash (a constant-time
  comparison of the derived key). It is checked even when the form's CSRF token is wrong, so the time taken
  doesn't tell an attacker which part failed.
- The session is Flask's signed cookie (OPS_SECRET_KEY): HttpOnly, SameSite=Strict, Secure when OPS_COOKIE_SECURE=1.
  A login lasts 8 hours from when it happened (not from the last click), and ends sooner if the password is
  changed, since the session holds a fingerprint of the hash it was made with.
- Failed logins: at most 5 per client address in 15 minutes, and 50 from all addresses together, after which
  login answers 429 until the window passes. In memory, so the service runs one gunicorn worker (several threads).
- Every page needs the session except /login and /static; only /login and /logout accept POST.
"""
import hmac
import logging
import secrets
import threading
import time
from collections import deque

from flask import abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from ops.settings import SESSION_LIFETIME

log = logging.getLogger("ops.auth")

FAILURE_WINDOW_S = 15 * 60
MAX_FAILURES_PER_CLIENT = 5
MAX_FAILURES_TOTAL = 50
PUBLIC_ENDPOINTS = {"login", "static"}


class LoginLimiter:
    """Failed login attempts in the last FAILURE_WINDOW_S seconds, per client address and in total."""

    def __init__(self, per_client=MAX_FAILURES_PER_CLIENT, total=MAX_FAILURES_TOTAL, window_s=FAILURE_WINDOW_S,
                 clock=time.monotonic):
        self.per_client, self.total, self.window_s, self.clock = per_client, total, window_s, clock
        self.lock = threading.Lock()
        self.by_client = {}
        self.all = deque()

    def _trim(self, times, now):
        while times and now - times[0] >= self.window_s:
            times.popleft()

    def blocked(self, client):
        """Whether login is refused for this client: too many failures from it, or from everyone together."""
        now = self.clock()
        with self.lock:
            self._trim(self.all, now)
            mine = self.by_client.get(client)
            if mine is not None:
                self._trim(mine, now)
                if not mine:
                    del self.by_client[client]
            return len(self.all) >= self.total or (mine is not None and len(mine) >= self.per_client)

    def failed(self, client):
        now = self.clock()
        with self.lock:
            self.by_client.setdefault(client, deque()).append(now)
            self.all.append(now)

    def succeeded(self, client):
        with self.lock:
            self.by_client.pop(client, None)


def csrf_token():
    """This session's CSRF token, created on first use and kept until the session is cleared."""
    token = session.get("csrf")
    if not token:
        token = session["csrf"] = secrets.token_urlsafe(32)
    return token


def csrf_ok():
    sent, expected = request.form.get("csrf_token", ""), session.get("csrf", "")
    return bool(expected) and hmac.compare_digest(sent.encode(), expected.encode())


def logged_in(settings, now=None):
    """Whether the session holds a login under SESSION_LIFETIME old, made with the current password hash."""
    auth = session.get("auth")
    if not isinstance(auth, dict):
        return False
    now = time.time() if now is None else now
    started = auth.get("at")
    if not isinstance(started, (int, float)) or not 0 <= now - started < SESSION_LIFETIME.total_seconds():
        return False
    return hmac.compare_digest(str(auth.get("v", "")), settings.password_version)


def install_auth(app, settings, limiter=None):
    """Adds the login check before every request, the /login and /logout routes and the template's CSRF token.
    Returns the limiter (tests pass their own)."""
    limiter = limiter or LoginLimiter()
    app.extensions["ops_login_limiter"] = limiter

    @app.before_request
    def require_login():
        if request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if request.endpoint == "logout" or logged_in(settings):
            return None
        session.pop("auth", None)
        if request.method in ("GET", "HEAD"):
            return redirect(url_for("login"))
        abort(401)
        return None   # not reached: abort raises

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            if logged_in(settings):
                return redirect(url_for("overview"))
            return render_template("login.html", csrf_token=csrf_token(), error=None)
        client = request.remote_addr or "unknown"   # the direct peer: welldash² is never behind a proxy
        if limiter.blocked(client):
            log.warning("login refused: too many failed attempts (client %s)", client)
            return render_template("login.html", csrf_token=csrf_token(),
                                   error="Too many failed attempts. Try again in 15 minutes."), 429
        form_ok = csrf_ok()
        password_ok = check_password_hash(settings.password_hash, request.form.get("password", ""))
        if not form_ok:
            return render_template("login.html", csrf_token=csrf_token(),
                                   error="The form expired. Please try again."), 400
        if not password_ok:
            limiter.failed(client)
            log.warning("login failed (client %s)", client)
            return render_template("login.html", csrf_token=csrf_token(), error="Wrong password."), 401
        limiter.succeeded(client)
        session.clear()   # a fresh session (and CSRF token) on every login
        session.permanent = True
        session["auth"] = {"at": time.time(), "v": settings.password_version}
        csrf_token()
        log.info("login (client %s)", client)
        return redirect(url_for("overview"))

    @app.route("/logout", methods=["POST"])
    def logout():
        if not csrf_ok():
            abort(400)
        session.clear()
        return redirect(url_for("login"))

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": csrf_token()}

    return limiter
