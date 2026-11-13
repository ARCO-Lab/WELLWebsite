#!/usr/bin/env bash
# Prints, and never runs, the steps that move the WELL containers off the PostgreSQL superuser onto the roles in
# roles.sql (well_app, well_ops and well_restore). Each step needs sudo on the VM and is meant to be read and run by
# hand, one at a time; the backend README's "Database roles" section explains each, and how to roll back.
#
#   dashboard/backend/app/db/roles.sh <database>      e.g. roles.sh welldb (the name at the end of BACKEND_DATABASE_URL)
set -euo pipefail

if [ $# -ne 1 ] || ! [[ $1 =~ ^[a-z_][a-z0-9_]*$ ]]; then
  echo "usage: $0 <database>   (the WELL database's name: lowercase letters, digits and _)" >&2
  exit 2
fi
db=$1
# Every superuser psql searches pg_catalog only, so nothing well_app creates in public runs as postgres.
su_psql="sudo -u postgres env PGOPTIONS='-c search_path=pg_catalog' psql"

cat <<EOF
# Run from ~/WELLWebsite, one step at a time. Nothing here has been run.

# 0. The server's version: 13.16 or newer (fixes CVE-2022-1552 and CVE-2024-7348). PostgreSQL 13 is past its end of
#    life (November 2025), so plan the upgrade too.
$su_psql -tAc 'SHOW server_version'

# 1. A backup first, as the app connects today.
docker compose exec worker python scripts/backup_db.py --no-prune

# 2. Create the roles and hand the tables to well_app (safe to run again). Then check.
$su_psql -d $db -v ON_ERROR_STOP=1 < dashboard/backend/app/db/roles.sql
$su_psql -d $db -v ON_ERROR_STOP=1 < dashboard/backend/app/db/roles_check.sql

# 3. A password for each role, stored as SCRAM. Generate them with: openssl rand -hex 24
$su_psql -d $db -c "SET password_encryption = 'scram-sha-256'" -c '\\password well_app'
$su_psql -d $db -c "SET password_encryption = 'scram-sha-256'" -c '\\password well_ops'
$su_psql -d $db -c "SET password_encryption = 'scram-sha-256'" -c '\\password well_restore'

# 4. pg_hba.conf: allow the three roles from the Docker networks by password, reject everything else from there
#    (postgres included). Its path: $su_psql -tAc 'SHOW hba_file'.
#    Keep a copy, edit, then reload:
#      host  $db                       well_app      10.20.0.0/16  scram-sha-256
#      host  $db                       well_ops      10.20.0.0/16  scram-sha-256
#      host  $db,welldb_restore_check  well_restore  10.20.0.0/16  scram-sha-256
#      host  all                       all           10.20.0.0/16  reject
#    The first matching line wins, so these go above every other host line that could match 10.20.0.0/16. Delete an
#    older line only if its address is 10.20.0.0/16 or a part of it; a wider one (e.g. 10.0.0.0/8, 0.0.0.0/0) stays,
#    below these. A drill run with --database welldb_restore_check_<suffix> needs that name on the well_restore line.
$su_psql -c 'SELECT pg_reload_conf()'
$su_psql -c "SELECT line_number, database, user_name, address, auth_method, error FROM pg_hba_file_rules WHERE error IS NOT NULL OR address = '10.20.0.0'"

# 5. Point the containers at the roles: keep a copy of both .env files (outside the repository, so they are never
#    committed), edit them, recreate the containers.
(umask 077 && cp -p .env ~/well-root.env.before-db-roles && cp -p dashboard/backend/app/.env ~/well-app.env.before-db-roles)
#    In .env:
#      BACKEND_DATABASE_URL=postgresql://well_app:<password>@host.docker.internal:5432/$db
#      OPS_DATABASE_URL=postgresql://well_ops:<password>@host.docker.internal:5432/$db
#    In dashboard/backend/app/.env (the worker reads it, and the restore drill runs there):
#      RESTORE_CHECK_DATABASE_URL=postgresql://well_restore:<password>@host.docker.internal:5432/$db
docker compose up -d --no-deps backend worker export_worker
docker compose up -d --no-deps ops                   # only if welldash² runs

# 6. Check: which roles are connected (no postgres from 10.20.x.x), the API reads the database (200), a backup made
#    as well_app leaves nothing out (no WARNING line), and the restore drill passes as well_restore.
$su_psql -d $db -c "SELECT usename, application_name, client_addr, count(*) FROM pg_stat_activity WHERE datname = '$db' GROUP BY 1, 2, 3 ORDER BY 1, 2"
docker compose exec backend curl -fsS -o /dev/null -w '%{http_code}\\n' -H 'X-Welldash2-Probe: 1' http://localhost:5000/api/latest
docker compose exec worker python scripts/backup_db.py --no-prune
docker compose exec worker python scripts/restore_check.py
EOF
