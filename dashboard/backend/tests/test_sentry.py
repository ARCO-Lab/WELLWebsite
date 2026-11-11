"""Tests for utils/sentry.py (error reporting). Nothing is sent anywhere: events go to an in-memory transport.
Run from dashboard/backend: python -m unittest discover -s tests"""
import os
import pathlib
import sys
import unittest
from unittest import mock

import sentry_sdk
from sentry_sdk.transport import Transport

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
            with mock.patch.dict(os.environ, env, clear=True), mock.patch("sentry_sdk.init") as init:
                self.assertFalse(well_sentry.init_sentry("backend"))
                init.assert_not_called()
        self.assertFalse(sentry_sdk.is_initialized())
        well_sentry.capture_job_error(RuntimeError("no-op while off"))   # must not raise

    def test_settings_are_errors_only_and_without_personal_data(self):
        env = {"SENTRY_DSN": FAKE_DSN, "SENTRY_ENVIRONMENT": "staging", "GIT_SHA": "abc123"}
        with mock.patch.dict(os.environ, env), mock.patch("sentry_sdk.init") as init:
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
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("sentry_sdk.init") as init:
            well_sentry.init_sentry("backend")
        self.assertEqual(init.call_args.kwargs["environment"], "production")
        self.assertIsNone(init.call_args.kwargs["release"])


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

        with mock.patch.dict(os.environ, {"SENTRY_DSN": FAKE_DSN}), mock.patch("sentry_sdk.init", side_effect=init):
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

        app.test_client().get("/boom?station=1&apiKey=SECRET", headers={"Cookie": "session=s"},
                              environ_base={"REMOTE_ADDR": "203.0.113.9"})
        events = self.flush()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["tags"]["component"], "backend")
        self.assertEqual(event["exception"]["values"][-1]["value"], "boom")
        self.assertEqual(set(event["request"]), {"method", "url"})
        text = repr(event)
        for leaked in ("SECRET", "session=s", "203.0.113.9"):
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


if __name__ == "__main__":
    unittest.main()
