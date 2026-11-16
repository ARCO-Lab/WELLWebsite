"""welldash² (ops/): it refuses to start without its secrets or with OPS_BIND unset or every address, the login
(password, CSRF and the failed-login limit checked before the hash, no global lock-out, the cookie Secure over
HTTPS, 8-hour sessions, sign-out revoking the session on the server), that every page needs the session and only
login/logout accept POST, the uptime check, the password helper, and, with TEST_POSTGRES_URL set (as in CI), every
page rendered from empty and from populated tables, the probe's rows and the 90-day cleanup.
No network: the outside services are replaced by stubs.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import datetime as dt
import os
import pathlib
import sys
import time
import unittest.mock

import requests

mock = unittest.mock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
os.environ["DATABASE_URL"] = "sqlite://"  # this test process only; never a real database

from sqlalchemy import create_engine  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from config import Config  # noqa: E402

Config.SQLALCHEMY_DATABASE_URI = "sqlite://"   # another test module may have imported Config first

from ops import auth, external, hashpw, probe  # noqa: E402
from ops.app import create_app  # noqa: E402
from ops.settings import ConfigError, load_settings  # noqa: E402

UTC = dt.timezone.utc
PASSWORD = "correct horse battery staple"    # a test value only
HASH = generate_password_hash(PASSWORD, method="pbkdf2:sha256:1000")   # cheap to check, for speed
ENV = {"OPS_PASSWORD_HASH": HASH, "OPS_SECRET_KEY": "k" * 40, "OPS_DATABASE_URL": "sqlite://",
       "OPS_BIND": "127.0.0.1"}
STUBS = {"github_ci": {"runs": [{"name": "CI", "status": "completed", "conclusion": "success", "sha": "abc1234",
                                 "created_at": "2026-11-10T12:00:00Z", "url": "https://github.com/x", "event": "push"}]},
         "sentry_issues": {"configured": False}, "healthchecks": {"configured": False},
         "goatcounter": {"configured": False}}
PAGES = ["/", "/uptime", "/traffic", "/system", "/visitors"]


def stub_external():
    return mock.patch.multiple(external, **{name: mock.Mock(return_value=value) for name, value in STUBS.items()})


def make_app(env=None, engine=None):
    return create_app(env={**ENV, **(env or {})}, engine=engine or create_engine("sqlite://"), start_background=False)


def sign_in(client, settings, at=None):
    """A valid session without going through the form (the form itself is tested in LoginTests), with its id
    registered in the app's session store as a login would."""
    sid = client.application.extensions["ops_sessions"].start()
    with client.session_transaction() as s:
        s["auth"] = {"at": at if at is not None else time.time(), "v": settings.password_version, "sid": sid}
        s["csrf"] = "csrf-token"


class SettingsTests(unittest.TestCase):
    def test_refuses_to_start_without_its_secrets(self):
        for missing, message in (("OPS_PASSWORD_HASH", "OPS_PASSWORD_HASH is not set"),
                                 ("OPS_SECRET_KEY", "OPS_SECRET_KEY is not set")):
            env = {k: v for k, v in ENV.items() if k != missing}
            with self.assertRaises(ConfigError) as caught, self.assertLogs("ops", "CRITICAL"):
                create_app(env=env, engine=create_engine("sqlite://"), start_background=False)
            self.assertIn(message, str(caught.exception))

    def test_rejects_bad_values_without_echoing_them(self):
        for env, message in (({"OPS_SECRET_KEY": "short"}, "shorter than 32"),
                             ({"OPS_PASSWORD_HASH": "plaintext-password"}, "single quotes"),
                             # what compose leaves of an unquoted hash: the $salt and $hash read as empty variables
                             ({"OPS_PASSWORD_HASH": "scrypt:32768:8:1"}, "single quotes"),
                             ({"OPS_DATABASE_URL": "", "DATABASE_URL": ""}, "OPS_DATABASE_URL"),
                             ({"OPS_RETENTION_DAYS": "ninety"}, "OPS_RETENTION_DAYS")):
            with self.assertRaises(ConfigError) as caught:
                load_settings({**ENV, **env})
            self.assertIn(message, str(caught.exception))
            self.assertNotIn("plaintext-password", str(caught.exception))
            self.assertNotIn("short", str(caught.exception).replace("shorter", ""))

    def test_quoted_hash_and_defaults(self):
        s = load_settings({**ENV, "OPS_PASSWORD_HASH": f"'{HASH}'"})
        self.assertEqual(s.password_hash, HASH)
        self.assertFalse(s.cookie_secure)
        self.assertEqual((s.retention_days, s.probe_interval_s), (90, 60))
        self.assertTrue(load_settings({**ENV, "OPS_COOKIE_SECURE": "1"}).cookie_secure)

    def test_ops_bind_is_required_and_not_every_address(self):
        for bind in (None, "", "0.0.0.0", "::", "[::]"):
            env = {k: v for k, v in ENV.items() if k != "OPS_BIND"}
            if bind is not None:
                env["OPS_BIND"] = bind
            with self.assertRaises(ConfigError) as caught:
                load_settings(env)
            self.assertIn("OPS_BIND", str(caught.exception))
            with self.assertRaises(ConfigError), self.assertLogs("ops", "CRITICAL"):
                create_app(env=env, engine=create_engine("sqlite://"), start_background=False)
        with self.assertRaises(ConfigError) as caught:
            load_settings({**ENV, "OPS_BIND": "well.cas.mcmaster.ca"})   # Docker publishes on addresses only
        self.assertIn("must be an IP address", str(caught.exception))
        for bind in ("127.0.0.1", "130.113.68.63", "::1"):
            self.assertEqual(load_settings({**ENV, "OPS_BIND": bind}).bind, bind)
        # Every address only when that is said on purpose
        for bind in ("0.0.0.0", "::"):
            self.assertEqual(load_settings({**ENV, "OPS_BIND": bind, "OPS_ALLOW_ANY_ADDRESS": "1"}).bind, bind)
        with self.assertRaises(ConfigError):
            load_settings({**ENV, "OPS_BIND": "0.0.0.0", "OPS_ALLOW_ANY_ADDRESS": "0"})


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.client = self.app.test_client()

    def csrf(self, client=None):
        client = client or self.client
        client.get("/login")
        with client.session_transaction() as s:
            return s["csrf"]

    def login(self, password, csrf=None, ip="192.0.2.10", client=None):
        client = client or self.client
        return client.post("/login", data={"password": password, "csrf_token": csrf or self.csrf(client)},
                           environ_base={"REMOTE_ADDR": ip})

    def test_login_page_has_one_password_field_and_csrf(self):
        page = self.client.get("/login")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('type="password"', html)
        self.assertNotIn("username", html.lower())
        self.assertEqual(html.count("<input"), 2)   # the password and the hidden CSRF token
        self.assertIn('name="csrf_token"', html)

    def test_right_password_signs_in_and_cookie_is_locked_down(self):
        response = self.login(PASSWORD)
        self.assertEqual((response.status_code, response.headers["Location"]), (302, "/"))
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertNotIn("Secure", cookie)   # plain HTTP (an SSH tunnel) and OPS_COOKIE_SECURE unset
        with stub_external():
            self.assertEqual(self.client.get("/system").status_code, 200)
        secure = make_app({"OPS_COOKIE_SECURE": "1"}).test_client()
        self.assertIn("Secure", self.login(PASSWORD, client=secure).headers["Set-Cookie"])

    def test_cookie_is_secure_whenever_the_request_is_https(self):
        client = self.app.test_client()
        client.get("/login", base_url="https://localhost")
        with client.session_transaction(base_url="https://localhost") as s:
            token = s["csrf"]
        response = client.post("/login", base_url="https://localhost",
                               data={"password": PASSWORD, "csrf_token": token})
        self.assertEqual(response.status_code, 302)
        self.assertIn("Secure", response.headers["Set-Cookie"])
        self.assertNotIn("Secure", self.client.get("/login").headers["Set-Cookie"])   # the same app over HTTP

    def test_wrong_password_and_bad_csrf(self):
        self.assertEqual(self.login("wrong").status_code, 401)
        self.assertEqual(self.client.get("/").status_code, 302)
        response = self.login(PASSWORD, csrf="forged")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/").status_code, 302)
        missing = self.client.post("/login", data={"password": PASSWORD})
        self.assertEqual(missing.status_code, 400)
        fresh = make_app().test_client()   # no session at all, so no token to match
        self.assertEqual(fresh.post("/login", data={"password": PASSWORD, "csrf_token": ""}).status_code, 400)

    def test_password_is_hashed_only_after_the_limit_and_csrf_pass(self):
        with mock.patch.object(auth, "check_password_hash", wraps=auth.check_password_hash) as check:
            for _ in range(5):
                self.assertEqual(self.login(PASSWORD, csrf="forged").status_code, 400)
            self.assertEqual(check.call_count, 0)   # a bad CSRF token never reaches the hash
            refused = self.login(PASSWORD)          # and counts as a failure: this address is now refused
            self.assertEqual(refused.status_code, 429)
            self.assertEqual(check.call_count, 0)
            self.assertEqual(self.login(PASSWORD, ip="192.0.2.99").status_code, 302)
            self.assertEqual(check.call_count, 1)

    def test_failed_logins_are_limited_per_address(self):
        for _ in range(5):
            self.assertEqual(self.login("wrong").status_code, 401)
        blocked = self.login(PASSWORD)   # even the right password, until the window passes
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Too many failed attempts", blocked.get_data(as_text=True))
        self.assertEqual(self.login(PASSWORD, ip="192.0.2.99").status_code, 302)   # another address isn't blocked

    def test_many_addresses_failing_cannot_lock_the_owner_out(self):
        for i in range(60):   # more than the 50 that used to lock login for everyone
            self.assertEqual(self.login("wrong", ip=f"198.51.100.{i}").status_code, 401)
        self.assertEqual(self.login(PASSWORD, ip="192.0.2.50").status_code, 302)

    def test_limiter_per_address_window_and_global_slowdown(self):
        now = [1000.0]
        limiter = auth.LoginLimiter(per_client=5, slowdown_after=8, slowdown_gap_s=60, window_s=900,
                                    clock=lambda: now[0])
        for _ in range(5):
            self.assertIsNone(limiter.attempt("a"))   # counted before the password is checked
        self.assertEqual(limiter.attempt("a"), "client")
        self.assertIsNone(limiter.attempt("b"))
        now[0] += 899
        self.assertEqual(limiter.attempt("a"), "client")
        now[0] += 1
        self.assertIsNone(limiter.attempt("a"))   # 15 minutes after its first failures
        for client in "cdefghij":
            self.assertIsNone(limiter.attempt(client))
        # 9 failures in the window: a new address still gets in, one that just failed waits a minute
        self.assertIsNone(limiter.attempt("someone-new"))
        self.assertEqual(limiter.attempt("c"), "slowdown")
        now[0] += 60
        self.assertIsNone(limiter.attempt("c"))
        # The right password clears that address and takes its attempt off the total
        total = len(limiter.all)
        limiter.succeeded("someone-new")
        self.assertNotIn("someone-new", limiter.by_client)
        self.assertEqual(len(limiter.all), total - 1)

    def test_limiter_forgets_addresses_whose_failures_are_old(self):
        now = [1000.0]
        limiter = auth.LoginLimiter(window_s=900, clock=lambda: now[0])
        for i in range(100):
            limiter.attempt(f"203.0.113.{i}")
        now[0] += 900
        limiter.attempt("192.0.2.1")
        self.assertEqual(list(limiter.by_client), ["192.0.2.1"])
        self.assertEqual(len(limiter.all), 1)

    def test_session_expires_after_8_hours_and_on_password_change(self):
        settings = self.app.extensions["ops_settings"]
        with stub_external():
            sign_in(self.client, settings, at=time.time() - 7.9 * 3600)
            self.assertEqual(self.client.get("/visitors").status_code, 200)
            sign_in(self.client, settings, at=time.time() - 8.01 * 3600)
            response = self.client.get("/visitors")
            self.assertEqual((response.status_code, response.headers["Location"]), (302, "/login"))
            sign_in(self.client, settings)
            other = make_app({"OPS_PASSWORD_HASH": generate_password_hash("another password!", "pbkdf2:sha256:1000")})
            other_client = other.test_client()
            with self.client.session_transaction() as s:
                old_session = dict(s)
            other.extensions["ops_sessions"].started[old_session["auth"]["sid"]] = time.time()
            with other_client.session_transaction() as s:
                s.update(old_session)   # same secret key and a known session id, but made with the old password
            self.assertEqual(other_client.get("/visitors").status_code, 302)

    def test_logout_needs_csrf_and_ends_the_session(self):
        settings = self.app.extensions["ops_settings"]
        sign_in(self.client, settings)
        self.assertEqual(self.client.post("/logout", data={"csrf_token": "forged"}).status_code, 400)
        with stub_external():
            self.assertEqual(self.client.get("/visitors").status_code, 200)
        response = self.client.post("/logout", data={"csrf_token": "csrf-token"})
        self.assertEqual((response.status_code, response.headers["Location"]), (302, "/login"))
        self.assertEqual(self.client.get("/visitors").status_code, 302)

    def test_logout_revokes_the_session_on_the_server(self):
        """A copy of the cookie taken before sign-out (as someone reading plain HTTP could) stops working."""
        self.assertEqual(self.login(PASSWORD).status_code, 302)
        with self.client.session_transaction() as s:
            captured = dict(s)
        thief = self.app.test_client()
        with thief.session_transaction() as s:
            s.update(captured)
        with stub_external():
            self.assertEqual(thief.get("/visitors").status_code, 200)
            self.assertEqual(self.client.post("/logout", data={"csrf_token": captured["csrf"]}).status_code, 302)
            self.assertEqual(thief.get("/visitors").status_code, 302)
        # A restart forgets every session: a cookie signed with the same key isn't enough on its own
        sign_in(self.client, self.app.extensions["ops_settings"])
        with self.client.session_transaction() as s:
            still_valid = dict(s)
        restarted = make_app().test_client()
        with restarted.session_transaction() as s:
            s.update(still_valid)
        self.assertEqual(restarted.get("/visitors").status_code, 302)

    def test_session_store(self):
        now = [1000.0]
        store = auth.SessionStore(lifetime_s=100, clock=lambda: now[0])
        first, second = store.start(), store.start()
        self.assertNotEqual(first, second)
        self.assertTrue(store.alive(first) and store.alive(second))
        store.end(first)
        self.assertFalse(store.alive(first))
        self.assertTrue(store.alive(second))
        self.assertFalse(store.alive(None) or store.alive("made-up"))
        now[0] += 100
        self.assertFalse(store.alive(second))
        store.start()   # drops the expired ones
        self.assertNotIn(second, store.started)


class RouteProtectionTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def test_every_page_needs_the_session(self):
        client = self.app.test_client()
        rules = [r for r in self.app.url_map.iter_rules() if r.endpoint not in ("login", "logout", "static")]
        self.assertEqual(sorted(r.rule for r in rules), sorted(PAGES))   # a new page must be added here on purpose
        for rule in rules:
            for method in sorted(rule.methods - {"OPTIONS"}):
                response = client.open(rule.rule, method=method)
                if method in ("GET", "HEAD"):
                    self.assertEqual((rule.rule, response.status_code, response.headers.get("Location")),
                                     (rule.rule, 302, "/login"))
                else:
                    self.assertEqual((rule.rule, method, response.status_code), (rule.rule, method, 401))
        # Paths that aren't pages, and static files, give nothing away either
        self.assertEqual(client.get("/no-such-page").status_code, 302)
        css = client.get("/static/ops.css")
        self.assertEqual(css.status_code, 200)
        css.close()

    def test_read_only_only_login_and_logout_accept_post(self):
        for rule in self.app.url_map.iter_rules():
            writes = rule.methods - {"GET", "HEAD", "OPTIONS"}
            if rule.endpoint == "login":
                self.assertEqual(writes, {"POST"})
            elif rule.endpoint == "logout":
                self.assertEqual(rule.methods - {"OPTIONS"}, {"POST"})
            else:
                self.assertEqual(writes, set(), rule.rule)

    def test_security_headers(self):
        response = self.app.test_client().get("/login")
        csp = response.headers["Content-Security-Policy"]
        for part in ("default-src 'self'", "frame-ancestors 'none'", "script-src 'none'"):
            self.assertIn(part, csp)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_pages_render_when_the_tables_are_missing(self):
        """SQLite has none of the tables: each section says it couldn't read, and the page still renders."""
        client = self.app.test_client()
        sign_in(client, self.app.extensions["ops_settings"])
        with stub_external():
            for path in PAGES:
                response = client.get(path)
                self.assertEqual(response.status_code, 200, path)
                if path != "/visitors":
                    self.assertIn("Couldn't read", response.get_data(as_text=True), path)
            self.assertEqual(client.get("/traffic?range=1;DROP TABLE x").status_code, 200)   # unknown: the default


class ProbeAndHelperTests(unittest.TestCase):
    def test_check_results(self):
        def answer(status):
            return mock.Mock(return_value=mock.Mock(status_code=status))
        now = dt.datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
        ok = probe.check("dashboard", "http://dashboard:8081/api/latest", {}, get=answer(200), now=now)
        self.assertEqual((ok["ok"], ok["status"], ok["error"], ok["checked_at"]), (True, 200, None, now))
        self.assertFalse(probe.check("wordpress", "http://wordpress/", {}, get=answer(502))["ok"])
        self.assertFalse(probe.check("wordpress", "http://wordpress/", {}, get=answer(301))["ok"])
        down = probe.check("dashboard", "http://x", {}, get=mock.Mock(side_effect=requests.exceptions.ConnectTimeout()))
        self.assertEqual((down["ok"], down["status"], down["error"]), (False, None, "ConnectTimeout"))

    def test_targets(self):
        settings = load_settings(ENV)
        targets = probe.probe_targets(settings)
        self.assertEqual([t[0] for t in targets], ["dashboard", "api", "wordpress"])
        self.assertEqual(targets[1][1], "http://backend:5000/api/latest")
        self.assertEqual(targets[1][2], {"X-Welldash2-Probe": "1"})   # kept out of the traffic counts
        self.assertEqual(targets[2][1], "http://wordpress/")
        self.assertEqual(targets[2][2]["Host"], "well.mcmaster.ca")
        none = load_settings({**ENV, "OPS_PROBE_DASHBOARD_URL": "", "OPS_PROBE_API_URL": "",
                              "OPS_PROBE_WORDPRESS_URL": ""})
        self.assertEqual(probe.probe_targets(none), [])

    def test_hashpw_prints_a_hash_never_the_password(self):
        printed = []
        self.assertEqual(hashpw.main([], ask=lambda prompt: PASSWORD, out=printed.append), 0)
        self.assertEqual(len(printed), 2)
        self.assertTrue(printed[0].startswith("OPS_PASSWORD_HASH='scrypt:"))
        self.assertTrue(printed[1].startswith("OPS_SECRET_KEY='"))
        self.assertNotIn(PASSWORD, "".join(printed))
        hash_value = printed[0].split("=", 1)[1]
        settings = load_settings({**ENV, "OPS_PASSWORD_HASH": hash_value, "OPS_SECRET_KEY": printed[1].split("=", 1)[1]})
        from werkzeug.security import check_password_hash
        self.assertTrue(check_password_hash(settings.password_hash, PASSWORD))
        answers = iter([PASSWORD, "different"])
        with mock.patch("sys.stderr"):
            self.assertEqual(hashpw.main([], ask=lambda prompt: next(answers), out=printed.append), 1)
            self.assertEqual(hashpw.main(["--hash-only"], ask=lambda prompt: "short", out=printed.append), 1)
        self.assertEqual(len(printed), 2)

    def test_outside_services_skipped_when_unconfigured_and_errors_hide_details(self):
        external.clear_cache()
        settings = load_settings(ENV)
        self.assertEqual(external.sentry_issues(settings), {"configured": False})
        self.assertEqual(external.healthchecks(settings), {"configured": False})
        self.assertEqual(external.goatcounter(settings), {"configured": False})
        hc = load_settings({**ENV, "HEALTHCHECKS_API_KEY": "secret-key-1"})
        response = requests.Response()
        response.status_code = 401
        failing = mock.Mock(side_effect=requests.exceptions.HTTPError("401 for https://x/?key=secret-key-1",
                                                                       response=response))
        result = external.healthchecks(hc, get=failing)
        self.assertEqual(result, {"error": "HTTP 401"})
        bad_code = load_settings({**ENV, "OPS_GOATCOUNTER_CODE": "evil.com/x?"})
        self.assertIn("error", external.goatcounter(bad_code))
        external.clear_cache()


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "set TEST_POSTGRES_URL to run welldash² against PostgreSQL")
class PostgresPageTests(unittest.TestCase):
    """Every page from empty tables, then from populated ones, in a schema of its own (dropped afterwards)."""

    @classmethod
    def setUpClass(cls):
        from db.database import db
        from db.models import AlertIncident, ExportJob, SensorMeasurement, VendorStatus
        url = os.environ["TEST_POSTGRES_URL"]
        admin = create_engine(url)
        with admin.begin() as conn:
            conn.exec_driver_sql("DROP SCHEMA IF EXISTS ops_test CASCADE; CREATE SCHEMA ops_test")
        admin.dispose()
        cls.engine = create_engine(url, connect_args={"options": "-c search_path=ops_test"})
        db.metadata.create_all(cls.engine, tables=[t.__table__ for t in (SensorMeasurement, ExportJob, VendorStatus,
                                                                          AlertIncident)])
        with cls.engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE schema_migrations (version varchar(255) PRIMARY KEY, "
                                 "applied_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            conn.exec_driver_sql((APP / "db" / "migrations" / "0005_ops_metrics.sql").read_text(encoding="utf-8"))
        cls.app = make_app(engine=cls.engine)
        cls.settings = cls.app.extensions["ops_settings"]

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        admin = create_engine(os.environ["TEST_POSTGRES_URL"])
        with admin.begin() as conn:
            conn.exec_driver_sql("DROP SCHEMA IF EXISTS ops_test CASCADE")
        admin.dispose()

    def get_all(self):
        client = self.app.test_client()
        sign_in(client, self.settings)
        pages = {}
        with stub_external():
            for path in PAGES + ["/uptime?range=7d", "/uptime?range=30d", "/traffic?range=7d", "/traffic?range=30d"]:
                response = client.get(path)
                self.assertEqual(response.status_code, 200, path)
                html = response.get_data(as_text=True)
                self.assertNotIn("Couldn't read", html, path)
                pages[path] = html
        return pages

    def test_1_empty_tables(self):
        pages = self.get_all()
        self.assertIn("No uptime checks recorded yet", pages["/"])
        self.assertIn("No data in this period", pages["/traffic"])
        self.assertIn("No failed checks", pages["/uptime"])

    def test_2_populated_tables(self):
        from sqlalchemy import text
        from utils.traffic import RequestAggregator, write_rows
        now = dt.datetime.now(UTC)
        from utils.timezone import EST_TZ
        site = lambda ts: ts.astimezone(EST_TZ).replace(tzinfo=None)   # noqa: E731  (naive site time, as stored)
        # Uptime: the dashboard up for an hour except a 3-minute outage; WordPress down now.
        answers = iter([502 if 20 <= m < 23 else 200 for m in range(60)])
        for m in range(60):
            probe.record(self.engine, [probe.check("dashboard", "http://d", {}, now=now - dt.timedelta(minutes=60 - m),
                                                   get=mock.Mock(return_value=mock.Mock(status_code=next(answers))))])
        probe.record(self.engine, [probe.check("wordpress", "http://w", {}, now=now - dt.timedelta(minutes=1),
                                               get=mock.Mock(side_effect=requests.exceptions.ConnectionError()))])
        agg = RequestAggregator()
        for m in range(1, 120):
            agg.record(now - dt.timedelta(minutes=m), "/api/series", "GET", 200, 120.0, 20000)
        agg.record(now - dt.timedelta(minutes=5), "/api/exports/jobs/<job_id>/download", "GET", 200, 900.0, 5_000_000)
        agg.record(now - dt.timedelta(minutes=5), "/api/latest", "GET", 503, 25000.0, 100)
        write_rows(self.engine, agg.take())
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO sensor_measurements (station_id, group_type, measurement_type, value, unit, "
                              "recorded_at) VALUES ('4501', 'Quality', 'Water Temperature', 7.5, 'C', :t)"),
                         {"t": site(now - dt.timedelta(minutes=20))})
            conn.execute(text("INSERT INTO vendor_status (source, last_attempt_at, last_success_at, consecutive_failures, "
                              "last_error) VALUES ('LI-COR', :n, :n, 0, NULL), ('WQData', :n, :old, 4, 'HTTP 503')"),
                         {"n": now, "old": now - dt.timedelta(hours=1)})
            conn.execute(text("INSERT INTO alert_incidents (incident_key, kind, title, detail, started_at, opened_at, "
                              "last_seen_at, notifications, flaps) VALUES ('vendor:WQData', 'VENDOR_DOWN', "
                              "'WQData API not responding', 'd', :t, :t, :t, 1, 0)"), {"t": now - dt.timedelta(hours=1)})
            for status, error in (("ready", None), ("failed", "The export took too long"), ("queued", None)):
                conn.execute(text("INSERT INTO export_jobs (id, status, domain, payload, estimated_rows, produced_rows, "
                                  "progress_pct, created_at, started_at, completed_at, error_message) VALUES "
                                  "(:id, :s, 'sensor', '{}', 1000, 900, 0, :c, :c, :done, :e)"),
                             {"id": status, "s": status, "c": site(now - dt.timedelta(hours=2)),
                              "done": site(now - dt.timedelta(hours=2) + dt.timedelta(seconds=40)), "e": error})
            conn.execute(text("INSERT INTO schema_migrations (version) VALUES ('0005_ops_metrics')"))
        pages = self.get_all()
        overview = pages["/"]
        self.assertIn("Dashboard page", overview)
        self.assertIn("WordPress site", overview)
        self.assertIn("ConnectionError", overview)
        self.assertIn("WQData API not responding", overview)
        self.assertIn("4 failed", overview)
        self.assertIn("abc1234", overview)            # the CI stub
        uptime = pages["/uptime"]
        self.assertIn("95.00\u00a0%", uptime)          # 57 of 60 dashboard checks
        self.assertIn("HTTP 502", uptime)
        self.assertIn("still down", uptime)            # WordPress
        self.assertIn("<svg", uptime)
        traffic_page = pages["/traffic"]
        self.assertIn("/api/series", traffic_page)
        self.assertIn("121", traffic_page)              # 119 + 1 + 1 requests
        self.assertIn("The export took too long", traffic_page)
        self.assertIn("<rect", traffic_page)
        self.assertIn("0005_ops_metrics", pages["/system"])
        self.assertIn("sensor_measurements", pages["/system"])

    def test_3_prune_keeps_the_last_90_days(self):
        from sqlalchemy import text
        now = dt.datetime.now(UTC)
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO uptime_probes (checked_at, target, ok) VALUES (:old, 'x', true), "
                              "(:new, 'x', true)"), {"old": now - dt.timedelta(days=91), "new": now - dt.timedelta(days=89)})
        deleted = probe.prune(self.engine, 90, now)
        self.assertEqual(deleted["uptime_probes"], 1)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM uptime_probes WHERE target = 'x'")).scalar(), 1)

    def test_4_statement_timeout(self):
        """welldash²'s own engine cuts a statement off after 20 s."""
        app = create_app(env={**ENV, "OPS_DATABASE_URL": os.environ["TEST_POSTGRES_URL"]}, start_background=False)
        engine = app.extensions["ops_engine"]
        with engine.connect() as conn:
            self.assertEqual(conn.exec_driver_sql("SHOW statement_timeout").scalar(), "20s")
        engine.dispose()

    def test_5_pages_cannot_write(self):
        """The page reads run in READ ONLY transactions."""
        from sqlalchemy import text
        from sqlalchemy.exc import InternalError, OperationalError, ProgrammingError
        from ops.data import reading
        with self.assertRaises((InternalError, OperationalError, ProgrammingError)):
            with reading(self.engine) as conn:
                conn.execute(text("DELETE FROM uptime_probes"))


if __name__ == "__main__":
    unittest.main()
