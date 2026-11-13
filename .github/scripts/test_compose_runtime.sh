#!/usr/bin/env bash
# Starts the services built from the backend image (backend, worker, export_worker and ops) from docker-compose.yml, as
# the VM runs them, and checks that each runs as the configured unprivileged user, with no capabilities and
# no-new-privileges, and can write where it must: the worker into the bind-mounted logs/ and backups/ folders, the API
# and the export worker into the exports volume. First it sets things up as a VM that ran the old root image would
# have them (root-owned folders and volume) and runs the one-time commands from docs/hosting.md, "Containers run
# unprivileged", so those are tested too.
#
# For CI: it needs Docker and sudo, writes .env and the two folders in this checkout, and removes its containers and
# volumes at the end.   bash .github/scripts/test_compose_runtime.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
SERVICES=(backend worker export_worker ops)
uid=$(id -u) gid=$(id -g)
compose() { docker compose --profile ops "$@"; }
cleanup() { compose down -v --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
fail() {
  echo "::error::$*"
  compose ps -a || true
  for s in "${SERVICES[@]}"; do
    echo "::group::logs of $s"; compose logs --no-color "$s" 2>&1 | tail -40 || true; echo "::endgroup::"
  done
  exit 1
}
# Waits up to $1 seconds for the command after it to succeed
wait_for() { local n=$1; shift; for _ in $(seq "$n"); do if "$@" >/dev/null 2>&1; then return 0; fi; sleep 1; done; return 1; }

# Placeholders, as the lint job's `docker compose config` uses, and vendor settings the worker needs to start. The
# database and the vendor APIs can't be reached, on purpose: the API's /health answers without them, and the worker
# and the export worker start and log the errors.
touch dashboard/frontend/.env.local
cat > dashboard/backend/app/.env <<'EOF'
HOBOLINK_API_URL=http://127.0.0.1:1
HOBOLINK_API_TOKEN=ci
HOBOLINK_LOGGERS=1
WQ_API_URL=http://127.0.0.1:1
WQ_API_KEY=ci
WQ_DEVICE_ID=1
EOF
cat > .env <<'EOF'
MYSQL_ROOT_PASSWORD=ci
WORDPRESS_DB_PASSWORD=ci
WP_HOME=http://localhost:8080
WP_SITEURL=http://localhost:8080
DASHBOARD_URL=http://localhost:8081
DASHBOARD_PORT=8081
BACKEND_DATABASE_URL=postgresql://ci:ci@127.0.0.1:1/ci
BACKEND_PORT=5000
BACKEND_INTERNAL_URL=http://backend:5000
NEXT_PUBLIC_FLASK_API_URL=http://localhost:5000
WORKER_LOG_TO_STDOUT=1
OPS_BIND=127.0.0.1
OPS_SECRET_KEY=ci-only-secret-key-that-is-long-enough
EOF

# As on a VM where the old image ran as root: the two folders and a file in each are root's, the backups folder is
# private, and the exports volume is root's and not writable by others.
sudo rm -rf dashboard/backend/app/logs backups
sudo mkdir -p dashboard/backend/app/logs backups/daily
sudo touch dashboard/backend/app/logs/db_injections.log backups/daily/old.dump
sudo chmod 0700 backups backups/daily
compose build "${SERVICES[@]}"
compose run --rm --no-deps -T --user 0 --entrypoint sh export_worker \
  -c 'touch /app/app/exports/old.csv && chmod 755 /app/app/exports'

# welldash²'s password hash, made in the image (it has `$` signs, hence the single quotes)
hash=$(compose run --rm --no-deps -T backend python -c \
  'from werkzeug.security import generate_password_hash as g; print(g("ci"))' | tail -1)
echo "OPS_PASSWORD_HASH='$hash'" >> .env

# The one-time commands from docs/hosting.md
grep -q '^BACKEND_UID=' .env || printf 'BACKEND_UID=%s\nBACKEND_GID=%s\n' "$uid" "$gid" >> .env
compose run --rm --no-deps -T --user 0 --cap-add CHOWN --cap-add DAC_READ_SEARCH --entrypoint chown \
  worker -R "$uid:$gid" /app/app/logs /app/backups
compose run --rm --no-deps -T --user 0 --cap-add CHOWN --cap-add DAC_READ_SEARCH --entrypoint chown \
  export_worker -R "$uid:$gid" /app/app/exports
[ "$(stat -c %u:%g backups/daily/old.dump)" = "$uid:$gid" ] || fail "the chown didn't reach the backups folder"

compose up -d backend worker export_worker
compose up -d --no-deps ops

wait_for 90 compose exec -T backend curl -fsS -m 5 -o /dev/null http://localhost:5000/health \
  || fail "backend: /health didn't answer"
wait_for 90 compose exec -T worker test -f /tmp/well-scheduler.alive || fail "worker: the scheduler loop didn't start"
wait_for 90 test -s dashboard/backend/app/logs/db_injections.log || fail "worker: wrote nothing to logs/"
wait_for 90 compose exec -T export_worker sh -c 'ls /tmp/celerybeat-schedule*' \
  || fail "export_worker: celery beat wrote no schedule file"
wait_for 60 sh -c 'docker compose --profile ops logs export_worker | grep -q "ready\."' \
  || fail "export_worker: celery didn't report ready"
wait_for 90 compose exec -T ops curl -fsS -m 5 -o /dev/null http://localhost:8090/login \
  || fail "ops: /login didn't answer"

for s in "${SERVICES[@]}"; do
  # The container's main process: its user, its capabilities (none) and whether it may gain privileges (no)
  status=$(compose exec -T "$s" cat /proc/1/status)
  ids=$(awk '/^Uid:/ {u = $2} /^Gid:/ {g = $2} END {print u ":" g}' <<<"$status")
  [ "$ids" = "$uid:$gid" ] || fail "$s: runs as $ids, not $uid:$gid"
  grep -Eq '^CapEff:[[:space:]]+0+$' <<<"$status" || fail "$s: has capabilities: $(grep ^CapEff <<<"$status")"
  grep -Eq '^NoNewPrivs:[[:space:]]+1$' <<<"$status" || fail "$s: no-new-privileges isn't set"
  # Nowhere to write in the code
  if compose exec -T "$s" sh -c 'touch /app/app/server.py' 2>/dev/null; then fail "$s: can write to its code"; fi
  echo "ok: $s runs as $ids with no capabilities and no-new-privileges"
done

# Writes: the exports volume (API and export worker), the worker's two bind-mounted folders, as the VM user
for s in backend export_worker; do
  # shellcheck disable=SC2016  # expanded in the container
  compose exec -T "$s" sh -c 'echo x > "$EXPORTS_DIR/ci-$HOSTNAME" && rm "$EXPORTS_DIR/ci-$HOSTNAME"' \
    || fail "$s: can't write to the exports volume"
done
compose exec -T worker sh -c 'echo x > /app/app/logs/ci-write && mkdir -m 700 -p /app/backups/ci && echo x > /app/backups/ci/x' \
  || fail "worker: can't write to logs/ or backups/"
for f in dashboard/backend/app/logs/ci-write dashboard/backend/app/logs/db_injections.log backups/ci/x; do
  [ "$(stat -c %u:%g "$f")" = "$uid:$gid" ] || fail "$f is owned by $(stat -c %u:%g "$f"), not $uid:$gid"
done
compose exec -T ops ls /ops/logs >/dev/null || fail "ops: can't read the logs folder"
echo "ok: the API and export worker write exports, the worker writes logs/ and backups/ as $uid:$gid, ops reads logs/"

# Nothing any of them tried to write was refused (gunicorn's control socket in HOME, say)
if denied=$(compose logs --no-color "${SERVICES[@]}" 2>&1 | grep -i "permission denied"); then
  fail "a service was refused a write: $(head -3 <<<"$denied")"
fi
echo "ok: no 'permission denied' in their logs"
