"""Celery's Redis retries stay out of Sentry unless the outage lasts (utils/broker_outage.py). Nothing is sent
anywhere: events go to an in-memory transport. Run from dashboard/backend: python -m unittest discover -s tests -t ."""
import inspect
import logging
import os
import pathlib
import sys
import types
import unittest
import unittest.mock

import sentry_sdk

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
os.environ["DATABASE_URL"] = "sqlite://"  # never a real database, whatever the environment says

from celery import Celery, beat  # noqa: E402
from celery.backends import redis as redis_backend  # noqa: E402
from celery.worker.consumer import connection as consumer_connection  # noqa: E402
from celery.worker.consumer import consumer  # noqa: E402

from utils import broker_outage  # noqa: E402
from utils import sentry as well_sentry  # noqa: E402
from tests.test_sentry import FAKE_DSN, MemoryTransport, stop_sentry  # noqa: E402

REFUSED = ConnectionRefusedError(111, "Connection refused")


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Records(logging.Handler):
    """The level each record had when it reached the logger's handlers (what docker compose logs shows)."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.levels = []

    def emit(self, record):
        self.levels.append(record.levelname)


class CeleryMessagesTests(unittest.TestCase):
    """The logger names and message starts the filter relies on are the installed Celery's."""

    def test_the_retry_loggers_and_messages(self):
        prefixes = broker_outage.RETRY_MESSAGES
        self.assertTrue(consumer.CONNECTION_ERROR.startswith(prefixes[consumer.logger.name]))
        self.assertTrue(redis_backend.E_LOST.startswith(prefixes[redis_backend.logger.name]))
        self.assertEqual(beat.logger.name, "celery.beat")
        self.assertIn(prefixes["celery.beat"], inspect.getsource(beat.Scheduler._ensure_connected))
        self.assertEqual(consumer_connection.logger.name, broker_outage.CONNECTED_LOGGER)
        self.assertIn(f"info('{broker_outage.CONNECTED_MESSAGE}%s'",
                      inspect.getsource(consumer_connection.Connection.start))

    def test_the_celery_app_installs_it(self):
        from tasks.celery_app import celery_app
        installed = broker_outage.install()
        for name in (*broker_outage.RETRY_MESSAGES, broker_outage.CONNECTED_LOGGER):
            self.assertIn(installed, logging.getLogger(name).filters, name)
        self.assertIs(broker_outage.install(), installed)   # once per process
        self.assertIs(celery_app.conf.broker_connection_retry_on_startup, True)


class OutageTests(unittest.TestCase):
    """The real SDK and logging integration, sending to memory, with a fresh filter on a fake clock."""

    def setUp(self):
        real_init = sentry_sdk.init
        with unittest.mock.patch.dict(os.environ, {"SENTRY_DSN": FAKE_DSN}), \
                unittest.mock.patch("sentry_sdk.init", side_effect=lambda **o: real_init(transport=MemoryTransport, **o)):
            self.assertTrue(well_sentry.init_sentry("export_worker"))
        self.addCleanup(stop_sentry)
        self.clock = Clock()
        self.outage = broker_outage.BrokerOutageFilter(clock=self.clock)
        self.records = Records()
        for name in (*broker_outage.RETRY_MESSAGES, broker_outage.CONNECTED_LOGGER):
            logger = logging.getLogger(name)
            # The process-wide filter (installed when tasks.celery_app is imported) runs on the real clock: set aside
            for installed in [f for f in logger.filters if isinstance(f, broker_outage.BrokerOutageFilter)]:
                logger.removeFilter(installed)
                self.addCleanup(logger.addFilter, installed)
            logger.addFilter(self.outage)
            logger.addHandler(self.records)
            self.addCleanup(logger.removeFilter, self.outage)
            self.addCleanup(logger.removeHandler, self.records)
        # The worker logs at INFO (--loglevel=info), so "Connected to" is seen; Python's default is WARNING
        connected = logging.getLogger(broker_outage.CONNECTED_LOGGER)
        self.addCleanup(connected.setLevel, connected.level)
        connected.setLevel(logging.INFO)

    def events(self):
        sentry_sdk.flush(timeout=2)
        return sentry_sdk.get_client().transport.events

    def retry(self, after_s=10):
        """One of the consumer's retry messages, as Celery logs it, `after_s` after the last one."""
        self.clock.now += after_s
        consumer.error(consumer.CONNECTION_ERROR, "redis://:**@redis:6379/0",
                       f"Error 111 connecting to redis:6379. {REFUSED.strerror}.", "Trying again in 2.00 seconds...")

    def test_a_deploy_restarting_redis_sends_nothing(self):
        for _ in range(28):   # the 28 events of one deploy, seconds apart
            self.retry(after_s=2)
        consumer_connection.info("Connected to %s", "redis://:**@redis:6379/0")
        self.assertEqual(self.events(), [])
        self.assertEqual(set(self.records.levels), {"WARNING", "INFO"})

    def test_an_outage_that_lasts_is_sent_once(self):
        self.retry()
        for _ in range(20):   # 30 s apart, as Celery's longest interval: 10 minutes in all
            self.retry(after_s=30)
        events = self.events()
        self.assertEqual(len(events), 1, events)
        event = events[0]
        self.assertEqual(event["level"], "error")
        self.assertEqual(event["message"], broker_outage.OUTAGE_MESSAGE)
        self.assertIn("Cannot connect to redis://:**@redis:6379/0", event["contexts"]["broker"]["last_error"])
        self.assertNotIn("Trying again", event["contexts"]["broker"]["last_error"])
        self.assertEqual(event["tags"]["component"], "export_worker")

    def test_reconnecting_ends_the_outage(self):
        for _ in range(9):
            self.retry(after_s=30)   # 4 min
        consumer_connection.info("Connected to %s", "redis://:**@redis:6379/0")
        for _ in range(9):
            self.retry(after_s=30)   # 4 min more, but a new outage
        self.assertEqual(self.events(), [])

    def test_retries_far_apart_are_separate_outages(self):
        for _ in range(4):
            self.retry(after_s=broker_outage.NEW_OUTAGE_AFTER_S + 60)
        self.assertEqual(self.events(), [])

    def test_beat_and_result_backend_retries_are_warnings_too(self):
        beat.logger.error("beat: Connection error: %s. Trying again in %s seconds...", REFUSED, 2)
        redis_backend.logger.error(redis_backend.E_LOST.strip(), 1, 20, "in 1.00 second")
        self.assertEqual(self.records.levels, ["WARNING", "WARNING"])
        self.assertEqual(self.events(), [])

    def test_other_errors_of_these_loggers_still_reach_sentry(self):
        consumer.error("Received unregistered task of type %r.", "exports.unknown")
        events = self.events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["level"], "error")
        self.assertEqual(self.records.levels, ["ERROR"])

    def test_a_failing_report_doesnt_break_logging(self):
        self.outage.report = unittest.mock.Mock(side_effect=RuntimeError("no network"))
        for _ in range(12):
            self.retry(after_s=30)
        self.outage.report.assert_called_once()
        self.assertEqual(self.records.levels.count("WARNING"), 12)


class RealRetryTests(unittest.TestCase):
    """Celery's own retry loop against a port that refuses connections, through the consumer's error handler."""

    def test_the_consumers_retries_are_logged_as_warnings(self):
        app = Celery("broker_outage_test", broker="redis://127.0.0.1:1/0")
        app.conf.broker_connection_max_retries = 1   # one retry message, then give up (about 2 s)
        records = Records()
        logger = logging.getLogger(consumer.logger.name)
        outage = broker_outage.BrokerOutageFilter(report=unittest.mock.Mock())
        logger.addFilter(outage)
        logger.addHandler(records)
        self.addCleanup(logger.removeFilter, outage)
        self.addCleanup(logger.removeHandler, records)
        state = types.SimpleNamespace(app=app, first_connection_attempt=True, broker_connection_retry_attempt=0)
        with self.assertRaises(Exception):
            consumer.Consumer.ensure_connected(state, app.connection_for_read())
        self.assertEqual(records.levels, ["WARNING"])
        self.assertIsNotNone(outage.started)
        outage.report.assert_not_called()


if __name__ == "__main__":
    unittest.main()
