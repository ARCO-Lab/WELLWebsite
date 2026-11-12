#!/usr/bin/env bash
# shellcheck disable=SC2016,SC2034  # check's conditions are single-quoted on purpose: check evals them later, so
# their variables (such as restored) are read then, not where they're written
# Tests wordpress/backup.sh. By default against stub `docker` and `curl` commands: the stub runs the script's
# in-container command with a fake mysqldump and a made-up password, so the quoting that keeps the password out of
# the host is tested for real. Nothing real is backed up or contacted.
#   bash .github/scripts/test_wordpress_backup.sh
# With --real it also backs up a throwaway MySQL 5.7 container (no network) seeded with a small WordPress-like
# database, and runs the script's --restore-check on the result. Needs Docker and the mysql:5.7 image.
#   bash .github/scripts/test_wordpress_backup.sh --real
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SCRIPT=$ROOT/wordpress/backup.sh
T=$(mktemp -d)
REAL_DB=""
trap 'if [ -n "$REAL_DB" ]; then docker rm -f "$REAL_DB" >/dev/null 2>&1; fi; rm -rf "$T"' EXIT

mkdir -p "$T/bin" "$T/container-bin" "$T/uploads/2026/11"
echo "photo" > "$T/uploads/2026/11/creek.jpg"
# The db container's own variables, which only the in-container command may read
CONTAINER_SECRET="container-secret-$$"
cat > "$T/bin/docker" <<'EOF'
#!/bin/sh
echo "docker $*" >> "$STUB_LOG"
case "$1 $2" in
  "compose ps") [ -n "${NO_DB:-}" ] || echo "id-db" ;;
  "exec id-db")
    [ "$3" = "sh" ] && [ "$4" = "-c" ] || exit 1
    exec env -i PATH="$T/container-bin:/usr/bin:/bin" MYSQL_ROOT_PASSWORD="$CONTAINER_SECRET" MYSQL_DATABASE=wordpress \
      T="$T" STUB_LOG="$STUB_LOG" DUMP="${DUMP:-ok}" sh -c "$5" ;;
esac
exit 0
EOF
# Fake mysqldump: insists on the password from MYSQL_PWD (as the real one would fail to log in without it)
cat > "$T/container-bin/mysqldump" <<'EOF'
#!/bin/sh
echo "mysqldump $*" >> "$STUB_LOG"
echo "mysqldump env MYSQL_PWD set: ${MYSQL_PWD:+yes}" >> "$STUB_LOG"
if [ "$MYSQL_PWD" != "$MYSQL_ROOT_PASSWORD" ] || [ "$DUMP" = denied ]; then
  echo "mysqldump: Got error: 1045: Access denied for user 'root'@'localhost' (using password: NO)" >&2; exit 2
fi
echo "-- MySQL dump 10.13"
[ "$DUMP" = no-options ] || echo 'CREATE TABLE `wp_options` (option_id int);'
echo 'CREATE TABLE `wp_posts` (ID int);'
[ "$DUMP" = truncated ] && exit 0
[ "$DUMP" = no-options ] && echo 'CREATE TABLE `wp_other` (x int);'
echo "-- Dump completed on 2026-11-11  3:45:00"
EOF
cat > "$T/bin/curl" <<'EOF'
#!/bin/sh
data="" url=""
while [ $# -gt 0 ]; do
  case "$1" in --data-raw) data=$2; shift ;; http*) url=$1 ;; esac
  shift
done
echo "ping $url $data" >> "$STUB_LOG"
EOF
chmod +x "$T/bin/docker" "$T/bin/curl" "$T/container-bin/mysqldump"
export T CONTAINER_SECRET STUB_LOG=$T/stub.log DOCKER=$T/bin/docker CURL=$T/bin/curl WP_UPLOADS_DIR=$T/uploads \
  WP_BACKUP_DIR=$T/backups WP_BACKUP_MIN_FREE_MB=0 WP_BACKUP_LOCK_WAIT=1 HEALTHCHECK_URL_WP_BACKUP=http://hc.test/x
B=$T/backups

reset() { rm -rf "$B"; : > "$STUB_LOG"; }
# Runs the script from another folder, with cron's minimal environment plus the test's settings (and EXTRA:
# more NAME=value settings, separated by spaces)
# shellcheck disable=SC2086  # EXTRA is split into words on purpose
run() {
  (cd / && env -i HOME="$T" PATH=/usr/bin:/bin T="$T" CONTAINER_SECRET="$CONTAINER_SECRET" STUB_LOG="$STUB_LOG" \
    DOCKER="$DOCKER" CURL="$CURL" WP_UPLOADS_DIR="$WP_UPLOADS_DIR" WP_BACKUP_DIR="$WP_BACKUP_DIR" \
    WP_BACKUP_MIN_FREE_MB="$WP_BACKUP_MIN_FREE_MB" WP_BACKUP_LOCK_WAIT="$WP_BACKUP_LOCK_WAIT" \
    HEALTHCHECK_URL_WP_BACKUP="${HC-$HEALTHCHECK_URL_WP_BACKUP}" DUMP="${DUMP:-ok}" NO_DB="${NO_DB:-}" \
    ${EXTRA:-} bash "$SCRIPT" "$@") > "$T/out" 2>&1
  echo $? > "$T/rc"
}
rc() { [ "$(cat "$T/rc")" = "$1" ]; }
said() { grep -qF -- "$1" "$T/out"; }
ran() { grep -qF -- "$1" "$STUB_LOG"; }
count() { find "$B" -maxdepth 1 -name "$1" | wc -l; }
# Backup files with the given stamps (empty, for retention tests)
make_backups() {
  local s; mkdir -p "$B"
  for s in "$@"; do : > "$B/wordpress-db-$s.sql.gz"; : > "$B/wordpress-uploads-$s.tar.gz"; done
  chmod 600 "$B"/wordpress-*
}
has() { [ -e "$B/wordpress-db-$1.sql.gz" ] && [ -e "$B/wordpress-uploads-$1.tar.gz" ]; }
gone() { [ ! -e "$B/wordpress-db-$1.sql.gz" ] && [ ! -e "$B/wordpress-uploads-$1.tar.gz" ]; }

pass=0 failures=0
check() {
  if eval "$2"; then echo "PASS  $1"; pass=$((pass + 1))
  else echo "FAIL  $1"; echo "      output: $(tr '\n' ' ' < "$T/out" | cut -c1-400)"; failures=$((failures + 1)); fi
}

reset; run
check "backup: succeeds, writes one database dump and one uploads archive" 'rc 0 && [ "$(count "wordpress-db-*.sql.gz")" = 1 ] && [ "$(count "wordpress-uploads-*.tar.gz")" = 1 ]'
check "backup: the folder is 0700 and both files 0600" '[ "$(stat -c %a "$B")" = 700 ] && [ -z "$(find "$B" -maxdepth 1 -type f ! -perm 600)" ]'
check "backup: no .partial or .err file left" '[ "$(count ".*.partial")" = 0 ] && [ "$(count ".*.err")" = 0 ]'
check "backup: mysqldump gets the password from MYSQL_PWD in the container, as root, with --single-transaction" 'ran "MYSQL_PWD set: yes" && ran "mysqldump --user=root --single-transaction" && ran " wordpress"'
check "backup: the password is never on a command line, in the output or in a backup" '! grep -qF "$CONTAINER_SECRET" "$STUB_LOG" "$T/out" && ! zgrep -qF "$CONTAINER_SECRET" "$B"/wordpress-db-*.sql.gz'
check "backup: the uploads archive holds the uploads" 'tar -tzf "$B"/wordpress-uploads-*.tar.gz | grep -qx "uploads/2026/11/creek.jpg"'
check "backup: pings /start, then success with a summary" 'ran "ping http://hc.test/x/start" && ran "ping http://hc.test/x WordPress backup" && ! ran "/fail"'
check "backup: ends with the retention line" 'said "Retention: 1 backups kept"'

reset; DUMP=denied run
check "mysqldump fails: exit 1, its error in the message and the /fail ping, nothing left behind" 'rc 1 && said "mysqldump failed" && said "Access denied" && ran "ping http://hc.test/x/fail mysqldump failed" && [ -z "$(ls -A "$B" | grep -v "^.backup.lock$")" ]'

reset; DUMP=truncated run
check "a dump cut short (no closing line): fails, no backup kept" 'rc 1 && said "cut short" && ran "/fail" && [ "$(count "wordpress-*")" = 0 ]'

reset; DUMP=no-options run
check "a dump with no options table: fails" 'rc 1 && said "no options table"'

reset; NO_DB=1 run
check "db container not running: fails and says so" 'rc 1 && said "the db container isn'"'"'t running" && ran "/fail"'

reset; WP_UPLOADS_DIR=$T/nowhere run
check "uploads folder missing: fails before dumping" 'rc 1 && said "doesn'"'"'t exist" && ! ran "mysqldump"'

# tar fails (exit 2) on an upload the cron user can't read. Skipped as root, which can read anything.
if [ "$(id -u)" != 0 ]; then
  reset; make_backups 20200101-0000; mkdir -p "$T/locked-uploads"; echo x > "$T/locked-uploads/private.jpg"
  chmod 000 "$T/locked-uploads/private.jpg"
  WP_UPLOADS_DIR=$T/locked-uploads run
  check "uploads archive fails: exit 1 and a /fail ping naming it, the checked dump kept" 'rc 1 && said "the uploads archive failed" && said "Permission denied" && ran "ping http://hc.test/x/fail the uploads archive failed" && [ "$(count "wordpress-db-*.sql.gz")" = 2 ] && [ -z "$(find "$B" -maxdepth 1 -name "wordpress-db-*.sql.gz" ! -perm 600)" ]'
  check "uploads archive fails: no archive or .partial left, and no retention run" '[ "$(count "wordpress-uploads-*.tar.gz")" = 1 ] && [ "$(count ".*.partial")" = 0 ] && [ "$(count ".*.err")" = 0 ] && has 20200101-0000 && ! said "Retention:"'
  chmod 644 "$T/locked-uploads/private.jpg"
fi

reset; HC="" run
check "no HEALTHCHECK_URL_WP_BACKUP: backs up, pings nothing" 'rc 0 && ! ran "ping"'

reset; mkdir -p "$B"; : > "$B/.wordpress-db-20261110-0345.sql.gz.partial"; : > "$B/.mysqldump-20261110-0345.err"; run
check "an unfinished file from a killed run: deleted by the next run" 'rc 0 && said "left unfinished" && [ ! -e "$B/.wordpress-db-20261110-0345.sql.gz.partial" ] && [ ! -e "$B/.mysqldump-20261110-0345.err" ]'

reset; mkdir -p "$B"; (flock 9; sleep 3) 9>>"$B/.backup.lock" & sleep 0.5; run; wait
check "another run holds the lock: waits WP_BACKUP_LOCK_WAIT, then fails and says so" 'rc 1 && said "held" && ran "/fail" && ! ran "mysqldump"'

reset; EXTRA=WP_BACKUP_KEEP_DAILY=0 run
check "a bad retention setting: fails before doing anything" 'rc 1 && said "WP_BACKUP_KEEP_DAILY must be a whole number of at least 1" && ! ran "mysqldump"'

reset; EXTRA=WP_BACKUP_MIN_FREE_MB=999999999 run
check "not enough disk space: fails before dumping" 'rc 1 && said "not enough disk space" && ! ran "mysqldump"'

# Retention, 2 days / 2 ISO weeks / 2 months. 2026-11-11 is a Wednesday: Nov 9-11 are week 46, Nov 8 ends week 45,
# Nov 1 and Oct 31 are in week 44.
reset; make_backups 20261111-0345 20261111-0200 20261110-0345 20261109-0345 20261108-0345 20261101-0345 \
  20261031-0345 20261015-0345 20260915-0345
mkdir -p "$B"; : > "$B/wordpress-db-before-update.sql.gz"; : > "$B/wordpress-db-20261399-0000.sql.gz"; : > "$B/notes.txt"
: > "$B/wordpress-uploads-20250101-0000.tar.gz"   # an archive whose dump was deleted by hand
EXTRA="WP_BACKUP_KEEP_DAILY=2 WP_BACKUP_KEEP_WEEKLY=2 WP_BACKUP_KEEP_MONTHLY=2" run --prune-only
check "retention keeps the newest per day (2), per ISO week (2) and per month (2)" 'rc 0 && has 20261111-0345 && has 20261110-0345 && has 20261108-0345 && has 20261031-0345'
check "retention deletes the rest, both files of each" 'gone 20261111-0200 && gone 20261109-0345 && gone 20261101-0345 && gone 20261015-0345 && gone 20260915-0345 && gone 20250101-0000'
check "retention leaves other files alone (other names, impossible dates)" '[ -e "$B/wordpress-db-before-update.sql.gz" ] && [ -e "$B/wordpress-db-20261399-0000.sql.gz" ] && [ -e "$B/notes.txt" ]'
check "--prune-only: no dump, no pings" '! ran "mysqldump" && ! ran "ping" && said "4 backups kept" && said "6 deleted"'

reset; make_backups 20200101-0000; run --no-prune
check "--no-prune: backs up and deletes nothing" 'rc 0 && has 20200101-0000 && [ "$(count "wordpress-db-*.sql.gz")" = 2 ]'

reset; run --restore-check
check "--restore-check with no backups: fails and pings nothing" 'rc 1 && said "no backups" && ! ran "ping"'

reset; mkdir -p "$B"; : > "$B/wordpress-db-20261111-0345.sql.gz"; run --restore-check 20261111-0345
check "--restore-check of a backup with no uploads archive: says so, still checks the dump" 'rc 1 && said "has no uploads archive" && said "doesn'"'"'t decompress"'

if [ "${1:-}" = --real ]; then
  # A throwaway MySQL 5.7 with no network, as on the VM, holding a small WordPress-like database
  REAL_DB=wp-backup-test-$$
  REAL_SECRET="real-secret-$$"
  docker run -d --rm --name "$REAL_DB" --network none -e MYSQL_ROOT_PASSWORD="$REAL_SECRET" -e MYSQL_DATABASE=wordpress \
    mysql:5.7 > /dev/null
  for _ in $(seq 1 300); do docker logs "$REAL_DB" 2>&1 | grep '^Version: .*port: 3306 ' >/dev/null && break; sleep 1; done
  docker exec -i "$REAL_DB" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 wordpress' <<'SQL'
CREATE TABLE wp_options (option_id bigint AUTO_INCREMENT PRIMARY KEY, option_name varchar(191) UNIQUE, option_value longtext) DEFAULT CHARSET=utf8mb4;
INSERT INTO wp_options (option_name, option_value) VALUES ('siteurl', 'https://example.test'), ('blogname', 'Café ☔');
CREATE TABLE wp_posts (ID bigint AUTO_INCREMENT PRIMARY KEY, post_title text) DEFAULT CHARSET=utf8mb4;
INSERT INTO wp_posts (post_title) VALUES ('First'), ('Second'), ('Third');
SQL
  reset
  (cd / && env DOCKER=docker CURL=curl HEALTHCHECK_URL_WP_BACKUP="" WP_DB_CONTAINER="$REAL_DB" bash "$SCRIPT") > "$T/out" 2>&1
  echo $? > "$T/rc"
  check "real MySQL 5.7: backup succeeds with both tables" 'rc 0 && said "(2 tables)"'
  check "real MySQL 5.7: the dump keeps UTF-8 text and holds no password" 'zgrep -qF "Café ☔" "$B"/wordpress-db-*.sql.gz && ! zgrep -qF "$REAL_SECRET" "$B"/wordpress-db-*.sql.gz && ! said "$REAL_SECRET"'
  (cd / && env DOCKER=docker WP_DB_CONTAINER="$REAL_DB" bash "$SCRIPT" --restore-check) > "$T/out" 2>&1
  echo $? > "$T/rc"
  check "real MySQL 5.7: --restore-check loads it into a throwaway container and passes" 'rc 0 && said "Restore check passed" && said "siteurl https://example.test" && said "3 rows in wp_posts"'
  check "real MySQL 5.7: --restore-check deletes its container" '[ -z "$(docker ps -aq --filter "name=^wp-restore-check-")" ]'
  # A copy of the dump cut short, under a newer stamp
  stamp=$(find "$B" -maxdepth 1 -name 'wordpress-db-*.sql.gz' -printf '%f\n' | sed -n 's/^wordpress-db-\(.*\)\.sql\.gz$/\1/p' | head -1)
  gzip -dc "$B/wordpress-db-$stamp.sql.gz" | head -n -1 | gzip > "$B/wordpress-db-29991231-2359.sql.gz"
  cp "$B/wordpress-uploads-$stamp.tar.gz" "$B/wordpress-uploads-29991231-2359.tar.gz"
  (cd / && env DOCKER=docker WP_DB_CONTAINER="$REAL_DB" bash "$SCRIPT" --restore-check) > "$T/out" 2>&1
  echo $? > "$T/rc"
  check "real MySQL 5.7: --restore-check fails on a dump cut short" 'rc 1 && said "cut short"'

  # "Restoring for real" in wordpress/README.md, with `docker exec <container>` for `docker compose exec db`, and
  # `docker run` of an image that runs as root for `docker compose run ... wordpress`: after a post is deleted, a
  # table added and a file uploaded, the restore brings back exactly the backed-up database and uploads. The live
  # uploads folder belongs to www-data (uid 33) here, as when WordPress writes its own uploads, so the restored folder
  # must get that owner back, and the old folder (which the test user can't delete) goes through the container.
  as_root() { docker run --rm -v "$site/home:/var/www/html" --entrypoint "$1" mysql:5.7 "${@:2}"; }
  rm -f "$B/wordpress-db-29991231-2359.sql.gz" "$B/wordpress-uploads-29991231-2359.tar.gz"
  docker exec "$REAL_DB" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot wordpress -e "DELETE FROM wp_posts WHERE ID = 1; CREATE TABLE wp_junk (x int)"'
  site=$T/site && mkdir -p "$site/home/wp-content/uploads" && echo "new" > "$site/home/wp-content/uploads/added-later.jpg"
  as_root chown -R 33:33 /var/www/html/wp-content/uploads
  (
    set -e
    cd "$site"
    STAMP=$stamp
    docker exec -i "$REAL_DB" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "DROP DATABASE IF EXISTS \`$MYSQL_DATABASE\`; CREATE DATABASE \`$MYSQL_DATABASE\` DEFAULT CHARACTER SET utf8mb4"'
    gunzip -c "$B/wordpress-db-$STAMP.sql.gz" | docker exec -i "$REAL_DB" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 "$MYSQL_DATABASE"'
    OWNER=$(stat -c %u:%g home/wp-content/uploads)
    mv home/wp-content/uploads home/wp-content/uploads.before-restore
    tar -p -C home/wp-content -xzf "$B/wordpress-uploads-$STAMP.tar.gz"
    as_root chown -R "$OWNER" /var/www/html/wp-content/uploads
    [ "$(stat -c %u:%g home/wp-content/uploads.before-restore/added-later.jpg)" = 33:33 ]   # checked before it goes
    as_root rm -rf /var/www/html/wp-content/uploads.before-restore
  ) > "$T/out" 2>&1
  echo $? > "$T/rc"
  restored=$(docker exec "$REAL_DB" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 -N -B wordpress -e "SELECT COUNT(*) FROM wp_posts; SHOW TABLES LIKE \"wp_junk\"; SELECT option_value FROM wp_options WHERE option_name = \"blogname\""' 2>&1 | tr '\n' '|')
  check "real MySQL 5.7: the README's restore steps bring back the database (rows, no extra table, UTF-8)" 'rc 0 && [ "$restored" = "3|Café ☔|" ]'
  check "real MySQL 5.7: the README's restore steps bring back the uploads, owned by the old folder's owner (uid 33)" '[ -f "$site/home/wp-content/uploads/2026/11/creek.jpg" ] && [ ! -e "$site/home/wp-content/uploads/added-later.jpg" ] && [ -z "$(find "$site/home/wp-content/uploads" ! -uid 33)" ]'
  check "real MySQL 5.7: the README's restore steps delete the old www-data folder through the container" '[ ! -e "$site/home/wp-content/uploads.before-restore" ]'
  as_root chown -R "$(id -u):$(id -g)" /var/www/html/wp-content   # so the test's own cleanup can delete it
fi

echo "$pass passed, $failures failed"
[ "$failures" = 0 ]
