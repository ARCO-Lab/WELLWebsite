#!/usr/bin/env bash
# Deploys the latest `main` to this VM: pulls it, rebuilds only the services whose files changed, checks the
# site is healthy, and rolls back if it isn't. See docs/deploying.md.
#
#   ./deploy.sh            deploy now (asks nothing; you're there)
#   ./deploy.sh --auto     for cron: only deploy a commit whose CI checks all passed, and hold (log, don't
#                          deploy) changes that need a person: DB migrations, docker-compose.yml, a WordPress
#                          core update, and code CI can't vouch for (HOLD_PATHS). Each problem is reported once,
#                          not on every run; a rolled-back commit isn't retried. Prints nothing when there's
#                          nothing to do, except once per commit while it waits for CI.
#   ./deploy.sh --dry-run  show what would happen, change nothing (no log, state or pings)
#
# A deploy that is stopped halfway (Ctrl-C, a reboot, a lost SSH session) is redone by the next run: the commit the
# containers were built from is recorded only after a healthy check, and a marker says a deploy was under way.
#
# Settings (environment, all optional): DEPLOY_BRANCH (main), DEPLOY_REMOTE (origin), DEPLOY_LOG
# (deploy.log next to this script), DEPLOY_HEALTHCHECK_URL (a Healthchecks.io ping URL: success pings it,
# failure pings <url>/fail), GITHUB_REPO (ARCO-Lab/WELLWebsite), DEPLOY_STATE_DIR (.deploy-state next to this
# script: the lock, the reported-problem state, the deployed commit and the rolled-back marker), DEPLOY_SITE_HOST
# (127.0.0.1: the address the health checks call ports 8080 and 8081 on) and DEPLOY_CI_WAIT_HOURS (3: how long
# --auto waits for CI on a commit before reporting it). DOCKER, CURL, GITHUB_API, DEPLOY_STATE, DEPLOY_HEALTH_TRIES,
# DEPLOY_HEALTH_WAIT and DEPLOY_WORKER_WAIT exist for tests.
set -Eeuo pipefail
# Files git writes here (a pull, a rollback) must stay readable by Apache in the wordpress container whatever umask
# the caller has: under umask 077 every changed file in home/ would be 0600 and WordPress would answer 500, and the
# rollback would write the old files 0600 again.
umask 022

AUTO=0 DRY=0
for arg in "$@"; do
  case "$arg" in
    --auto) AUTO=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) awk 'NR > 1 && !/^#/ { exit } NR > 1' "$0"; exit 0 ;;   # the comment block above
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

cd "$(dirname "$(readlink -f "$0")")"
BRANCH=${DEPLOY_BRANCH:-main}
REMOTE=${DEPLOY_REMOTE:-origin}
LOG=${DEPLOY_LOG:-$PWD/deploy.log}
# Not /tmp: RHEL deletes files there after 10 days, which would drop the lock file and the rolled-back marker (so cron
# would retry a commit it had rolled back). The directory is git-ignored.
STATE_DIR=${DEPLOY_STATE_DIR:-$PWD/.deploy-state}
STATE=${DEPLOY_STATE:-$STATE_DIR/state}
# Where the lock and state were kept before; the state is moved once, below
LEGACY=${TMPDIR:-/tmp}/well-deploy
# Written after the first run of this version that ends well (up to date, or deployed and healthy). From then on the
# old lock and state in /tmp are ignored: no run of the previous version can still be going, and /tmp is writable by
# every user, so a lock someone else left there must not be able to stop deploys.
LEGACY_DONE=$STATE_DIR/legacy-retired
SITE_HOST=${DEPLOY_SITE_HOST:-127.0.0.1}
REPO=${GITHUB_REPO:-ARCO-Lab/WELLWebsite}
API=${GITHUB_API:-https://api.github.com}
DOCKER=${DOCKER:-docker}
CURL=${CURL:-curl}
# --auto holds these for a person to deploy with ./deploy.sh: CI and the automation (.github/, which could also make
# a bad change pass CI), this script, code under home/ that is live the moment it is pulled, with no rebuild or test
# (PHP, and JavaScript, HTML and SVG that run in a logged-in administrator's browser, where they could install a
# plugin), wp-config, .htaccess, and everything in wordpress/ (the Apache/PHP config, and backup.sh, which the host's
# cron runs from this checkout). A merged pull request alone is not enough for these, so a change that got past
# review can't go live unattended.
HOLD_PATHS='^\.github/|^deploy\.sh$|^home/.*\.(php|m?js|html?|svg)$|(^|/)wp-config[^/]*$|(^|/)\.htaccess$|^wordpress/'
REQUIRED_CHECKS=("Backend image and tests" "Dashboard build" "Dashboard image" "Deploy script" "End-to-end data (vendors to browser)")  # job names in .github/workflows/ci.yml

# Best effort: an unwritable deploy.log must never stop a deploy halfway (tee still prints the line either way)
log() {
  if [ "$DRY" = 1 ]; then echo "$*"; return 0; fi
  { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; } 2>/dev/null || true
}
# Pings DEPLOY_HEALTHCHECK_URL (if set) with the suffix in $1 ("" for success, /fail); a failed ping is ignored.
ping_health() {
  if [ "$DRY" = 0 ] && [ -n "${DEPLOY_HEALTHCHECK_URL:-}" ]; then
    "$CURL" -fsS -m 10 --retry 3 -o /dev/null "$DEPLOY_HEALTHCHECK_URL$1" || true
  fi
}
fail() { trap - ERR INT TERM HUP; log "FAILED: $*"; ping_health /fail; exit 1; }
# --auto runs every few minutes: report a problem once (keyed by $1), not on every run. The key is cleared by the
# next healthy deploy or up-to-date run, and replaced by any other problem, so new problems are always reported.
once() {
  [ "$DRY" = 1 ] && return 0
  if [ "$AUTO" = 1 ] && [ -f "$STATE" ] && [ "$(cat "$STATE")" = "$1" ]; then exit 0; fi
  { echo "$1" > "$STATE"; } 2>/dev/null || true  # unwritable: the problem is still reported, just not deduplicated
}
clear_state() { [ "$DRY" = 1 ] || rm -f "$STATE"; }
# A command that fails unexpectedly (anywhere: set -E carries the trap into functions and subshells) still gets a
# FAILED line and a /fail ping, reported once per line. In a subshell such as $(...) it only exits with the
# command's status, so the failure is reported once, by the main shell.
# shellcheck disable=SC2329  # called by the ERR trap below
on_err() {
  [ "$BASHPID" = "$$" ] || exit "$1"
  trap - ERR
  once "error at line $2"
  fail "line $2: $3 failed"
}
trap 'on_err $? "$LINENO" "$BASH_COMMAND"' ERR
# The last commit that was deployed and rolled back. Kept apart from $STATE (which `once` overwrites) so no other
# problem can erase it; cleared by a healthy deploy or a deploy by hand.
ROLLED_BACK=$STATE.rolled-back
# The commit the containers were last built from, written only once the site was healthy after that build. The
# checkout's HEAD isn't proof: a deploy stopped between the merge and the rebuild leaves HEAD on the new commit and
# the containers on the old one.
DEPLOYED=$STATE.deployed
# One line per deploy or rollback under way ("deploy|rollback <from> <to>"), removed when it ends. A line left
# behind means a run was stopped halfway, and the next run rebuilds what changed between those commits too.
IN_PROGRESS=$STATE.in-progress
# "<commit> <seconds since 1970>": when --auto first saw that commit waiting for CI
PENDING=$STATE.pending
# Ctrl-C, a lost SSH session or a shutdown: say so and stop. The in-progress line stays, so the next run (cron's, or
# ./deploy.sh) redoes the rebuild instead of reporting "up to date" with the containers on an older commit.
# shellcheck disable=SC2329  # called by the traps below
on_signal() {
  trap - ERR INT TERM HUP
  log "INTERRUPTED by SIG$1$([ -s "$IN_PROGRESS" ] && echo "; the next run redoes the rebuild")"
  ping_health /fail
  exit $((128 + $2))
}
trap 'on_signal INT 2' INT
trap 'on_signal TERM 15' TERM
trap 'on_signal HUP 1' HUP
# A full commit id (sha1 or sha256) of a commit in this repository
is_commit() { [[ "$1" =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]] && git cat-file -e "$1^{commit}" 2>/dev/null; }
# Best effort, like the other state files: an unwritable one is logged and the deploy goes on
record_deployed() { { echo "$1" > "$DEPLOYED"; } 2>/dev/null || log "couldn't write $DEPLOYED"; }
mark_in_progress() {
  { echo "$1" >> "$IN_PROGRESS"; } 2>/dev/null || log "couldn't write $IN_PROGRESS; if this run is stopped halfway, the next one won't know to redo it"
}
end_in_progress() { rm -f "$IN_PROGRESS" 2>/dev/null || true; }
retire_legacy() { [ "$DRY" = 1 ] || { : > "$LEGACY_DONE"; } 2>/dev/null || true; }
# Leaves NEW undeployed for a person (reason in $*): logs HELD once, pings /fail, and exits without an error.
hold() {
  once "held $NEW"
  log "HELD $(git rev-parse --short "$NEW"): $* Deploy it by hand with ./deploy.sh once that's done."
  ping_health /fail
  exit 0
}

# One run at a time (cron every few minutes, plus a person running it by hand)
busy() {
  [ "$AUTO" = 1 ] && exit 0
  echo "Another deploy is running." >&2
  exit 1
}
mkdir -p "$STATE_DIR"
exec 9>"$STATE_DIR/lock"
flock -n 9 || busy
# Until a run of this version has ended well (LEGACY_DONE): a run of the previous version of this script locks the old
# file instead, so while that file exists, take it too. Opened read-only, so a file that isn't ours (another user's,
# in /tmp) is skipped rather than an error.
if [ ! -e "$LEGACY_DONE" ] && [ -e "$LEGACY.lock" ] && { exec 8<"$LEGACY.lock"; } 2>/dev/null; then flock -n 8 || busy; fi
# Move the state the previous version kept in /tmp, once, so a problem already reported isn't reported again and a
# rolled-back commit still isn't retried. Only for the default location, and not on a dry run.
if [ "$DRY" = 0 ] && [ -z "${DEPLOY_STATE:-}" ] && [ ! -e "$LEGACY_DONE" ]; then
  for suffix in "" .rolled-back; do
    if [ -f "$LEGACY.state$suffix" ] && [ ! -e "$STATE$suffix" ]; then mv -f "$LEGACY.state$suffix" "$STATE$suffix" 2>/dev/null || true; fi
  done
fi

# Keep deploy.log (which also gets cron's stderr) to about DEPLOY_LOG_MAX bytes (5 MB): move it to deploy.log.1
if [ "$DRY" = 0 ] && [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt "${DEPLOY_LOG_MAX:-5242880}" ]; then
  mv -f "$LOG" "$LOG.1" 2>/dev/null || true
fi

# Never overwrite edits made on the VM (untracked files such as .env are fine)
dirty=$(git status --porcelain --untracked-files=no)
if [ -n "$dirty" ]; then
  once "dirty"
  fail "the checkout has local changes to tracked files; commit or discard them first: $(head -5 <<<"$dirty" | tr '\n' ' ')"
fi

# git's own messages go into the FAILED line rather than stderr, so a repeated failure stays quiet in cron
if ! err=$(git fetch -q "$REMOTE" "$BRANCH" 2>&1); then
  once "fetch-failed"
  fail "couldn't fetch $REMOTE/$BRANCH: $(head -3 <<<"$err" | tr '\n' ' ')"
fi
HEAD_AT=$(git rev-parse HEAD)
NEW=$(git rev-parse "$REMOTE/$BRANCH")
# OLD: what the containers run. The recorded commit when there is one; before the first deploy by this version of
# the script, the checkout.
OLD=$HEAD_AT
recorded=$(cat "$DEPLOYED" 2>/dev/null || true)
if is_commit "$recorded"; then OLD=$recorded; fi
# Runs that were stopped halfway: their "<from> <to>" pairs (see IN_PROGRESS), unreadable lines dropped, and the
# kind of the last one
WAS=() WAS_KIND=""
if [ -f "$IN_PROGRESS" ]; then
  while read -r kind from to _; do
    if [[ "$kind" =~ ^(deploy|rollback)$ ]] && is_commit "$from" && is_commit "$to"; then
      WAS+=("$from $to"); WAS_KIND=$kind
    fi
  done < "$IN_PROGRESS" || true
  if [ ${#WAS[@]} -eq 0 ] && [ "$DRY" = 0 ]; then end_in_progress; fi
fi
# A run stopped halfway with no record before it (the first deploy by this version), or stopped between recording
# the deployed commit and clearing its line, makes OLD look like NEW. What the containers ran for sure before it is
# the stopped run's starting commit, so that is what a rollback goes back to.
if [ "$OLD" = "$NEW" ] && [ ${#WAS[@]} -gt 0 ]; then read -r OLD _ <<<"${WAS[0]}"; fi
if [ "$OLD" = "$NEW" ] && [ "$HEAD_AT" = "$NEW" ] && [ ${#WAS[@]} -eq 0 ]; then
  [ "$AUTO" = 1 ] || echo "Already up to date at $(git rev-parse --short HEAD)."
  # The first run of this version: the checkout is taken as what the containers run
  if [ "$DRY" = 0 ] && [ ! -f "$DEPLOYED" ]; then record_deployed "$NEW"; fi
  clear_state
  [ "$DRY" = 1 ] || rm -f "$PENDING"
  retire_legacy
  ping_health ""
  exit 0
fi
# A commit that was deployed and rolled back isn't retried by cron; a newer commit or ./deploy.sh moves past it.
# If that rollback itself was stopped halfway, cron finishes it, once: back to the commit it was rolling back to.
FINISH=0 TARGET=$NEW
if [ "$AUTO" = 1 ] && [ -f "$ROLLED_BACK" ] && [ "$(cat "$ROLLED_BACK")" = "$NEW" ]; then
  [ "$WAS_KIND" = rollback ] || exit 0
  once "finish-rollback $NEW"
  FINISH=1
  read -r TARGET _ <<<"${WAS[${#WAS[@]}-1]}"
fi
if [ "$FINISH" = 0 ] && ! git merge-base --is-ancestor "$HEAD_AT" "$NEW"; then
  once "not-fast-forward $HEAD_AT $NEW"
  fail "$REMOTE/$BRANCH isn't a fast-forward of the checkout ($(git rev-parse --short "$HEAD_AT")); sort it out by hand"
fi

# --auto: only commits whose CI passed. Failed: don't deploy. Pending (still running, or not started): try again on
# the next run, logging once that it waits; after DEPLOY_CI_WAIT_HOURS, report it, since a run that never starts
# ([skip ci] in a squash message, a disabled workflow, a renamed job) would otherwise leave the VM behind in silence.
# Not when finishing a rollback: that goes back to a commit that was already deployed.
if [ "$AUTO" = 1 ] && [ "$FINISH" = 0 ]; then
  if ! checks=$("$CURL" -fsS -m 20 -H "Accept: application/vnd.github+json" "$API/repos/$REPO/commits/$NEW/check-runs?per_page=100"); then
    once "github-api $NEW"
    fail "couldn't ask GitHub for the CI result of $(git rev-parse --short "$NEW")"
  fi
  if ! verdict=$(CHECKS_JSON="$checks" python3 -c '
import json, os, sys
runs = {r["name"]: r for r in json.loads(os.environ["CHECKS_JSON"]).get("check_runs", [])}
required = sys.argv[1:]
waiting = [n + (" (" + str(runs[n]["status"]) + ")" if n in runs else " (not started)")
           for n in required if n not in runs or runs[n]["status"] != "completed"]
if waiting:
    print("pending: " + ", ".join(waiting))
elif all(runs[n]["conclusion"] == "success" for n in required):
    print("passed")
else:
    print("failed: " + ", ".join(n + "=" + str(runs[n]["conclusion"]) for n in required))
' "${REQUIRED_CHECKS[@]}" 2>&1); then
    once "github-reply $NEW"
    fail "couldn't read GitHub's CI result for $(git rev-parse --short "$NEW"): $(tail -1 <<<"$verdict")"
  fi
  case "$verdict" in
    pending*)
      [ "$DRY" = 0 ] || { echo "CI hasn't finished for $(git rev-parse --short "$NEW") (${verdict#pending: })"; exit 0; }
      read -r seen_sha seen_at _ 2>/dev/null < "$PENDING" || true
      if [ "${seen_sha:-}" != "$NEW" ] || ! [[ "${seen_at:-}" =~ ^[0-9]+$ ]]; then
        { echo "$NEW $(date +%s)" > "$PENDING"; } 2>/dev/null || true
        log "waiting for CI on $(git rev-parse --short "$NEW") (${verdict#pending: })"
        exit 0
      fi
      wait_hours=${DEPLOY_CI_WAIT_HOURS:-3}
      [[ "$wait_hours" =~ ^[0-9]+$ ]] || wait_hours=3
      if [ $(( $(date +%s) - seen_at )) -lt $(( wait_hours * 3600 )) ]; then exit 0; fi
      once "ci-stuck $NEW"
      fail "CI hasn't finished for $(git rev-parse --short "$NEW") after $wait_hours hours (${verdict#pending: }); not deploying. Re-run CI on that commit (Actions tab), or deploy it by hand with ./deploy.sh"
      ;;
    passed) ;;
    *) once "ci-failed $NEW"; fail "CI didn't pass for $(git rev-parse --short "$NEW") ($verdict); not deploying" ;;
  esac
fi

# --no-renames: a moved file counts at both its old and new path, so the services on both sides rebuild. Plus what
# a run that was stopped halfway changed: its containers may be on either side of it.
changed_between() { git -c core.quotePath=false diff --name-only --no-renames "$1" "$2"; }
CHANGED=$(
  changed_between "$OLD" "$TARGET"
  for w in "${WAS[@]}"; do read -r a b <<<"$w"; changed_between "$a" "$b"; done
)
CHANGED=$(sed '/^$/d' <<<"$CHANGED" | sort -u)
if [ "$AUTO" = 1 ] && [ "$FINISH" = 0 ]; then
  # git prints a name with a quote, backslash or control character quoted and escaped ("home/a\".php"), which none
  # of the patterns below would match, so such a change is held whatever it is.
  if grep -q '^"' <<<"$CHANGED"; then hold "it changes a file whose name has quotes, backslashes or control characters: $(grep -m 3 '^"' <<<"$CHANGED" | tr '\n' ' ')"; fi
  if grep -q '^dashboard/backend/app/db/migrations/' <<<"$CHANGED"; then hold "it adds or changes a database migration, which must be applied by hand first."; fi
  if grep -qx 'docker-compose.yml' <<<"$CHANGED"; then hold "it changes docker-compose.yml, which can restart or re-network the whole stack."; fi
  if grep -qx 'home/wp-includes/version.php' <<<"$CHANGED"; then hold "it updates WordPress core, which needs its database update run from wp-admin."; fi
  if held=$(grep -E "$HOLD_PATHS" <<<"$CHANGED"); then
    hold "it changes files a person must deploy (CI, deploy.sh, WordPress code or config, wordpress/): $(head -5 <<<"$held" | tr '\n' ' ')"
  fi
fi

SERVICES=()
# Adds services to the rebuild list, once each. ALL means the whole stack.
add() { local s; for s in "$@"; do [[ " ${SERVICES[*]-} " == *" $s "* ]] || SERVICES+=("$s"); done; }
if grep -q '^dashboard/frontend/' <<<"$CHANGED"; then add dashboard; fi
if grep -q '^dashboard/backend/' <<<"$CHANGED"; then
  add backend worker export_worker
  # welldash² (the ops service) runs the backend image too, but only where it was turned on; rebuild it if it runs.
  if [ -n "$("$DOCKER" compose ps -q ops 2>/dev/null || true)" ]; then add ops; fi
fi
if grep -qx 'docker-compose.yml' <<<"$CHANGED"; then add ALL; fi
# Apache/PHP config files in wordpress/ are bind-mounted into the wordpress container one file at a time. Apache and
# PHP read them only at start, and git replaces a changed file with a new one, so the running container keeps the old
# copy until it's recreated. Compose sees no change in its own config, so a plain `up -d` wouldn't recreate it.
RECREATE=()
if grep -Eq '^wordpress/.*\.(conf|ini)$' <<<"$CHANGED"; then RECREATE=(wordpress); fi
# Everything else needs no rebuild: WordPress is the stock wordpress image with home/ bind-mounted, so home/ is
# live once merged (which is why --auto holds its PHP, HOLD_PATHS); docs, tests and CI aren't deployed.

summary="$(git rev-parse --short "$OLD")..$(git rev-parse --short "$TARGET") ($(git log --format=%s -1 "$TARGET" | cut -c1-70)); services: ${SERVICES[*]:-none}${RECREATE[*]:+; recreate: ${RECREATE[*]}}${WAS[*]:+; with what a run that was stopped halfway changed}"
if [ "$DRY" = 1 ]; then echo "Would deploy $summary"; exit 0; fi

# Rebuilds and starts the services in SERVICES, and recreates those in RECREATE. Returns 1 if compose fails.
rebuild() {
  if [[ " ${SERVICES[*]-} " == *" ALL "* ]]; then
    "$DOCKER" compose up -d --build || return 1
  elif [ ${#SERVICES[@]} -gt 0 ]; then
    "$DOCKER" compose up -d --build --no-deps "${SERVICES[@]}" || return 1
  fi
  if [ ${#RECREATE[@]} -gt 0 ]; then
    "$DOCKER" compose up -d --force-recreate --no-deps "${RECREATE[@]}" || return 1
  fi
}

# The site's pages. Returns 0, or sets PROBLEM to what's wrong and returns 1. $1: how many times to try
# /api/latest and the WordPress home page (5 s apart), the slowest to come back after a rebuild or recreate. The
# checks set PROBLEM rather than print it so they're called straight from `if`, where the ERR trap doesn't apply,
# not from a $(...) subshell.
site_ok() {
  local code=000
  for _ in $(seq 1 "$1"); do
    code=$("$CURL" -s -o /dev/null -m 10 -w '%{http_code}' "http://$SITE_HOST:8081/api/latest" || true)
    [ "$code" = 200 ] && break
    sleep "${DEPLOY_HEALTH_WAIT:-5}"
  done
  if [ "$code" != 200 ]; then PROBLEM="dashboard /api/latest answered $code"; return 1; fi
  code=$("$CURL" -s -o /dev/null -m 10 -w '%{http_code}' "http://$SITE_HOST:8081/" || true)
  if [ "$code" != 200 ]; then PROBLEM="dashboard home answered $code"; return 1; fi
  # Tried as often as /api/latest: a recreated wordpress container answers only once Apache has started
  for _ in $(seq 1 "$1"); do
    code=$("$CURL" -s -o /dev/null -m 20 -w '%{http_code}' -H 'Host: well.mcmaster.ca' -H 'X-Forwarded-Proto: https' "http://$SITE_HOST:8080/" || true)
    [ "$code" = 200 ] && break
    sleep "${DEPLOY_HEALTH_WAIT:-5}"
  done
  if [ "$code" != 200 ]; then PROBLEM="WordPress home answered $code"; return 1; fi
}

# The rebuilt background workers serve no page, and compose restarts them when they crash (Docker even reports a
# restarting container as Running), so a single "is it running" sample proves nothing. Instead: note each rebuilt
# worker's container and restart count right after the rebuild...
WORKERS=() OPS_WATCH=""
container_state() { # <service>: "<service>:<container id>:<restart count>"
  local id
  id=$("$DOCKER" compose ps -q "$1" 2>/dev/null | head -1 || true)
  echo "$1:$id:$("$DOCKER" inspect -f '{{.RestartCount}}' "$id" 2>/dev/null || echo '?')"
}
note_workers() {
  local s
  WORKERS=()
  for s in worker export_worker; do
    [[ " ${SERVICES[*]-} " == *" $s "* || " ${SERVICES[*]-} " == *" ALL "* ]] || continue
    WORKERS+=("$(container_state "$s")")
  done
  # welldash² (ops) is watched the same way when it was rebuilt by name, but only reported (ops_report): it isn't
  # public, so it never rolls the site back, even if it was already failing before the deploy.
  OPS_WATCH=""
  if [[ " ${SERVICES[*]-} " == *" ops "* ]]; then OPS_WATCH=$(container_state ops); fi
}
# ...then, a minute after the rebuild, require each to be the same container, running, and not restarted since
wait_after_rebuild() {
  local now=$(( $(date +%s) - REBUILT_AT ))
  if [ "$now" -lt "${DEPLOY_WORKER_WAIT:-60}" ]; then sleep $(( ${DEPLOY_WORKER_WAIT:-60} - now )); fi
}
stayed_up() { # "<service>:<id>:<count>" from container_state; returns 0, or sets PROBLEM and returns 1
  local s id count now
  IFS=: read -r s id count <<<"$1"
  if [ -z "$id" ]; then PROBLEM="no $s container after the rebuild"; return 1; fi
  now=$("$DOCKER" inspect -f '{{.State.Status}} {{.RestartCount}}' "$id" 2>/dev/null || echo "gone")
  if [ "$now" != "running $count" ]; then
    PROBLEM="the $s container didn't stay up (status and restart count: '$now', right after the rebuild: restart count $count)"
    return 1
  fi
}
workers_ok() {
  local w
  [ ${#WORKERS[@]} -eq 0 ] && return 0
  wait_after_rebuild
  for w in "${WORKERS[@]}"; do stayed_up "$w" || return 1; done
}
ops_report() {
  [ -n "$OPS_WATCH" ] || return 0
  wait_after_rebuild
  if ! stayed_up "$OPS_WATCH"; then
    log "welldash² needs a look: $PROBLEM. The public site is fine and the deploy is kept; see docker compose logs ops"
  fi
}

# After a healthy deploy that built images, frees what old builds hold on disk: dangling images (old builds no longer
# tagged) and the build cache beyond its 5 GB most recently used. The images the containers ran before this deploy
# (noted in KEEP_IMAGES) are kept as rollback points. Volumes are never touched. Best effort: logs what it freed,
# and a failure is only logged, never fails a healthy deploy. Called with ||, so the ERR trap doesn't apply.
KEEP_IMAGES=""
prune_old_builds() {
  local id removed=0 kept=0 before after cache root
  [ ${#SERVICES[@]} -gt 0 ] || return 0
  root=$("$DOCKER" info -f '{{.DockerRootDir}}' 2>/dev/null || true)
  before=$(df -Pk "${root:-/}" 2>/dev/null | awk 'NR == 2 {print $4}' || true)
  for id in $("$DOCKER" image ls -q --no-trunc -f dangling=true 2>/dev/null || true); do
    if grep -qxF "${id#sha256:}" <<<"$KEEP_IMAGES"; then kept=$((kept + 1)); continue; fi
    # One still used by a container (even a stopped one) is refused by docker and left in place
    if "$DOCKER" image rm "$id" >/dev/null 2>&1; then removed=$((removed + 1)); fi
  done
  cache=$("$DOCKER" builder prune -f --reserved-space 5GB 2>&1 | grep -i '^total' | tr -s ' \t' ' ' || true)
  after=$(df -Pk "${root:-/}" 2>/dev/null | awk 'NR == 2 {print $4}' || true)
  local disk=""
  if [ -n "$before" ] && [ -n "$after" ]; then disk="; free disk went from $((before / 1024)) MB to $((after / 1024)) MB"; fi
  log "pruned $removed old image(s) (kept $kept as rollback points) and the build cache (${cache:-nothing freed})$disk"
}

rebuild_and_check() {  # returns 0, or sets PROBLEM and returns 1
  if ! rebuild; then PROBLEM="the rebuild failed"; return 1; fi
  REBUILT_AT=$(date +%s)
  note_workers
  site_ok "${DEPLOY_HEALTH_TRIES:-24}" && workers_ok  # up to ~2 minutes for the pages to come back
}

# If the site is already down, a deploy would be blamed for it (and rolled back). Not checked when finishing a
# rollback: the site is likely down because the rollback was stopped, and there is nothing further back to go to.
was_healthy=1 PROBLEM=""
if [ "$FINISH" = 1 ]; then
  was_healthy=0
elif ! site_ok 3; then
  was_healthy=0
  if [ "$AUTO" = 1 ]; then
    once "unhealthy-before"
    fail "the site is already unhealthy ($PROBLEM), so not deploying $(git rev-parse --short "$NEW"); fix the site, or deploy by hand with ./deploy.sh"
  fi
  log "the site is already unhealthy ($PROBLEM); deploying anyway, and not rolling back if it stays unhealthy"
fi

if [ "$FINISH" = 1 ]; then
  log "finishing a rollback that was stopped halfway: back to $(git rev-parse --short "$TARGET") from $(git rev-parse --short "$NEW"); services: ${SERVICES[*]:-none}${RECREATE[*]:+; recreate: ${RECREATE[*]}}"
  # --keep, as the rollback does: the checkout may still be on either commit
  git reset -q --keep "$TARGET" || fail "couldn't finish rolling back to $(git rev-parse --short "$TARGET") (git reset failed); needs a person now"
  if rebuild_and_check; then
    record_deployed "$TARGET"
    end_in_progress
    fail "finished rolling back to $(git rev-parse --short "$TARGET"), which is healthy again; $(git rev-parse --short "$NEW") needs a look. Cron won't retry it: push a fix, or run ./deploy.sh by hand."
  fi
  end_in_progress
  fail "finished rolling back to $(git rev-parse --short "$TARGET") but the site is STILL unhealthy ($PROBLEM); needs a person now"
fi

[ "$AUTO" = 1 ] || rm -f "$ROLLED_BACK" 2>/dev/null || true  # deploying by hand moves past a rolled-back commit
# Merge first, so a merge git refuses (e.g. an untracked file in the way) is reported once, like other problems
if ! err=$(git merge -q --ff-only "$NEW" 2>&1); then
  once "merge-failed $NEW"
  fail "couldn't fast-forward to $(git rev-parse --short "$NEW") ($summary): $(head -3 <<<"$err" | tr '\n' ' ')"
fi
# From here until the end the checkout and the containers may disagree, so a run stopped here leaves this line for
# the next one (and the deployed commit isn't moved until the site is healthy)
mark_in_progress "deploy $OLD $NEW"
log "deploying $summary"
# Image ids without the sha256: prefix, one per line, as `docker image ls --no-trunc` gives them once stripped
if [ ${#SERVICES[@]} -gt 0 ]; then KEEP_IMAGES=$("$DOCKER" compose images -q 2>/dev/null | sed 's/^sha256://' || true); fi
if rebuild_and_check; then
  log "deployed $(git rev-parse --short HEAD); healthy"
  record_deployed "$(git rev-parse HEAD)"
  end_in_progress
  ops_report
  prune_old_builds || log "pruning old images failed; the deploy is kept"
  clear_state
  rm -f "$ROLLED_BACK" "$PENDING" 2>/dev/null || true
  retire_legacy
  ping_health ""
  exit 0
fi
problem=$PROBLEM
if [ "$was_healthy" = 0 ]; then
  # The rebuild ran to the end, so there is nothing to redo; the deployed commit stays where it was
  end_in_progress
  fail "deployed $(git rev-parse --short HEAD), but the site is still unhealthy ($problem); needs a person now"
fi
log "unhealthy after deploying $(git rev-parse --short "$NEW") ($problem); rolling back to $(git rev-parse --short "$OLD")"
# If the rollback is stopped halfway, the next cron run finishes it
mark_in_progress "rollback $OLD $NEW"
# So cron doesn't redeploy it every 5 minutes. Best effort: an unwritable file mustn't stop the rollback.
{ echo "$NEW" > "$ROLLED_BACK"; } 2>/dev/null || log "couldn't write $ROLLED_BACK; cron may retry $(git rev-parse --short "$NEW")"
git reset -q --keep "$OLD" || fail "couldn't roll back to $(git rev-parse --short "$OLD") (git reset failed) after $(git rev-parse --short "$NEW") was unhealthy ($problem); needs a person now"
if rebuild_and_check; then
  end_in_progress
  fail "rolled back to $(git rev-parse --short "$OLD"), which is healthy again; $(git rev-parse --short "$NEW") needs a look ($problem). Cron won't retry it: push a fix, or run ./deploy.sh by hand."
fi
end_in_progress
fail "rolled back to $(git rev-parse --short "$OLD") but the site is STILL unhealthy ($PROBLEM); needs a person now"
