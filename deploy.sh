#!/usr/bin/env bash
# Deploys the latest `main` to this VM: pulls it, rebuilds only the services whose files changed, checks the
# site is healthy, and rolls back if it isn't. See docs/deploying.md.
#
#   ./deploy.sh            deploy now (asks nothing; you're there)
#   ./deploy.sh --auto     for cron: only deploy a commit whose CI checks all passed, and hold (log, don't
#                          deploy) changes that need a person: DB migrations, docker-compose.yml, a WordPress
#                          core update. Each problem is reported once, not on every run; a rolled-back commit
#                          isn't retried. Prints nothing when there's nothing to do.
#   ./deploy.sh --dry-run  show what would happen, change nothing (no log, state or pings)
#
# Settings (environment, all optional): DEPLOY_BRANCH (main), DEPLOY_REMOTE (origin), DEPLOY_LOG
# (deploy.log next to this script), DEPLOY_HEALTHCHECK_URL (a Healthchecks.io ping URL: success pings it,
# failure pings <url>/fail), GITHUB_REPO (ARCO-Lab/WELLWebsite), DEPLOY_STATE_DIR (.deploy-state next to this
# script: the lock, the reported-problem state and the rolled-back marker). DOCKER, CURL, GITHUB_API, DEPLOY_STATE,
# DEPLOY_HEALTH_TRIES, DEPLOY_HEALTH_WAIT and DEPLOY_WORKER_WAIT exist for tests.
set -Eeuo pipefail

AUTO=0 DRY=0
for arg in "$@"; do
  case "$arg" in
    --auto) AUTO=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
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
REPO=${GITHUB_REPO:-ARCO-Lab/WELLWebsite}
API=${GITHUB_API:-https://api.github.com}
DOCKER=${DOCKER:-docker}
CURL=${CURL:-curl}
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
fail() { trap - ERR; log "FAILED: $*"; ping_health /fail; exit 1; }
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
# A run of the previous version of this script locks the old file instead, so while that file exists, take it too.
# Opened read-only, so a file that isn't ours (another user's, in /tmp) is skipped rather than an error.
if [ -e "$LEGACY.lock" ] && { exec 8<"$LEGACY.lock"; } 2>/dev/null; then flock -n 8 || busy; fi
# Move the state the previous version kept in /tmp, once, so a problem already reported isn't reported again and a
# rolled-back commit still isn't retried. Only for the default location, and not on a dry run.
if [ "$DRY" = 0 ] && [ -z "${DEPLOY_STATE:-}" ]; then
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
OLD=$(git rev-parse HEAD)
NEW=$(git rev-parse "$REMOTE/$BRANCH")
if [ "$OLD" = "$NEW" ]; then
  [ "$AUTO" = 1 ] || echo "Already up to date at $(git rev-parse --short HEAD)."
  clear_state
  ping_health ""
  exit 0
fi
# A commit that was deployed and rolled back isn't retried by cron; a newer commit or ./deploy.sh moves past it
if [ "$AUTO" = 1 ] && [ -f "$ROLLED_BACK" ] && [ "$(cat "$ROLLED_BACK")" = "$NEW" ]; then exit 0; fi
if ! git merge-base --is-ancestor "$OLD" "$NEW"; then
  once "not-fast-forward $OLD $NEW"
  fail "$REMOTE/$BRANCH isn't a fast-forward of the checkout ($(git rev-parse --short "$OLD")); sort it out by hand"
fi

# --auto: only commits whose CI passed. Pending: try again on the next run. Failed or missing: don't deploy.
if [ "$AUTO" = 1 ]; then
  if ! checks=$("$CURL" -fsS -m 20 -H "Accept: application/vnd.github+json" "$API/repos/$REPO/commits/$NEW/check-runs?per_page=100"); then
    once "github-api $NEW"
    fail "couldn't ask GitHub for the CI result of $(git rev-parse --short "$NEW")"
  fi
  if ! verdict=$(CHECKS_JSON="$checks" python3 -c '
import json, os, sys
runs = {r["name"]: r for r in json.loads(os.environ["CHECKS_JSON"]).get("check_runs", [])}
required = sys.argv[1:]
if any(n not in runs or runs[n]["status"] != "completed" for n in required):
    print("pending")
elif all(runs[n]["conclusion"] == "success" for n in required):
    print("passed")
else:
    print("failed: " + ", ".join(n + "=" + str(runs[n]["conclusion"]) for n in required))
' "${REQUIRED_CHECKS[@]}" 2>&1); then
    once "github-reply $NEW"
    fail "couldn't read GitHub's CI result for $(git rev-parse --short "$NEW"): $(tail -1 <<<"$verdict")"
  fi
  case "$verdict" in
    pending) exit 0 ;;
    passed) ;;
    *) once "ci-failed $NEW"; fail "CI didn't pass for $(git rev-parse --short "$NEW") ($verdict); not deploying" ;;
  esac
fi

# --no-renames: a moved file counts at both its old and new path, so the services on both sides rebuild
CHANGED=$(git -c core.quotePath=false diff --name-only --no-renames "$OLD" "$NEW")
if [ "$AUTO" = 1 ]; then
  if grep -q '^dashboard/backend/app/db/migrations/' <<<"$CHANGED"; then hold "it adds or changes a database migration, which must be applied by hand first."; fi
  if grep -qx 'docker-compose.yml' <<<"$CHANGED"; then hold "it changes docker-compose.yml, which can restart or re-network the whole stack."; fi
  if grep -qx 'home/wp-includes/version.php' <<<"$CHANGED"; then hold "it updates WordPress core, which needs its database update run from wp-admin."; fi
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
# live once merged; docs, tests and CI aren't deployed.

summary="$(git rev-parse --short "$OLD")..$(git rev-parse --short "$NEW") ($(git log --format=%s -1 "$NEW" | cut -c1-70)); services: ${SERVICES[*]:-none}${RECREATE[*]:+; recreate: ${RECREATE[*]}}"
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
    code=$("$CURL" -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:8081/api/latest || true)
    [ "$code" = 200 ] && break
    sleep "${DEPLOY_HEALTH_WAIT:-5}"
  done
  if [ "$code" != 200 ]; then PROBLEM="dashboard /api/latest answered $code"; return 1; fi
  code=$("$CURL" -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:8081/ || true)
  if [ "$code" != 200 ]; then PROBLEM="dashboard home answered $code"; return 1; fi
  # Tried as often as /api/latest: a recreated wordpress container answers only once Apache has started
  for _ in $(seq 1 "$1"); do
    code=$("$CURL" -s -o /dev/null -m 20 -w '%{http_code}' -H 'Host: well.mcmaster.ca' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8080/ || true)
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

# If the site is already down, a deploy would be blamed for it (and rolled back)
was_healthy=1 PROBLEM=""
if ! site_ok 3; then
  was_healthy=0
  if [ "$AUTO" = 1 ]; then
    once "unhealthy-before"
    fail "the site is already unhealthy ($PROBLEM), so not deploying $(git rev-parse --short "$NEW"); fix the site, or deploy by hand with ./deploy.sh"
  fi
  log "the site is already unhealthy ($PROBLEM); deploying anyway, and not rolling back if it stays unhealthy"
fi

[ "$AUTO" = 1 ] || rm -f "$ROLLED_BACK" 2>/dev/null || true  # deploying by hand moves past a rolled-back commit
# Merge first, so a merge git refuses (e.g. an untracked file in the way) is reported once, like other problems
if ! err=$(git merge -q --ff-only "$NEW" 2>&1); then
  once "merge-failed $NEW"
  fail "couldn't fast-forward to $(git rev-parse --short "$NEW") ($summary): $(head -3 <<<"$err" | tr '\n' ' ')"
fi
log "deploying $summary"
# Image ids without the sha256: prefix, one per line, as `docker image ls --no-trunc` gives them once stripped
if [ ${#SERVICES[@]} -gt 0 ]; then KEEP_IMAGES=$("$DOCKER" compose images -q 2>/dev/null | sed 's/^sha256://' || true); fi
if rebuild_and_check; then
  log "deployed $(git rev-parse --short HEAD); healthy"
  ops_report
  prune_old_builds || log "pruning old images failed; the deploy is kept"
  clear_state
  rm -f "$ROLLED_BACK" 2>/dev/null || true
  ping_health ""
  exit 0
fi
problem=$PROBLEM
if [ "$was_healthy" = 0 ]; then
  fail "deployed $(git rev-parse --short HEAD), but the site is still unhealthy ($problem); needs a person now"
fi
log "unhealthy after deploying $(git rev-parse --short "$NEW") ($problem); rolling back to $(git rev-parse --short "$OLD")"
# So cron doesn't redeploy it every 5 minutes. Best effort: an unwritable file mustn't stop the rollback.
{ echo "$NEW" > "$ROLLED_BACK"; } 2>/dev/null || log "couldn't write $ROLLED_BACK; cron may retry $(git rev-parse --short "$NEW")"
git reset -q --keep "$OLD" || fail "couldn't roll back to $(git rev-parse --short "$OLD") (git reset failed) after $(git rev-parse --short "$NEW") was unhealthy ($problem); needs a person now"
if rebuild_and_check; then
  fail "rolled back to $(git rev-parse --short "$OLD"), which is healthy again; $(git rev-parse --short "$NEW") needs a look ($problem). Cron won't retry it: push a fix, or run ./deploy.sh by hand."
fi
fail "rolled back to $(git rev-parse --short "$OLD") but the site is STILL unhealthy ($PROBLEM); needs a person now"
