# Debian trixie named explicitly: the PostgreSQL apt repository below is per Debian release, so the base image must
# not move to a new release unnoticed.
FROM python:3.11-slim-trixie
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# pg_dump and pg_restore for the nightly database backup (scripts/backup_db.py), in the server's major version (13
# on the VM): Debian's own client is newer, and a newer pg_dump writes archives that pg_restore 13 can't read. They
# come from the PostgreSQL project's apt repository and live in /usr/lib/postgresql/13/bin. Change the version
# here, and DEFAULT_PG_BIN_DIR in utils/backup.py, when the server is upgraded.
# The repository's signing key is checked against its SHA-256 (it is the key with fingerprint
# B97B 0AFC AA1A 47F0 44F2 44A0 7FCC 7D46 ACCC 4CF8), so the build stops if the download isn't that key.
# PostgreSQL 13 is past end of life: if its client ever leaves this repository, switch to the archive,
# https://apt-archive.postgresql.org/pub/repos/apt with the suite trixie-pgdg-archive.
RUN install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
       https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && echo "0144068502a1eddd2a0280ede10ef607d1ec592ce819940991203941564e8e76  /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc" \
       | sha256sum -c - \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-13 \
    && rm -rf /var/lib/apt/lists/* \
    && /usr/lib/postgresql/13/bin/pg_dump --version

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs as an unprivileged user (uid and gid 10001), not root, so code execution in the API isn't root in the
# container. The code stays root's, read-only to it. The folders it writes (logs/, exports/ and /app/backups, which
# compose mounts) are writable by any user (mode 1777, like /tmp), so docker-compose.yml can run it as another uid
# (BACKEND_UID: the VM user that owns the bind-mounted folders), and a named volume created from one starts out
# writable too. Everything else it writes goes to /tmp, HOME included (gunicorn keeps its control socket there), also
# for a uid that has no entry in the image's /etc/passwd.
ENV HOME=/tmp
RUN groupadd --system --gid 10001 well \
    && useradd --system --uid 10001 --gid 10001 --home-dir /tmp --no-create-home --shell /usr/sbin/nologin well \
    && mkdir -p /app/app/logs /app/app/exports /app/backups \
    && chmod 1777 /app/app/logs /app/app/exports /app/backups
USER 10001:10001

# Set working directory to app folder where the Python modules are
WORKDIR /app/app

EXPOSE 5000

# 3 worker processes with 4 threads each (gthread), so a few slow chart requests can't hold every worker while
# /api/latest and the health checks wait behind them. With threads, --timeout only restarts a worker that has
# stopped responding altogether; a slow request is bounded by DB_STATEMENT_TIMEOUT_MS (docker-compose.yml)
# instead. --max-requests restarts each worker now and then (jittered, so not all at once) to release memory a
# large response left behind. --keep-alive 10 keeps an idle connection open longer than the dashboard's proxy
# (dashboard/frontend/src/lib/proxyBackend.ts, 5 s) keeps it for reuse, so the dashboard closes idle connections
# first: if gunicorn closed them first (its default is 2 s), Next could send a request on a connection gunicorn
# had just closed, and the page got a 502. The access log goes to stdout (docker compose logs backend).
# Not the sync worker: it reads each request in its only thread, so a client that sent nothing for --timeout got the
# worker stopped, and its SystemExit reached Sentry as an error (WELL-BACKEND-2). gthread gives a new connection 5 s
# to start sending, then parks it without holding a thread. Once a request has started, gunicorn doesn't limit how
# long the rest takes to arrive: 12 clients trickling headers or a body hold all 12 threads. So the backend has no
# public port: only the dashboard's proxy connects, and it sends each request whole, after Next has read it.
CMD ["gunicorn", "-k", "gthread", "-w", "3", "--threads", "4", "--timeout", "60", "--graceful-timeout", "30", \
     "--max-requests", "1000", "--max-requests-jitter", "100", "--keep-alive", "10", "--access-logfile", "-", \
     "-b", "0.0.0.0:5000", "server:app"]