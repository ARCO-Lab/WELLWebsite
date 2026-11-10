#!/usr/bin/env bash
# Deploys the latest `main` to this VM: pulls it, rebuilds only the services whose files changed, checks the
# site is healthy, and rolls back if it isn't. See the README's "Deploying" section.
#
#   ./deploy.sh            deploy now (asks nothing; you're there)
#   ./deploy.sh --auto     for cron: only deploy a commit whose CI checks all passed, and hold (log, don't
#                          deploy) changes that need a person: DB migrations, docker-compose.yml, a WordPress
#                          core update. Prints nothing when there's nothing to do.
#   ./deploy.sh --dry-run  show what would happen, change nothing
#
# Settings (environment, all optional): DEPLOY_BRANCH (main), DEPLOY_REMOTE (origin), DEPLOY_LOG
# (deploy.log next to this script), DEPLOY_HEALTHCHECK_URL (a Healthchecks.io ping URL: success pings it,
# failure pings <url>/fail), GITHUB_REPO (ARCO-Lab/WELLWebsite). DOCKER, CURL, GITHUB_API and DEPLOY_STATE
# exist for tests.
set -euo pipefail

AUTO=0 DRY=0
for arg in "$@"; do
  case "$arg" in
    --auto) AUTO=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

cd "$(dirname "$(readlink -f "$0")")"
BRANCH=${DEPLOY_BRANCH:-main}
REMOTE=${DEPLOY_REMOTE:-origin}
LOG=${DEPLOY_LOG:-$PWD/deploy.log}
STATE=${DEPLOY_STATE:-${TMPDIR:-/tmp}/well-deploy.state}
REPO=${GITHUB_REPO:-ARCO-Lab/WELLWebsite}
API=${GITHUB_API:-https://api.github.com}
DOCKER=${DOCKER:-docker}
CURL=${CURL:-curl}
REQUIRED_CHECKS=("Backend image and tests" "Dashboard build" "Deploy script")  # job names in .github/workflows/ci.yml

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
ping_health() { if [ -n "${DEPLOY_HEALTHCHECK_URL:-}" ]; then "$CURL" -fsS -m 10 --retry 3 -o /dev/null "$DEPLOY_HEALTHCHECK_URL$1" || true; fi; }
fail() { log "FAILED: $*"; ping_health /fail; exit 1; }
# --auto runs every few minutes: report a held or CI-failed commit once, not on every run
once() {
  if [ "$AUTO" = 1 ] && [ -f "$STATE" ] && [ "$(cat "$STATE")" = "$1" ]; then exit 0; fi
  echo "$1" > "$STATE"
}
hold() {
  once "held $NEW"
  log "HELD $(git rev-parse --short "$NEW"): $* Deploy it by hand with ./deploy.sh once that's done."
  ping_health /fail
  exit 0
}

# One run at a time (cron every few minutes, plus a person running it by hand)
exec 9>"${TMPDIR:-/tmp}/well-deploy.lock"
if ! flock -n 9; then
  [ "$AUTO" = 1 ] && exit 0
  echo "Another deploy is running." >&2
  exit 1
fi

# Never overwrite edits made on the VM (untracked files such as .env are fine)
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  fail "the checkout has local changes to tracked files; commit or discard them first: $(git status --porcelain --untracked-files=no | head -5 | tr '\n' ' ')"
fi

git fetch -q "$REMOTE" "$BRANCH"
OLD=$(git rev-parse HEAD)
NEW=$(git rev-parse "$REMOTE/$BRANCH")
if [ "$OLD" = "$NEW" ]; then
  [ "$AUTO" = 1 ] || echo "Already up to date at $(git rev-parse --short HEAD)."
  ping_health ""
  exit 0
fi
if ! git merge-base --is-ancestor "$OLD" "$NEW"; then
  fail "$REMOTE/$BRANCH isn't a fast-forward of the checkout ($(git rev-parse --short "$OLD")); sort it out by hand"
fi

# --auto: only commits whose CI passed. Pending: try again on the next run. Failed or missing: don't deploy.
if [ "$AUTO" = 1 ]; then
  checks=$("$CURL" -fsS -m 20 -H "Accept: application/vnd.github+json" "$API/repos/$REPO/commits/$NEW/check-runs?per_page=100") \
    || fail "couldn't ask GitHub for the CI result of $(git rev-parse --short "$NEW")"
  verdict=$(CHECKS_JSON="$checks" python3 -c '
import json, os, sys
runs = {r["name"]: r for r in json.loads(os.environ["CHECKS_JSON"]).get("check_runs", [])}
required = sys.argv[1:]
if any(n not in runs or runs[n]["status"] != "completed" for n in required):
    print("pending")
elif all(runs[n]["conclusion"] == "success" for n in required):
    print("passed")
else:
    print("failed: " + ", ".join(n + "=" + str(runs[n]["conclusion"]) for n in required))
' "${REQUIRED_CHECKS[@]}")
  case "$verdict" in
    pending) exit 0 ;;
    passed) ;;
    *) once "ci-failed $NEW"; fail "CI didn't pass for $(git rev-parse --short "$NEW") ($verdict); not deploying" ;;
  esac
fi

CHANGED=$(git diff --name-only "$OLD" "$NEW")
if [ "$AUTO" = 1 ]; then
  if grep -q '^dashboard/backend/app/db/migrations/' <<<"$CHANGED"; then hold "it adds or changes a database migration, which must be applied by hand first."; fi
  if grep -qx 'docker-compose.yml' <<<"$CHANGED"; then hold "it changes docker-compose.yml, which can restart or re-network the whole stack."; fi
  if grep -qx 'home/wp-includes/version.php' <<<"$CHANGED"; then hold "it updates WordPress core, which needs its database update run from wp-admin."; fi
fi

SERVICES=()
add() { local s; for s in "$@"; do [[ " ${SERVICES[*]-} " == *" $s "* ]] || SERVICES+=("$s"); done; }
if grep -q '^dashboard/frontend/' <<<"$CHANGED"; then add dashboard; fi
if grep -q '^dashboard/backend/' <<<"$CHANGED"; then add backend worker export_worker; fi
if grep -q '^wordpress/' <<<"$CHANGED"; then add wordpress; fi
if grep -qx 'docker-compose.yml' <<<"$CHANGED"; then add ALL; fi
# Everything else needs no rebuild: home/ is bind-mounted (live once merged); docs, tests and CI aren't deployed.

summary="$(git rev-parse --short "$OLD")..$(git rev-parse --short "$NEW") ($(git log --format=%s -1 "$NEW" | cut -c1-70)); services: ${SERVICES[*]:-none}"
if [ "$DRY" = 1 ]; then echo "Would deploy $summary"; exit 0; fi

rebuild() {
  [ ${#SERVICES[@]} -eq 0 ] && return 0
  if [[ " ${SERVICES[*]} " == *" ALL "* ]]; then
    "$DOCKER" compose up -d --build
  else
    "$DOCKER" compose up -d --build --no-deps "${SERVICES[@]}"
  fi
}

# Prints what's wrong and returns 1, or prints nothing and returns 0
healthy() {
  local i code=000
  for i in $(seq 1 "${DEPLOY_HEALTH_TRIES:-24}"); do  # up to ~2 minutes for containers to come up
    code=$("$CURL" -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:8081/api/latest || true)
    [ "$code" = 200 ] && break
    sleep "${DEPLOY_HEALTH_WAIT:-5}"
  done
  if [ "$code" != 200 ]; then echo "dashboard /api/latest answered $code"; return 1; fi
  code=$("$CURL" -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:8081/ || true)
  if [ "$code" != 200 ]; then echo "dashboard home answered $code"; return 1; fi
  code=$("$CURL" -s -o /dev/null -m 20 -w '%{http_code}' -H 'Host: well.mcmaster.ca' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8080/ || true)
  if [ "$code" != 200 ]; then echo "WordPress home answered $code"; return 1; fi
  if [ "$("$DOCKER" inspect -f '{{.State.Running}}' wellwebsite-worker-1 2>/dev/null)" != true ]; then echo "the worker isn't running"; return 1; fi
}

log "deploying $summary"
git merge -q --ff-only "$NEW"
problem=""
if rebuild && problem=$(healthy); then
  log "deployed $(git rev-parse --short HEAD); healthy"
  ping_health ""
  exit 0
fi
problem=${problem:-the rebuild failed}
log "unhealthy after deploying $(git rev-parse --short "$NEW") ($problem); rolling back to $(git rev-parse --short "$OLD")"
git reset -q --keep "$OLD"
rebuild || true
if problem2=$(healthy); then
  fail "rolled back to $(git rev-parse --short "$OLD"), which is healthy again; $(git rev-parse --short "$NEW") needs a look ($problem)"
fi
fail "rolled back to $(git rev-parse --short "$OLD") but the site is STILL unhealthy (${problem2:-}); needs a person now"
