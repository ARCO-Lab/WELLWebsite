"""The backend's tests. Run from dashboard/backend: python -m unittest discover -s tests -t .

With -t . unittest imports this package before any test module, so the line below runs first. It points the app
at an in-memory SQLite database whatever the shell or app/.env (which config.py loads) says: config.py reads
DATABASE_URL once, when first imported, and server.py builds the app on import, so without a value some test
modules can't be imported, and with a real one a test could reach a real database. Tests that need PostgreSQL
don't use DATABASE_URL; they take a throwaway database's URL from their own variable (MIGRATE_TEST_DATABASE_URL,
TEST_POSTGRES_URL) and are skipped without it."""
import os

os.environ["DATABASE_URL"] = "sqlite://"

# Never report to Sentry from a test, even when run inside a container whose env has the real DSN
# (docker compose exec backend python -m unittest ...): server.py starts reporting on import when SENTRY_DSN is set.
# Set to "" (which utils/sentry.py treats as unset), not removed: config.py's load_dotenv() would refill a removed
# variable from app/.env in a clone that has one, such as the VM's. tests/test_sentry.py sets a fake DSN itself and
# sends to memory only.
for _name in ("SENTRY_DSN", "SENTRY_ENVIRONMENT", "SENTRY_COMPONENT"):
    os.environ[_name] = ""

# Apps built on a PostgreSQL test database would count their requests (utils/traffic.py) and write them from a
# background thread into whatever request_metrics table exists then, another test's included. tests/test_traffic.py
# turns it back on for the one test that checks it.
os.environ["REQUEST_METRICS"] = "0"
