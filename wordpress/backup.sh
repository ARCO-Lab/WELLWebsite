#!/usr/bin/env bash
# Backs up the WordPress site: its MySQL database (mysqldump --single-transaction, run inside the `db` container) and
# the media library (home/wp-content/uploads, as a tar). Both are checked, then kept in WP_BACKUP_DIR, readable by
# their owner only, and old backups are deleted. Run nightly from cron on the VM (see wordpress/README.md); it can
# also be run by hand.
#
#   wordpress/backup.sh                         back up now, then apply retention
#   wordpress/backup.sh --no-prune              back up, delete nothing
#   wordpress/backup.sh --prune-only            apply retention to the existing backups only
#   wordpress/backup.sh --restore-check [STAMP] load the newest backup (or the one stamped YYYYmmdd-HHMM) into a
#                                               throwaway MySQL container with no network, check it, delete the
#                                               container; changes nothing else and pings nothing
#
# Settings (environment, all optional):
#   WP_BACKUP_DIR              where backups go (default wp-backups/ in the repository root, gitignored)
#   WP_BACKUP_KEEP_DAILY       how many days keep their newest backup (default 7)
#   WP_BACKUP_KEEP_WEEKLY      how many ISO weeks keep their newest backup (default 8)
#   WP_BACKUP_KEEP_MONTHLY     how many months keep their newest backup (default 12)
#   WP_BACKUP_MIN_FREE_MB      free space to leave on the disk after a backup the size of the last one (default 2048)
#   HEALTHCHECK_URL_WP_BACKUP  a Healthchecks.io ping URL: <url>/start when a backup begins, <url> when it succeeds,
#                              <url>/fail (with the reason) when it fails
# DOCKER, CURL, WP_DB_CONTAINER, WP_UPLOADS_DIR, WP_RESTORE_IMAGE and WP_BACKUP_LOCK_WAIT exist for tests.
#
# A backup is two files with the same Toronto-time stamp: wordpress-db-YYYYmmdd-HHMM.sql.gz and
# wordpress-uploads-YYYYmmdd-HHMM.tar.gz. Each is written as a hidden .partial file and renamed only once it has
# passed its check, so a failed run leaves nothing that looks like a good file. The dump is checked and kept first: if
# the uploads archive then fails, the run fails (exit 1, /fail ping) but keeps the dump. Only files with those names
# are ever deleted, both files of a backup together. The database password stays in the db container: mysqldump
# reads it from the container's own environment, so it is never on a command line or in the output.
set -Eeuo pipefail

MODE=backup PRUNE=1 STAMP_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --no-prune) PRUNE=0 ;;
    --prune-only) MODE=prune ;;
    --restore-check)
      MODE=restore-check
      if [ $# -gt 1 ] && [[ "$2" != -* ]]; then STAMP_ARG=$2; shift; fi ;;
    -h|--help) sed -n '2,29p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# cron starts with a minimal PATH and the home directory as working directory
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
ROOT=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
cd "$ROOT"
DIR=${WP_BACKUP_DIR:-$ROOT/wp-backups}
UPLOADS=${WP_UPLOADS_DIR:-$ROOT/home/wp-content/uploads}
DOCKER=${DOCKER:-docker}
CURL=${CURL:-curl}
SITE_TZ=America/Toronto
DB_PREFIX=wordpress-db- DB_SUFFIX=.sql.gz
UP_PREFIX=wordpress-uploads- UP_SUFFIX=.tar.gz
declare -A WHAT=([backup]="WordPress backup" [prune]="WordPress backup retention" [restore-check]="WordPress restore check")

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }
warn() { log "WARNING: $*" >&2; }
# Pings HEALTHCHECK_URL_WP_BACKUP (if set, and only for a backup run) with the suffix in $1 ("" for success, /start,
# /fail) and the message in $2 as the body; a failed ping never changes the outcome.
ping_hc() {
  [ "$MODE" = backup ] && [ -n "${HEALTHCHECK_URL_WP_BACKUP:-}" ] || return 0
  "$CURL" -fsS -m 10 --retry 3 -o /dev/null --data-raw "${2:-}" "$HEALTHCHECK_URL_WP_BACKUP$1" || true
}
PARTIALS=() RESTORE_CONTAINER=""
# shellcheck disable=SC2329  # called by the EXIT trap below
cleanup() {
  local p
  for p in "${PARTIALS[@]}"; do rm -f "$p"; done
  if [ -n "$RESTORE_CONTAINER" ]; then "$DOCKER" rm -f "$RESTORE_CONTAINER" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT
# Reports the failure ($*) and ends the run. Only ever called from the main shell, not from inside $(...), so a
# failure is reported and pinged once.
die() {
  trap - ERR
  log "ERROR: ${WHAT[$MODE]} failed: $*" >&2
  ping_hc /fail "$*"
  exit 1
}
# A command that fails unexpectedly still ends in an ERROR line and a /fail ping. In a subshell it only exits with
# the command's status, so the main shell reports it, once.
# shellcheck disable=SC2329  # called by the ERR trap below
on_err() {
  [ "$BASHPID" = "$$" ] || exit "$1"
  die "line $2: $3 failed"
}
trap 'on_err $? "$LINENO" "$BASH_COMMAND"' ERR
trap 'die "stopped by a signal"' INT TERM HUP

# Sets variable $1 from the whole-number setting $2 (default $3, at least $4); a bad value stops the run rather than
# being guessed.
int_setting() {
  local raw=${!2:-$3}
  if ! [[ "$raw" =~ ^[0-9]+$ ]] || [ "$((10#$raw))" -lt "$4" ]; then die "$2 must be a whole number of at least $4, got '$raw'"; fi
  printf -v "$1" %d "$((10#$raw))"
}
int_setting KEEP_DAILY WP_BACKUP_KEEP_DAILY 7 1
int_setting KEEP_WEEKLY WP_BACKUP_KEEP_WEEKLY 8 0
int_setting KEEP_MONTHLY WP_BACKUP_KEEP_MONTHLY 12 0
int_setting MIN_FREE_MB WP_BACKUP_MIN_FREE_MB 2048 0
int_setting LOCK_WAIT WP_BACKUP_LOCK_WAIT 900 0

# The backup folder is 0700 and every file in it 0600 (the dump holds password hashes and unpublished posts). The
# umask is set only in this subshell and the ones that write backups, never for the whole script.
( umask 077 && mkdir -p "$DIR" && : >> "$DIR/.backup.lock" ) || die "couldn't create $DIR"
chmod 700 "$DIR"
# One run at a time: a second run (cron and a person, or a restore check) waits up to WP_BACKUP_LOCK_WAIT seconds
exec 9>>"$DIR/.backup.lock"
flock -w "$LOCK_WAIT" 9 || die "another backup or restore check held $DIR/.backup.lock for more than ${LOCK_WAIT}s"

# The stamps (YYYYmmdd-HHMM) of the backups in $DIR, newest first. Names with an impossible date are left out, so
# they are never deleted.
stamps() {
  local f s
  for f in "$DIR/$DB_PREFIX"*"$DB_SUFFIX" "$DIR/$UP_PREFIX"*"$UP_SUFFIX"; do
    [ -e "$f" ] || continue
    s=${f##*/}; s=${s#"$DB_PREFIX"}; s=${s#"$UP_PREFIX"}; s=${s%"$DB_SUFFIX"}; s=${s%"$UP_SUFFIX"}
    if [[ "$s" =~ ^[0-9]{8}-[0-9]{4}$ ]] && date -d "${s:0:8} ${s:9:2}:${s:11:2}" >/dev/null 2>&1; then echo "$s"; fi
  done | sort -ru
}

# The stamps retention deletes: all but the newest backup of each of the KEEP_DAILY most recent days that have one,
# of each of the KEEP_WEEKLY most recent ISO weeks, and of each of the KEEP_MONTHLY most recent months.
stamps_to_prune() {
  local s day week month keep
  local -A days=() weeks=() months=()
  while read -r s; do
    [ -n "$s" ] || continue
    day=${s:0:8} month=${s:0:6} keep=0
    week=$(date -d "$day" +%G-%V)
    if [ -z "${days[$day]-}" ] && [ "${#days[@]}" -lt "$KEEP_DAILY" ]; then days[$day]=1; keep=1; fi
    if [ -z "${weeks[$week]-}" ] && [ "${#weeks[@]}" -lt "$KEEP_WEEKLY" ]; then weeks[$week]=1; keep=1; fi
    if [ -z "${months[$month]-}" ] && [ "${#months[@]}" -lt "$KEEP_MONTHLY" ]; then months[$month]=1; keep=1; fi
    if [ "$keep" = 0 ]; then echo "$s"; fi
  done < <(stamps)
}

# Deletes the backups retention doesn't keep. Returns 1 if a file couldn't be deleted.
prune() {
  local s n=0 total doomed
  total=$(stamps | wc -l)
  doomed=$(stamps_to_prune)
  for s in $doomed; do
    rm -f "$DIR/$DB_PREFIX$s$DB_SUFFIX" "$DIR/$UP_PREFIX$s$UP_SUFFIX" || return 1
    log "Deleted old backup $s"
    n=$((n + 1))
  done
  log "Retention: $((total - n)) backups kept (newest per day for $KEEP_DAILY days, per week for $KEEP_WEEKLY weeks," \
    "per month for $KEEP_MONTHLY months), $n deleted."
}

human() { numfmt --to=iec --suffix=B "$1" 2>/dev/null || echo "$1 bytes"; }

# Sets DB to the running db container: WP_DB_CONTAINER, or compose's `db` service in this checkout
find_db() {
  DB=${WP_DB_CONTAINER:-}
  [ -n "$DB" ] || DB=$("$DOCKER" compose ps -q db 2>/dev/null | sed -n 1p || true)
  [ -n "$DB" ] || die "the db container isn't running (docker compose ps -q db found nothing in $ROOT)"
}

# Checks a gzipped dump: it decompresses in full, mysqldump's closing line is there (a dump cut short has none), and
# it creates the options table every WordPress database has. Prints the number of tables, or the reason and returns 1.
# (grep reads to the end rather than -q, which would stop early and make gzip fail under pipefail.)
# shellcheck disable=SC2016  # the backticks are MySQL's quoting, matched literally
check_dump() {
  local tables
  gzip -t "$1" 2>/dev/null || { echo "the dump doesn't decompress"; return 1; }
  gzip -dc "$1" | tail -n 1 | grep '^-- Dump completed' >/dev/null \
    || { echo "the dump has no '-- Dump completed' line at the end, so it is cut short"; return 1; }
  tables=$(gzip -dc "$1" | grep -c '^CREATE TABLE `' || true)
  gzip -dc "$1" | grep -E '^CREATE TABLE `[A-Za-z0-9_]*options`' >/dev/null \
    || { echo "the dump has no options table ($tables tables)"; return 1; }
  echo "$tables"
}

back_up() {
  local stamp db_final up_final db_part up_part err prev=0 free need tables files rc s
  # Unfinished files left by a run that was killed (the EXIT trap removes this run's own)
  for s in "$DIR"/.wordpress-*.partial "$DIR"/.mysqldump-*.err; do
    [ -e "$s" ] || continue
    rm -f "$s"
    log "Deleted ${s##*/}, left unfinished by an earlier run that was stopped"
  done
  [ -d "$UPLOADS" ] || die "the uploads folder $UPLOADS doesn't exist"

  # Refuse to start if a backup the size of the last one would leave less than WP_BACKUP_MIN_FREE_MB free
  s=$(stamps | sed -n 1p)
  if [ -n "$s" ]; then
    prev=$(( $(stat -c %s "$DIR/$DB_PREFIX$s$DB_SUFFIX" 2>/dev/null || echo 0) + $(stat -c %s "$DIR/$UP_PREFIX$s$UP_SUFFIX" 2>/dev/null || echo 0) ))
  fi
  free=$(( $(df -Pk "$DIR" | awk 'NR==2 {print $4}') * 1024 ))
  need=$(( prev + MIN_FREE_MB * 1024 * 1024 ))
  if [ "$free" -lt "$need" ]; then
    die "not enough disk space in $DIR: $(human "$free") free, but a backup like the last one ($(human "$prev")) plus WP_BACKUP_MIN_FREE_MB=$MIN_FREE_MB needs $(human "$need")"
  fi

  stamp=$(TZ=$SITE_TZ date +%Y%m%d-%H%M)
  db_final=$DIR/$DB_PREFIX$stamp$DB_SUFFIX up_final=$DIR/$UP_PREFIX$stamp$UP_SUFFIX
  if [ -e "$db_final" ] || [ -e "$up_final" ]; then die "a backup stamped $stamp already exists; try again in a minute"; fi
  db_part=$DIR/.$DB_PREFIX$stamp$DB_SUFFIX.partial up_part=$DIR/.$UP_PREFIX$stamp$UP_SUFFIX.partial
  err=$DIR/.mysqldump-$stamp.err
  PARTIALS=("$db_part" "$up_part" "$err")
  find_db

  # The single-quoted script runs in the container: $MYSQL_ROOT_PASSWORD and $MYSQL_DATABASE are the container's own
  # variables (set by docker-compose.yml), and MYSQL_PWD hands the password to mysqldump without a command-line
  # argument. --single-transaction gives a consistent snapshot of the InnoDB tables without locking the site.
  log "Dumping the WordPress database (container ${DB:0:12}) to ${db_final##*/}"
  # shellcheck disable=SC2016  # expanded by sh inside the container, not here
  if ! ( umask 077 && "$DOCKER" exec "$DB" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump --user=root \
          --single-transaction --quick --routines --triggers --events --hex-blob --no-tablespaces \
          --default-character-set=utf8mb4 "${MYSQL_DATABASE:?is not set in the db container}"' 2>"$err" \
        | gzip -6 > "$db_part" ); then
    die "mysqldump failed: $(tail -c 1500 "$err" | tr '\n' ' ')"
  fi
  if ! tables=$(check_dump "$db_part"); then die "$tables"; fi

  # The dump has passed its check, so it is kept even if the uploads archive fails below
  chmod 600 "$db_part"
  mv "$db_part" "$db_final"
  PARTIALS=("$up_part" "$err")

  log "Archiving ${UPLOADS#"$ROOT"/}"
  rc=0
  ( umask 077 && tar -C "$(dirname "$UPLOADS")" -czf "$up_part" "$(basename "$UPLOADS")" 2>"$err" ) || rc=$?
  # GNU tar exits 1 when a file changed while it was read (an upload during the backup): the archive is still
  # complete apart from that file, so that is a warning. Anything else (e.g. a file the cron user can't read) fails
  # the run, with the database dump kept.
  if [ "$rc" = 1 ]; then
    warn "tar: $(tail -c 500 "$err" | tr '\n' ' ')"
  elif [ "$rc" != 0 ]; then
    die "the uploads archive failed (tar exit $rc: $(tail -c 1500 "$err" | tr '\n' ' ')); the database dump is kept as ${db_final##*/}"
  fi
  files=$(tar -tzf "$up_part" 2>/dev/null | wc -l) \
    || die "the uploads archive doesn't read back; the database dump is kept as ${db_final##*/}"

  chmod 600 "$up_part"
  mv "$up_part" "$up_final"
  rm -f "$err"
  PARTIALS=()
  SUMMARY="WordPress backup $stamp: database $(human "$(stat -c %s "$db_final")") ($tables tables), uploads $(human "$(stat -c %s "$up_final")") ($files entries)"
  log "Backup written to $DIR. $SUMMARY"
}

restore_check() {
  local stamp=$STAMP_ARG db_file up_file image name tables options prefix siteurl posts files restored
  [ -n "$stamp" ] || stamp=$(stamps | sed -n 1p)
  [ -n "$stamp" ] || die "no backups in $DIR"
  db_file=$DIR/$DB_PREFIX$stamp$DB_SUFFIX up_file=$DIR/$UP_PREFIX$stamp$UP_SUFFIX
  [ -f "$db_file" ] || die "no database dump $db_file"
  # A backup whose uploads archive failed has only its dump (that run failed and said so); the dump is still checked
  if [ -f "$up_file" ]; then
    files="$(tar -tzf "$up_file" 2>/dev/null | wc -l) entries" || die "the uploads archive $up_file doesn't read back"
  else
    files="none (this backup has no uploads archive)"
    warn "$stamp has no uploads archive (that night's archive failed); checking its database dump only"
  fi
  if ! tables=$(check_dump "$db_file"); then die "$tables"; fi

  # The same MySQL image the site runs (the db container's), unless WP_RESTORE_IMAGE says otherwise
  image=${WP_RESTORE_IMAGE:-}
  if [ -z "$image" ]; then
    find_db
    image=$("$DOCKER" inspect -f '{{.Config.Image}}' "$DB" 2>/dev/null) || die "couldn't read the db container's image"
  fi
  name=wp-restore-check-$$
  log "Restoring $stamp into a throwaway $image container ($name, no network)"
  # No network, so the empty root password is reachable only through docker exec. --rm also removes its data volume.
  RESTORE_CONTAINER=$name
  "$DOCKER" run -d --rm --name "$name" --network none -e MYSQL_ALLOW_EMPTY_PASSWORD=yes "$image" >/dev/null \
    || die "couldn't start a $image container"
  # The image's entrypoint first runs a temporary server to initialize (its Version: line says port: 0), then the real
  # one, whose Version: line (printed after "ready for connections") says port: 3306
  for _ in $(seq 1 300); do
    if "$DOCKER" logs "$name" 2>&1 | grep '^Version: .*port: 3306 ' >/dev/null; then break; fi
    sleep 1
  done
  "$DOCKER" logs "$name" 2>&1 | grep '^Version: .*port: 3306 ' >/dev/null \
    || die "the throwaway MySQL didn't start within 5 minutes"
  "$DOCKER" exec "$name" mysql -uroot -e 'CREATE DATABASE restore_check' || die "couldn't create the throwaway database"
  gzip -dc "$db_file" | "$DOCKER" exec -i "$name" mysql -uroot --default-character-set=utf8mb4 restore_check \
    || die "the dump didn't load into MySQL"
  restored=$(restored_sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'restore_check'")
  [ "$restored" = "$tables" ] || die "the dump creates $tables tables, but $restored were restored"
  options=$(restored_sql "SELECT table_name FROM information_schema.tables WHERE table_schema = 'restore_check' AND table_name LIKE '%options' ORDER BY LENGTH(table_name) LIMIT 1")
  [ -n "$options" ] || die "the restored database has no options table"
  prefix=${options%options}
  siteurl=$(restored_sql "SELECT option_value FROM \`$options\` WHERE option_name = 'siteurl'")
  [ -n "$siteurl" ] || die "the restored $options table has no siteurl"
  posts=$(restored_sql "SELECT COUNT(*) FROM \`${prefix}posts\`" 2>/dev/null || echo "?")
  log "Restore check passed for $stamp: $restored tables restored, siteurl $siteurl, $posts rows in ${prefix}posts;" \
    "uploads archive: $files. The throwaway container is deleted now."
}
# Runs a query ($1) on the restored database and prints the result without headers
restored_sql() { "$DOCKER" exec "$RESTORE_CONTAINER" mysql -uroot -N -B -e "$1" restore_check; }

case "$MODE" in
  prune) prune || die "deleting old backups failed" ;;
  restore-check) restore_check ;;
  backup)
    ping_hc /start ""
    SUMMARY=""
    back_up
    if [ "$PRUNE" = 1 ]; then
      # The new backup is written and checked; the next run's retention tries the old ones again
      prune || warn "the backup is fine, but deleting old backups failed"
    fi
    ping_hc "" "$SUMMARY"
    ;;
esac
