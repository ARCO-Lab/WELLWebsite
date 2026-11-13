#!/usr/bin/env bash
# Prints, and never runs, the steps that move the WELL containers off the PostgreSQL superuser onto the roles in
# roles.sql (well_app and well_ops). Each step needs sudo on the VM and is meant to be read and run by hand, one at
# a time; the backend README's "Database roles" section explains each, and how to roll back.
#
#   dashboard/backend/app/db/roles.sh <database>      e.g. roles.sh welldb (the name at the end of BACKEND_DATABASE_URL)
set -euo pipefail

if [ $# -ne 1 ] || ! [[ $1 =~ ^[a-z_][a-z0-9_]*$ ]]; then
  echo "usage: $0 <database>   (the WELL database's name: lowercase letters, digits and _)" >&2
  exit 2
fi
db=$1

cat <<EOF
# Run from ~/WELLWebsite, one step at a time. Nothing here has been run.

# 1. A backup first, as the app connects today.
docker compose exec worker python scripts/backup_db.py --no-prune

# 2. Create the roles and hand the tables to well_app (safe to run again). Then check.
sudo -u postgres psql -d $db -v ON_ERROR_STOP=1 < dashboard/backend/app/db/roles.sql
sudo -u postgres psql -d $db -v ON_ERROR_STOP=1 < dashboard/backend/app/db/roles_check.sql

# 3. A password for each role, stored as SCRAM. Generate them with: openssl rand -hex 24
sudo -u postgres psql -d $db -c "SET password_encryption = 'scram-sha-256'" -c '\\password well_app'
sudo -u postgres psql -d $db -c "SET password_encryption = 'scram-sha-256'" -c '\\password well_ops'

# 4. pg_hba.conf: allow the two roles from the Docker networks by password, reject everything else from there
#    (postgres included). Its path: sudo -u postgres psql -tAc 'SHOW hba_file'. Keep a copy, edit, then reload:
#      host  $db,welldb_restore_check  well_app  10.20.0.0/16  scram-sha-256
#      host  $db                       well_ops  10.20.0.0/16  scram-sha-256
#      host  all                       all       10.20.0.0/16  reject
#    These go above any other line that matches 10.20.0.0/16 (the first matching line wins); replace the old one.
sudo -u postgres psql -c 'SELECT pg_reload_conf()'
sudo -u postgres psql -c "SELECT line_number, database, user_name, address, auth_method, error FROM pg_hba_file_rules WHERE address = '10.20.0.0'"

# 5. Point the containers at the roles: keep a copy of .env, edit it, recreate the containers.
#      BACKEND_DATABASE_URL=postgresql://well_app:<password>@host.docker.internal:5432/$db
#      OPS_DATABASE_URL=postgresql://well_ops:<password>@host.docker.internal:5432/$db
(umask 077 && cp -p .env .env.before-db-roles)
docker compose up -d --no-deps backend worker export_worker
docker compose up -d --no-deps ops                   # only if welldash² runs

# 6. Check: which roles are connected (no postgres from 10.20.x.x), the API reads the database (200), and a
#    backup made as well_app leaves nothing out (no WARNING line).
sudo -u postgres psql -d $db -c "SELECT usename, application_name, client_addr, count(*) FROM pg_stat_activity WHERE datname = '$db' GROUP BY 1, 2, 3 ORDER BY 1, 2"
docker compose exec backend curl -fsS -o /dev/null -w '%{http_code}\\n' -H 'X-Welldash2-Probe: 1' http://localhost:5000/api/latest
docker compose exec worker python scripts/backup_db.py --no-prune
EOF
