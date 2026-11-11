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
# tests/test_sentry.py sets a fake DSN itself and sends to memory only.
for _name in ("SENTRY_DSN", "SENTRY_ENVIRONMENT", "SENTRY_COMPONENT"):
    os.environ.pop(_name, None)
