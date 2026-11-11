"""Tests for utils/sentry.py (error reporting). Nothing is sent anywhere: events go to an in-memory transport.
Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import os
import pathlib
import subprocess
import sys
import unittest.mock
import uuid

import sentry_sdk
from sentry_sdk.transport import Transport

# Also when this module runs on its own, without tests/__init__.py: no test may see the real DSN. "" rather than
# removed, so load_dotenv() can't refill it from app/.env (see tests/__init__.py).
for _name in ("SENTRY_DSN", "SENTRY_ENVIRONMENT", "SENTRY_COMPONENT"):
    os.environ[_name] = ""

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from utils import sentry as well_sentry  # noqa: E402

FAKE_DSN = "https://public@example.invalid/1"


class MemoryTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.events = []

    def capture_envelope(self, envelope):
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


def stop_sentry():
    well_sentry._last_sent.clear()
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)
    sentry_sdk.get_global_scope().remove_tag("component")


class InitTests(unittest.TestCase):
    def tearDown(self):
        stop_sentry()

    def test_without_a_dsn_nothing_is_started(self):
        for value in (None, "", "  "):
            env = {k: v for k, v in os.environ.items() if k != "SENTRY_DSN"}
            if value is not None:
                env["SENTRY_DSN"] = value
            with unittest.mock.patch.dict(os.environ, env, clear=True), unittest.mock.patch("sentry_sdk.init") as init:
                self.assertFalse(well_sentry.init_sentry("backend"))
                init.assert_not_called()
        self.assertFalse(sentry_sdk.is_initialized())
        well_sentry.capture_job_error(RuntimeError("no-op while off"))   # must not raise

    def test_settings_are_errors_only_and_without_personal_data(self):
        env = {"SENTRY_DSN": FAKE_DSN, "SENTRY_ENVIRONMENT": "staging", "GIT_SHA": "abc123"}
        with unittest.mock.patch.dict(os.environ, env), unittest.mock.patch("sentry_sdk.init") as init:
            self.assertTrue(well_sentry.init_sentry("worker"))
        options = init.call_args.kwargs
        self.assertEqual(options["dsn"], FAKE_DSN)
        self.assertEqual(options["environment"], "staging")
        self.assertEqual(options["release"], "abc123")
        self.assertIs(options["send_default_pii"], False)
        self.assertEqual(options["traces_sample_rate"], 0)
        self.assertIs(options["include_local_variables"], False)
        self.assertIs(options["before_send"], well_sentry.before_send)

    def test_environment_defaults_to_production_and_release_to_none(self):
        env = {k: v for k, v in os.environ.items() if k not in ("SENTRY_ENVIRONMENT", "GIT_SHA")}
        env["SENTRY_DSN"] = FAKE_DSN
        with unittest.mock.patch.dict(os.environ, env, clear=True), unittest.mock.patch("sentry_sdk.init") as init:
            well_sentry.init_sentry("backend")
        self.assertEqual(init.call_args.kwargs["environment"], "production")
        self.assertIsNone(init.call_args.kwargs["release"])

    def test_sentry_component_overrides_the_default_tag(self):
        # docker-compose.yml sets it for worker and export_worker, whose scripts import server.py ("backend").
        env = {"SENTRY_DSN": FAKE_DSN, "SENTRY_COMPONENT": "worker"}
        with unittest.mock.patch.dict(os.environ, env), unittest.mock.patch("sentry_sdk.init"):
            well_sentry.init_sentry("backend")
        self.assertEqual(sentry_sdk.get_global_scope()._tags["component"], "worker")


class BeforeSendTests(unittest.TestCase):
    def test_request_details_and_ip_are_dropped(self):
        event = {
            "request": {
                "method": "POST", "url": "https://welldash.example/api/exports",
                "data": {"email": "someone@example.com"}, "cookies": {"session": "s"},
                "headers": {"Cookie": "session=s", "User-Agent": "x", "X-Forwarded-For": "203.0.113.9"},
                "query_string": "station=1&token=t", "env": {"REMOTE_ADDR": "203.0.113.9"},
            },
            "user": {"ip_address": "203.0.113.9"},
        }
        out = well_sentry.before_send(event)
        self.assertEqual(out["request"], {"method": "POST", "url": "https://welldash.example/api/exports"})
        self.assertNotIn("user", out)
        self.assertNotIn("203.0.113.9", repr(out))

    def test_query_strings_in_messages_are_filtered(self):
        message = "403 Client Error: Forbidden for url: https://wqdata.example/v1/data?apiKey=SECRET&from=1"
        event = {"exception": {"values": [{"type": "HTTPError", "value": message}]}, "logentry": {"message": message}}
        out = well_sentry.before_send(event)
        self.assertNotIn("SECRET", repr(out))
        self.assertEqual(out["exception"]["values"][0]["value"],
                         "403 Client Error: Forbidden for url: https://wqdata.example/v1/data?[Filtered]")

    def test_query_strings_in_relative_urls_are_filtered(self):
        # requests' ConnectionError names the URL as a path after the host and port.
        message = ("HTTPSConnectionPool(host='www.wqdatalive.com', port=443): Max retries exceeded with url: "
                   "/api/v1/devices/123/parameters/data?apiKey=SECRET&from=2026-11-10&to=2026-11-11 "
                   "(Caused by NameResolutionError(\"Failed to resolve 'www.wqdatalive.com'\"))")
        out = well_sentry.before_send({"exception": {"values": [{"type": "ConnectionError", "value": message}]}})
        value = out["exception"]["values"][0]["value"]
        self.assertNotIn("SECRET", value)
        self.assertIn("with url: /api/v1/devices/123/parameters/data?[Filtered] (Caused by", value)

    def test_http_breadcrumbs_lose_their_query(self):
        crumb = {"type": "http", "data": {"url": "https://wqdata.example/v1/data?apiKey=SECRET",
                                          "http.query": "apiKey=SECRET", "method": "GET"}}
        out = well_sentry.before_breadcrumb(crumb)
        self.assertNotIn("SECRET", repr(out))
        self.assertEqual(out["data"]["method"], "GET")


class EndToEndTests(unittest.TestCase):
    """The real SDK with the real settings, sending to memory: a Flask error and a scheduler-style captured error."""

    def setUp(self):
        self.transport = None
        real_init = sentry_sdk.init

        def init(**options):
            self.options = options
            return real_init(transport=MemoryTransport, **options)

        with unittest.mock.patch.dict(os.environ, {"SENTRY_DSN": FAKE_DSN}), unittest.mock.patch("sentry_sdk.init", side_effect=init):
            self.assertTrue(well_sentry.init_sentry("backend"))
            # A second call (e.g. server.py imported by the worker) keeps the first component.
            self.assertTrue(well_sentry.init_sentry("worker"))
        self.transport = sentry_sdk.get_client().transport

    def tearDown(self):
        stop_sentry()

    def flush(self):
        sentry_sdk.flush(timeout=2)
        return self.transport.events

    def test_a_flask_error_is_reported_without_request_details(self):
        from flask import Flask
        app = Flask("sentry_test")

        @app.route("/boom")
        def boom():
            raise ValueError("boom")

        # Made at run time, so they don't also appear in the source lines Sentry sends around each frame.
        key, session, ip = uuid.uuid4().hex, uuid.uuid4().hex, f"203.0.113.{uuid.uuid4().int % 250 + 1}"
        app.test_client().get(f"/boom?station=1&apiKey={key}", headers={"Cookie": f"session={session}"},
                              environ_base={"REMOTE_ADDR": ip})
        events = self.flush()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["tags"]["component"], "backend")
        self.assertEqual(event["exception"]["values"][-1]["value"], "boom")
        self.assertEqual(set(event["request"]), {"method", "url"})
        text = repr(event)
        for leaked in (key, session, ip):
            self.assertNotIn(leaked, text)
        frames = event["exception"]["values"][-1]["stacktrace"]["frames"]
        self.assertFalse(any("vars" in f for f in frames), "local variables must not be sent")

    def test_an_already_reported_error_is_not_sent_twice(self):
        first = RuntimeError("LI-COR down")
        well_sentry.capture_job_error(first)
        summary = RuntimeError("ingestion failed for: LI-COR")
        summary.already_reported = True
        well_sentry.capture_job_error(summary)
        events = self.flush()
        self.assertEqual([e["exception"]["values"][-1]["value"] for e in events], ["LI-COR down"])

    def test_scheduler_jobs_tag_their_errors(self):
        from utils.jobs import run_in_background

        def api_injection_job():
            raise RuntimeError("database unreachable")

        run_in_background(api_injection_job, log=lambda *_: None)().join(5)
        events = self.flush()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["tags"]["job"], "api_injection_job")
        self.assertEqual(events[0]["tags"]["component"], "backend")

    def test_the_same_failure_is_sent_at_most_once_an_hour(self):
        clock = [1000.0]
        with unittest.mock.patch.object(well_sentry.time, "monotonic", lambda: clock[0]):
            for minute in range(0, 60, 10):   # an hour of 10-minute runs failing the same way (times differ)
                well_sentry.capture_job_error(ConnectionError(f"LI-COR down at 10:{minute:02d}"), source="LI-COR")
                clock[0] += 600
            well_sentry.capture_job_error(ConnectionError("WQData down at 11:00"), source="WQData")   # another source
            well_sentry.capture_job_error(ConnectionError("LI-COR down at 11:00"), source="LI-COR")   # an hour on
        events = self.flush()
        self.assertEqual([(e["tags"]["source"], e["exception"]["values"][-1]["value"]) for e in events],
                         [("LI-COR", "LI-COR down at 10:00"), ("WQData", "WQData down at 11:00"),
                          ("LI-COR", "LI-COR down at 11:00")])

    def test_a_different_message_of_the_same_type_is_not_throttled(self):
        for message in ("connection refused", "connection refused", 'column "x" does not exist'):
            well_sentry.capture_job_error(RuntimeError(message))
        events = self.flush()
        self.assertEqual([e["exception"]["values"][-1]["value"] for e in events],
                         ["connection refused", 'column "x" does not exist'])

    def test_subprocess_failures_differ_by_arguments_exit_code_and_last_error_line(self):
        def failed(month, code, stderr="", stdout=""):
            return subprocess.CalledProcessError(code, ["python", "scripts/upload_data.py", "--month", month],
                                                 output=stdout, stderr=stderr)
        sent = [
            failed("9", 1, "Traceback ...\nTimeoutError: no answer after 31 s\n"),
            failed("9", 1, "Traceback ...\nTimeoutError: no answer after 30 s\n"),   # same failure: throttled
            failed("9", 1, "Traceback ...\nKeyError: 'files'\n"),                    # another error
            failed("9", 2, stdout="DEBUG: ...\nERROR: No sensor data found from 2026-09-01 to 2026-10-01\n"),
            failed("10", 2, stdout="DEBUG: ...\nERROR: No sensor data found from 2026-10-01 to 2026-11-01\n"),
            failed("10", 2, stdout="ERROR: No sensor data found from 2026-10-01 to 2026-11-01\n"),  # same: throttled
            failed("10", 3),                                                          # another exit code
            subprocess.TimeoutExpired(["python", "scripts/upload_data.py", "--month", "10"], 7200),
        ]
        for error in sent:
            well_sentry.capture_job_error(error)
        got = [(e["contexts"]["subprocess"]["command"].split()[-1], e["contexts"]["subprocess"]["exit_code"])
               for e in self.flush()]
        # Month 10's no-data failure isn't hidden behind month 9's (same exit code, empty stderr).
        self.assertEqual(got, [("9", 1), ("9", 1), ("9", 2), ("10", 2), ("10", 3), ("10", None)])

    def test_stdout_error_lines_go_with_the_event(self):
        key = uuid.uuid4().hex
        stdout = ("DEBUG: reading 4,000 rows of data\nINFO: station 3\n"
                  f"ERROR: GET https://borealis.example/api?key={key} failed\n"
                  "ERROR: No sensor data found from 2026-10-01 to 2026-11-01; nothing uploaded.\n")
        well_sentry.capture_job_error(subprocess.CalledProcessError(2, ["python", "scripts/upload_data.py"],
                                                                    output=stdout, stderr=""))
        context = self.flush()[0]["contexts"]["subprocess"]
        self.assertEqual(context["error_lines"], [
            "ERROR: GET https://borealis.example/api?[Filtered] failed",
            "ERROR: No sensor data found from 2026-10-01 to 2026-11-01; nothing uploaded."])
        self.assertNotIn("DEBUG", repr(context))
        self.assertNotIn(key, repr(context))

    def test_digest_style_error_lines_are_attached_and_tell_failures_apart(self):
        def digest_failed(stdout):
            return subprocess.CalledProcessError(1, ["python", "scripts/daily_digest.py"], output=stdout, stderr="")
        smtp = "[INFO] building\n[ERROR] Emailing the digest failed: SMTPAuthenticationError: 535; the digest was:\n"
        recipients = "[ERROR] SMTP is configured but ALERT_EMAILS has no valid address; the digest was:\n"
        for stdout in (smtp, smtp, recipients):
            well_sentry.capture_job_error(digest_failed(stdout))
        events = self.flush()
        self.assertEqual([e["contexts"]["subprocess"]["error_lines"] for e in events],
                         [[smtp.splitlines()[1]], [recipients.strip()]])

    def test_http_statuses_are_not_collapsed(self):
        sig = well_sentry.failure_signature
        self.assertNotEqual(sig(RuntimeError("HTTP 401 from LI-COR")), sig(RuntimeError("HTTP 503 from LI-COR")))
        self.assertEqual(sig(RuntimeError("HTTP 503 at 10:20, row 123456")),
                         sig(RuntimeError("HTTP 503 at 11:40, row 98")))
        self.assertEqual(sig(RuntimeError("timed out after 700 s")), sig(RuntimeError("timed out after 99 s")))
        self.assertEqual(sig(RuntimeError("job ab12cd34 failed")), sig(RuntimeError("job 9f8e7d6c failed")))

    def test_a_failed_subprocess_is_sent_with_its_exit_code_and_stderr(self):
        error = subprocess.CalledProcessError(1, ["python", "scripts/upload_data.py", "--year", "2026"],
                                              output="lots of output", stderr="x" * 5000 + "\nValueError: bad month")
        well_sentry.capture_job_error(error)
        context = self.flush()[0]["contexts"]["subprocess"]
        self.assertEqual(context["command"], "python scripts/upload_data.py --year 2026")
        self.assertEqual(context["exit_code"], 1)
        # The cut-off first line (5000 x's) is dropped, so the tail starts at a whole line.
        self.assertEqual(context["stderr_tail"], "ValueError: bad month")

    def test_the_stderr_tail_never_starts_inside_an_unscrubbed_url(self):
        n, key = well_sentry.STDERR_TAIL_CHARS, uuid.uuid4().hex
        after_key = "&from=2026-10-01 failed\n"
        url_line = f"GET https://wqdata.example/v1/devices/1/data?apiKey={key}{after_key}"
        last = "\nValueError: boom"
        stderr = "start\n" + url_line + "y" * (n - len(after_key) - 10 - len(last)) + last
        self.assertTrue(stderr[-n:].startswith(key[-10:]), "the raw cut falls inside the key")
        tail = well_sentry.stderr_tail(subprocess.CalledProcessError(1, ["python", "x.py"], stderr=stderr))
        self.assertNotIn(key[-10:], tail)
        self.assertTrue(tail.endswith("ValueError: boom"))
        self.assertLessEqual(len(tail), n)

    def test_a_long_last_line_is_kept_rather_than_dropped_as_partial(self):
        n = well_sentry.STDERR_TAIL_CHARS
        stderr = "Traceback ...\nValueError: " + "z" * (n + 500) + "\n"
        tail = well_sentry.stderr_tail(subprocess.CalledProcessError(1, ["python", "x.py"], stderr=stderr))
        self.assertEqual(tail, ("z" * n + "\n")[-n:])

    def test_scheduler_subprocesses_run_without_the_dsn(self):
        # So a crash in upload_data.py is reported once, by the scheduler, not also by the script itself.
        from utils.jobs import run_bounded
        code = "import os; print(repr(os.environ.get('SENTRY_DSN')))"
        with unittest.mock.patch.dict(os.environ, {"SENTRY_DSN": FAKE_DSN}):
            result = run_bounded([sys.executable, "-c", code], timeout=30)
        self.assertEqual(result.stdout.strip(), "''")


if __name__ == "__main__":
    unittest.main()
