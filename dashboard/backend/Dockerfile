FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set working directory to app folder where the Python modules are
WORKDIR /app/app

EXPOSE 5000

# 3 worker processes with 4 threads each (gthread), so a few slow chart requests can't hold every worker while
# /api/latest and the health checks wait behind them. With threads, --timeout only restarts a worker that has
# stopped responding altogether; a slow request is bounded by DB_STATEMENT_TIMEOUT_MS (docker-compose.yml)
# instead. --max-requests restarts each worker now and then (jittered, so not all at once) to release memory a
# large response left behind. The access log goes to stdout (docker compose logs backend).
CMD ["gunicorn", "-k", "gthread", "-w", "3", "--threads", "4", "--timeout", "60", "--graceful-timeout", "30", \
     "--max-requests", "1000", "--max-requests-jitter", "100", "--access-logfile", "-", \
     "-b", "0.0.0.0:5000", "server:app"]