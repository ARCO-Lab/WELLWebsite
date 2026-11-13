"""welldash²'s login: one shared password, a signed session cookie, CSRF tokens and a failed-login limit.

- The password is checked against OPS_PASSWORD_HASH with werkzeug's check_password_hash (a constant-time
  comparison of the derived key). The limit and the form's CSRF token are checked first, so a client can't make the
  one worker compute scrypt any faster than the limit allows.
- The session is Flask's signed cookie (OPS_SECRET_KEY): HttpOnly, SameSite=Strict, and Secure over HTTPS or when
  OPS_COOKIE_SECURE=1 (ops/app.py). A login lasts 8 hours from when it happened (not from the last click), and ends
  sooner if the password is changed, since the session holds a fingerprint of the hash it was made with.
- Each login also gets a random session id that the server keeps (SessionStore). Sign out removes it, so a copy of
  the cookie stops working too; a restart of the service forgets them all and signs everyone out.
- Failed logins, counted per client address in 15-minute windows: after 5, that address is refused until its
  oldest failure is 15 minutes old. When 50 or more have failed from all addresses together, each address with a
  failure must also wait a minute between tries. Nobody is ever refused for others' failures, so many machines
  guessing can't lock the owner out. Every attempt counts as a failure until the password is found right, so
  parallel requests can't get past the limit, and a bad CSRF token counts too.
- In memory, so the service runs one gunicorn worker (several threads).
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
SLOWDOWN_AFTER_TOTAL = 50     # failures from all addresses together in the window
SLOWDOWN_GAP_S = 60           # then the wait after an address's last failure before it may try again
SWEEP_EVERY_S = 60            # how often addresses with no failures left in the window are forgotten
PUBLIC_ENDPOINTS = {"login", "static"}

REFUSED = {
    "client": "Too many failed attempts. Try again in 15 minutes.",
    "slowdown": "Many failed sign-ins recently. Wait a minute before trying again.",
}


class LoginLimiter:
    """Failed login attempts in the last window_s seconds, per client address and in total."""

    def __init__(self, per_client=MAX_FAILURES_PER_CLIENT, slowdown_after=SLOWDOWN_AFTER_TOTAL,
                 slowdown_gap_s=SLOWDOWN_GAP_S, window_s=FAILURE_WINDOW_S, clock=time.monotonic):
        self.per_client, self.slowdown_after, self.slowdown_gap_s = per_client, slowdown_after, slowdown_gap_s
        self.window_s, self.clock = window_s, clock
        self.lock = threading.Lock()
        self.by_client = {}
        self.all = deque()
        self.last_sweep = clock()

    def _trim(self, times, now):
        while times and now - times[0] >= self.window_s:
            times.popleft()

    def _sweep(self, now):
        # Without it, every address that failed once would stay in memory until it came back.
        if now - self.last_sweep < SWEEP_EVERY_S:
            return
        self.last_sweep = now
        for client in [c for c, times in self.by_client.items() if not times or now - times[-1] >= self.window_s]:
            del self.by_client[client]

    def attempt(self, client):
        """Called before the password is checked. None, after counting this attempt as a failure until
        succeeded() says otherwise; or why it is refused ("client" or "slowdown", keys of REFUSED), uncounted."""
        now = self.clock()
        with self.lock:
            self._trim(self.all, now)
            self._sweep(now)
            mine = self.by_client.get(client)
            if mine is not None:
                self._trim(mine, now)
                if len(mine) >= self.per_client:
                    return "client"
                if mine and len(self.all) >= self.slowdown_after and now - mine[-1] < self.slowdown_gap_s:
                    return "slowdown"
            self.by_client.setdefault(client, deque()).append(now)
            self.all.append(now)
            return None

    def succeeded(self, client):
        """The right password: forget this address's failures, and take the attempt just counted off the total."""
        with self.lock:
            mine = self.by_client.pop(client, None)
            if mine:
                try:
                    self.all.remove(mine[-1])
                except ValueError:   # already trimmed out of the window
                    pass


class SessionStore:
    """The ids of sessions that are signed in, in memory (one worker). Sign out removes the id, so the cookie it
    was in stops working everywhere, not just in the browser that signed out."""

    def __init__(self, lifetime_s=SESSION_LIFETIME.total_seconds(), clock=time.time):
        self.lifetime_s, self.clock = lifetime_s, clock
        self.lock = threading.Lock()
        self.started = {}   # session id -> when it signed in

    def start(self):
        sid = secrets.token_urlsafe(24)
        now = self.clock()
        with self.lock:
            for old in [s for s, at in self.started.items() if now - at >= self.lifetime_s]:
                del self.started[old]
            self.started[sid] = now
        return sid

    def alive(self, sid):
        if not isinstance(sid, str):
            return False
        with self.lock:
            started = self.started.get(sid)
        return started is not None and self.clock() - started < self.lifetime_s

    def end(self, sid):
        with self.lock:
            self.started.pop(sid, None)


def csrf_token():
    """This session's CSRF token, created on first use and kept until the session is cleared."""
    token = session.get("csrf")
    if not token:
        token = session["csrf"] = secrets.token_urlsafe(32)
    return token


def csrf_ok():
    sent, expected = request.form.get("csrf_token", ""), session.get("csrf", "")
    return bool(expected) and hmac.compare_digest(sent.encode(), expected.encode())


def logged_in(settings, sessions, now=None):
    """Whether the session holds a login under SESSION_LIFETIME old, made with the current password hash, that
    hasn't signed out."""
    auth = session.get("auth")
    if not isinstance(auth, dict):
        return False
    now = time.time() if now is None else now
    started = auth.get("at")
    if not isinstance(started, (int, float)) or not 0 <= now - started < SESSION_LIFETIME.total_seconds():
        return False
    if not hmac.compare_digest(str(auth.get("v", "")), settings.password_version):
        return False
    return sessions.alive(auth.get("sid"))


def install_auth(app, settings, limiter=None, sessions=None):
    """Adds the login check before every request, the /login and /logout routes and the template's CSRF token.
    Returns the limiter (tests pass their own); the session store is app.extensions["ops_sessions"]."""
    limiter = limiter or LoginLimiter()
    sessions = sessions or SessionStore()
    app.extensions["ops_login_limiter"] = limiter
    app.extensions["ops_sessions"] = sessions

    @app.before_request
    def require_login():
        if request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if request.endpoint == "logout" or logged_in(settings, sessions):
            return None
        session.pop("auth", None)
        if request.method in ("GET", "HEAD"):
            return redirect(url_for("login"))
        abort(401)
        return None   # not reached: abort raises

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            if logged_in(settings, sessions):
                return redirect(url_for("overview"))
            return render_template("login.html", csrf_token=csrf_token(), error=None)
        client = request.remote_addr or "unknown"   # the direct peer: welldash² is never behind a proxy
        refused = limiter.attempt(client)
        if refused:
            log.warning("login refused: %s limit (client %s)", refused, client)
            return render_template("login.html", csrf_token=csrf_token(), error=REFUSED[refused]), 429
        if not csrf_ok():
            log.warning("login failed: bad CSRF token (client %s)", client)
            return render_template("login.html", csrf_token=csrf_token(),
                                   error="The form expired. Please try again."), 400
        if not check_password_hash(settings.password_hash, request.form.get("password", "")):
            log.warning("login failed (client %s)", client)
            return render_template("login.html", csrf_token=csrf_token(), error="Wrong password."), 401
        limiter.succeeded(client)
        session.clear()   # a fresh session (and CSRF token) on every login
        session.permanent = True
        session["auth"] = {"at": time.time(), "v": settings.password_version, "sid": sessions.start()}
        csrf_token()
        log.info("login (client %s)", client)
        return redirect(url_for("overview"))

    @app.route("/logout", methods=["POST"])
    def logout():
        if not csrf_ok():
            abort(400)
        auth = session.get("auth")
        if isinstance(auth, dict):
            sessions.end(auth.get("sid"))   # the cookie is dead even if a copy of it was kept
        session.clear()
        return redirect(url_for("login"))

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": csrf_token()}

    return limiter
