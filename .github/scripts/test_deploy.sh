#!/usr/bin/env bash
# shellcheck disable=SC2016,SC2034  # check's conditions are single-quoted on purpose: check evals them later, so
# their $(...) and variables (such as old) are read then, not where they're written
# Tests deploy.sh in a sandbox: a bare repo plays GitHub, a clone plays the VM's checkout, and stub `docker` and
# `curl` commands record what would run and answer CI/health queries. Nothing real is deployed or contacted.
#   bash .github/scripts/test_deploy.sh
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
export TMPDIR=$T GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

# The "GitHub" remote and a working copy for pushing changes to it
git init -q --bare -b main "$T/remote.git"
git clone -q "$T/remote.git" "$T/work" 2>/dev/null
cd "$T/work" || exit 1
mkdir -p dashboard/frontend dashboard/backend/app/db/migrations home/wp-includes
for f in README.md dashboard/frontend/page.tsx dashboard/backend/app/x.py home/wp-includes/version.php docker-compose.yml; do echo 0 > "$f"; done
cp "$ROOT/deploy.sh" .
git add -A && git commit -qm init && git push -q origin HEAD:main

# The VM's checkout
git clone -q -b main "$T/remote.git" "$T/vm"

# Stubs. docker: `compose up` marks the stack as rebuilt; `compose ps -q <svc>` names a container "id-<svc>" that
# reports 0 restarts. While $BAD_WORKER_SHA is checked out, service $MISSING has no container, and $CRASHING's
# restart count reads 2 on the second look (a crash loop that Docker still shows as running). curl: answers
# check-runs from $CHECKS_FILE (or fails if $API_DOWN), records health pings, and pages answer $HEALTH_CODE, 500
# while $BAD_SHA is checked out, or $HEALTH_AFTER_REBUILD once the stack has been rebuilt.
mkdir "$T/bin"
cat > "$T/bin/docker" <<'EOF'
#!/bin/sh
echo "docker $*" >> "$STUB_LOG"
bad_head() { [ -n "${BAD_WORKER_SHA:-}" ] && [ "$(git -C "$VM" rev-parse HEAD)" = "$BAD_WORKER_SHA" ]; }
case "$*" in
  "compose up"*) touch "$T/rebuilt"
    if [ -n "${BREAK_LOG:-}" ]; then rm -f "$DEPLOY_LOG"; mkdir -p "$DEPLOY_LOG"; fi ;;  # deploy.log unwritable mid-deploy
  "compose ps -q ops") [ -n "${OPS_RUNNING:-}" ] && echo "id-ops" ;;   # welldash²: off unless the test turns it on
  "compose ps -q "*) if [ "$4" = "${MISSING:-}" ] && bad_head; then :; else echo "id-$4"; fi ;;
  "inspect -f {{.RestartCount}} "*) echo 0 ;;
  "inspect -f {{.State.Status}} {{.RestartCount}} "*)
    if [ "$4" = "id-${CRASHING:-}" ] && bad_head; then echo "running 2"; else echo "running 0"; fi ;;
esac
exit 0
EOF
cat > "$T/bin/curl" <<'EOF'
#!/bin/sh
for a in "$@"; do
  case "$a" in
    *check-runs*) [ -n "${API_DOWN:-}" ] && exit 22; cat "$CHECKS_FILE"; exit 0 ;;
    http://hc.test/*) echo "ping $a" >> "$STUB_LOG"; exit 0 ;;
  esac
done
case "$*" in
  *127.0.0.1:8080*)
    # WordPress: 500 while $WP_BAD_SHA is checked out; with $WP_SLOW_START, 000 on the first call after a
    # rebuild/recreate (Apache not listening yet), then the usual answers
    if [ -n "${WP_BAD_SHA:-}" ] && [ "$(git -C "$VM" rev-parse HEAD)" = "$WP_BAD_SHA" ]; then printf 500; exit 0; fi
    if [ -n "${WP_SLOW_START:-}" ] && [ -f "$T/rebuilt" ] && [ ! -f "$T/wp-started" ]; then touch "$T/wp-started"; printf 000; exit 0; fi ;;
esac
case "$*" in
  *http_code*)
    if [ -n "${BAD_SHA:-}" ] && [ "$(git -C "$VM" rev-parse HEAD)" = "$BAD_SHA" ]; then printf 500
    elif [ -n "${HEALTH_AFTER_REBUILD:-}" ] && [ -f "$T/rebuilt" ]; then printf "$HEALTH_AFTER_REBUILD"
    else printf "${HEALTH_CODE:-200}"; fi ;;
esac
exit 0
EOF
chmod +x "$T/bin/docker" "$T/bin/curl"
export T DOCKER=$T/bin/docker CURL=$T/bin/curl STUB_LOG=$T/stub.log DEPLOY_LOG=$T/deploy.log DEPLOY_STATE=$T/state \
  CHECKS_FILE=$T/checks.json DEPLOY_HEALTH_TRIES=2 DEPLOY_HEALTH_WAIT=0 DEPLOY_WORKER_WAIT=0 VM=$T/vm

ci() { # ci <backend conclusion|pending> <dashboard conclusion|pending>
  python3 - "$1" "$2" > "$CHECKS_FILE" <<'EOF'
import json, sys
def run(name, c):
    return {"name": name, "status": "in_progress" if c == "pending" else "completed",
            "conclusion": None if c == "pending" else c}
print(json.dumps({"check_runs": [run("Backend image and tests", sys.argv[1]), run("Dashboard build", sys.argv[2]),
                                 run("Dashboard image", "success"), run("Deploy script", "success"),
                                 run("End-to-end data (vendors to browser)", "success")]}))
EOF
}
change() { # commit and push edits to the given paths
  (cd "$T/work" && for f in "$@"; do mkdir -p "$(dirname "$f")"; echo "$RANDOM" >> "$f"; done \
    && git add -A && git commit -qm "change $*" && git push -q origin HEAD:main)
}
sync_vm() {
  git -C "$T/vm" fetch -q && git -C "$T/vm" reset -q --hard origin/main
  : > "$STUB_LOG"; rm -rf "$DEPLOY_STATE" "$DEPLOY_STATE.rolled-back" "$DEPLOY_LOG" "$T/rebuilt"
}
deploy() { rm -f "$T/rebuilt"; (cd "$T/vm" && bash ./deploy.sh "$@") > "$T/out" 2>&1; echo $? > "$T/rc"; }
head_is_remote() { [ "$(git -C "$T/vm" rev-parse HEAD)" = "$(git -C "$T/work" rev-parse HEAD)" ]; }
ran() { grep -qF -- "$1" "$STUB_LOG"; }
said() { grep -qF -- "$1" "$T/out"; }
rc() { [ "$(cat "$T/rc")" = "$1" ]; }

pass=0 failures=0
check() {
  if eval "$2"; then echo "PASS  $1"; pass=$((pass + 1))
  else echo "FAIL  $1"; echo "      output: $(tr '\n' ' ' < "$T/out" | cut -c1-300)"; failures=$((failures + 1)); fi
}

sync_vm; deploy
check "up to date: nothing runs" 'rc 0 && said "Already up to date" && [ ! -s "$STUB_LOG" ]'

sync_vm; change dashboard/frontend/page.tsx; deploy
check "frontend change: rebuilds only the dashboard, no worker check" 'rc 0 && head_is_remote && ran "compose up -d --build --no-deps dashboard" && ! ran "backend" && ! ran "compose ps"'

sync_vm; change dashboard/backend/app/x.py; ci success success; deploy --auto
check "--auto, CI passed: rebuilds backend, worker, export_worker" 'rc 0 && head_is_remote && ran "--no-deps backend worker export_worker"'
check "backend change: checks both workers' containers" 'ran "compose ps -q worker" && ran "compose ps -q export_worker" && ran "inspect -f {{.State.Status}} {{.RestartCount}} id-export_worker"'

check "backend change, welldash² not running: not rebuilt" '! ran "export_worker ops"'

sync_vm; change dashboard/backend/app/x.py; OPS_RUNNING=1 deploy
check "backend change, welldash² running: rebuilt with the backend" 'rc 0 && ran "--no-deps backend worker export_worker ops" && said "healthy"'

sync_vm; change dashboard/backend/app/x.py; ci pending success; deploy --auto
check "--auto, CI still running: waits, changes nothing" 'rc 0 && ! head_is_remote && [ ! -s "$STUB_LOG" ] && [ ! -s "$T/out" ]'

sync_vm; change dashboard/backend/app/x.py; ci failure success; deploy --auto
check "--auto, CI failed: refuses and says so" 'rc 1 && ! head_is_remote && said "CI didn'"'"'t pass" && ! ran "compose"'
deploy --auto
check "--auto, CI failed: reports it only once" 'rc 0 && [ ! -s "$T/out" ]'

sync_vm; change dashboard/backend/app/x.py; API_DOWN=1 deploy --auto
check "--auto, GitHub API error: says so" 'rc 1 && said "couldn'"'"'t ask GitHub" && ! ran "compose"'
API_DOWN=1 deploy --auto
check "--auto, GitHub API error: reports it only once" 'rc 0 && [ ! -s "$T/out" ]'

sync_vm; change dashboard/backend/app/x.py; echo 'not json' > "$CHECKS_FILE"; deploy --auto
check "--auto, GitHub sends something that isn't JSON: says so" 'rc 1 && said "couldn'"'"'t read GitHub'"'"'s CI result" && said "JSONDecodeError" && ! ran "compose"'
deploy --auto
check "--auto, GitHub keeps sending non-JSON: reported only once" 'rc 0 && [ ! -s "$T/out" ]'

sync_vm; cp "$T/vm/.git/index" "$T/index.good"; echo garbage > "$T/vm/.git/index"; DEPLOY_HEALTHCHECK_URL=http://hc.test/x deploy --auto
check "a command failing unexpectedly (a corrupt git index) logs FAILED with the line, once, and pings /fail" 'rc 1 && [ "$(grep -c "FAILED" "$T/out")" = 1 ] && said "FAILED: line " && grep -q "FAILED: line " "$DEPLOY_LOG" && ran "ping http://hc.test/x/fail"'
: > "$STUB_LOG"; DEPLOY_HEALTHCHECK_URL=http://hc.test/x deploy --auto
check "--auto, the same unexpected failure: no second FAILED line or ping" 'rc 0 && ! said "FAILED" && [ ! -s "$STUB_LOG" ]'
cp "$T/index.good" "$T/vm/.git/index"

sync_vm; change dashboard/frontend/page.tsx; DEPLOY_REMOTE=nowhere DEPLOY_HEALTHCHECK_URL=http://hc.test/x deploy
check "fetch fails: logs FAILED and pings /fail" 'rc 1 && said "FAILED: couldn'"'"'t fetch nowhere/main" && ran "ping http://hc.test/x/fail" && ! ran "compose"'
DEPLOY_REMOTE=nowhere deploy --auto
check "--auto, fetch fails: reported only once, without git's own stderr" 'rc 0 && [ ! -s "$T/out" ]'

sync_vm; change dashboard/backend/app/db/migrations/2026-12-01_x.sql; ci success success; deploy --auto
check "--auto, new migration: held" 'rc 0 && ! head_is_remote && said "HELD" && said "migration" && ! ran "compose"'
deploy --auto
check "--auto, held: reports it only once" 'rc 0 && [ ! -s "$T/out" ]'

sync_vm; change docker-compose.yml; ci success success; deploy --auto
check "--auto, docker-compose.yml change: held" 'rc 0 && ! head_is_remote && said "docker-compose.yml"'

sync_vm; change home/wp-includes/version.php; ci success success; deploy --auto
check "--auto, WordPress core update: held" 'rc 0 && ! head_is_remote && said "WordPress core"'

sync_vm; change docker-compose.yml; deploy
check "by hand, docker-compose.yml change: rebuilds everything, checks both workers" 'rc 0 && head_is_remote && ran "compose up -d --build" && ! ran "--no-deps" && ran "compose ps -q worker" && ran "compose ps -q export_worker"'

sync_vm; change README.md; deploy
check "docs-only change: merged, nothing rebuilt" 'rc 0 && head_is_remote && ! ran "compose"'

sync_vm; change wordpress/zz-performance.conf; ci success success; deploy --auto
check "--auto, WordPress Apache/PHP config change: recreates only the wordpress container, then checks the site" 'rc 0 && head_is_remote && ran "compose up -d --force-recreate --no-deps wordpress" && ! ran "--build" && said "recreate: wordpress" && said "healthy"'

sync_vm; old=$(git -C "$T/vm" rev-parse HEAD); change wordpress/php-hardening.ini
WP_BAD_SHA=$(git -C "$T/work" rev-parse HEAD) deploy
check "WordPress config change that breaks WordPress only: rolls back and recreates wordpress with the old config" 'rc 1 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && said "WordPress home answered 500" && [ "$(grep -c "force-recreate --no-deps wordpress" "$STUB_LOG")" = 2 ] && said "healthy again"'

sync_vm; rm -f "$T/wp-started"; change wordpress/zz-performance.conf; WP_SLOW_START=1 deploy
check "recreated wordpress not answering on the first try: waits for it, deploys, no rollback" 'rc 0 && head_is_remote && said "healthy" && ! said "rolling back" && [ -f "$T/wp-started" ]'

sync_vm; change wordpress/theme-images.mjs; deploy
check "other files in wordpress/ (not .conf/.ini): nothing restarted" 'rc 0 && head_is_remote && ! ran "compose"'

sync_vm; (cd "$T/work" && echo 1 >> docker-compose.yml && mkdir -p wordpress && echo 1 >> wordpress/zz-performance.conf && git add -A && git commit -qm both && git push -q origin HEAD:main); deploy
check "by hand, docker-compose.yml and a WordPress config change: rebuilds everything and recreates wordpress" 'rc 0 && ran "compose up -d --build" && ran "compose up -d --force-recreate --no-deps wordpress"'

sync_vm; (cd "$T/work" && git mv dashboard/frontend/page.tsx dashboard/backend/app/page.tsx && git commit -qm move && git push -q origin HEAD:main); deploy
check "a file moved between services: both sides rebuild" 'rc 0 && ran "--no-deps dashboard backend worker export_worker"'

sync_vm; change dashboard/frontend/page.tsx; DEPLOY_HEALTHCHECK_URL=http://hc.test/x deploy --dry-run
check "--dry-run: says what it would do, changes nothing" 'rc 0 && ! head_is_remote && said "Would deploy" && said "services: dashboard" && [ ! -s "$STUB_LOG" ]'

sync_vm; echo dirty >> "$T/vm/README.md"; DEPLOY_HEALTHCHECK_URL=http://hc.test/x deploy --dry-run --auto
check "--dry-run that fails: no log, state or ping" 'rc 1 && said "FAILED" && [ ! -e "$DEPLOY_LOG" ] && [ ! -e "$DEPLOY_STATE" ] && [ ! -s "$STUB_LOG" ]'
git -C "$T/vm" checkout -q -- README.md

sync_vm; echo dirty >> "$T/vm/README.md"; change dashboard/frontend/page.tsx; DEPLOY_HEALTHCHECK_URL=http://hc.test/x deploy --auto
check "local edits on the VM: refuses and pings /fail" 'rc 1 && said "local changes" && ! ran "compose" && ran "ping http://hc.test/x/fail"'
: > "$STUB_LOG"; DEPLOY_HEALTHCHECK_URL=http://hc.test/x deploy --auto
check "--auto, local edits: reported only once" 'rc 0 && [ ! -s "$T/out" ] && [ ! -s "$STUB_LOG" ]'
git -C "$T/vm" checkout -q -- README.md

sync_vm; (cd "$T/vm" && echo vm > vm-only && git add vm-only && git commit -qm "commit made on the VM"); change README.md; deploy --auto
check "--auto, not a fast-forward: refuses" 'rc 1 && said "isn'"'"'t a fast-forward" && ! ran "compose"'
deploy --auto
check "--auto, not a fast-forward: reported only once" 'rc 0 && [ ! -s "$T/out" ]'

sync_vm; old=$(git -C "$T/vm" rev-parse HEAD); change dashboard/frontend/page.tsx
export BAD_SHA; BAD_SHA=$(git -C "$T/work" rev-parse HEAD); deploy
check "unhealthy after deploy: rolls back to the previous commit" 'rc 1 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && said "rolling back" && said "healthy again"'
: > "$STUB_LOG"; ci success success; deploy --auto
check "--auto after a rollback: doesn't redeploy the rolled-back commit" 'rc 0 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && [ ! -s "$T/out" ] && ! ran "compose"'
DEPLOY_REMOTE=nowhere deploy --auto; echo dirty >> "$T/vm/README.md"; deploy --auto; git -C "$T/vm" checkout -q -- README.md
: > "$STUB_LOG"; deploy --auto
check "--auto after a rollback, then fetch and local-edit errors: still doesn't redeploy it" 'rc 0 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && [ ! -s "$T/out" ] && ! ran "compose"'
unset BAD_SHA; change dashboard/frontend/page.tsx; deploy --auto
check "--auto after a rollback: a newer commit deploys" 'rc 0 && head_is_remote && ran "compose up" && [ ! -e "$DEPLOY_STATE.rolled-back" ]'

sync_vm; old=$(git -C "$T/vm" rev-parse HEAD); change dashboard/frontend/page.tsx
export BAD_SHA; BAD_SHA=$(git -C "$T/work" rev-parse HEAD); deploy; unset BAD_SHA
deploy
check "by hand after a rollback: deploys the rolled-back commit" 'rc 0 && head_is_remote && said "healthy" && [ ! -e "$DEPLOY_STATE.rolled-back" ]'

sync_vm; old=$(git -C "$T/vm" rev-parse HEAD); change dashboard/frontend/page.tsx; mkdir "$DEPLOY_STATE.rolled-back"
BAD_SHA=$(git -C "$T/work" rev-parse HEAD) deploy
check "rollback record can't be written: still rolls back" 'rc 1 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && said "couldn'"'"'t write" && said "healthy again"'

sync_vm; change dashboard/frontend/new.tsx; echo untracked > "$T/vm/dashboard/frontend/new.tsx"; ci success success; deploy --auto
check "--auto, fast-forward refused (an untracked file in the way): says so" 'rc 1 && ! head_is_remote && said "couldn'"'"'t fast-forward" && ! ran "compose"'
deploy --auto
check "--auto, fast-forward refused: reported only once" 'rc 0 && [ ! -s "$T/out" ]'
rm -f "$T/vm/dashboard/frontend/new.tsx"

sync_vm; change dashboard/frontend/page.tsx; mkdir "$DEPLOY_LOG"; DEPLOY_HEALTHCHECK_URL=http://hc.test/x deploy
check "deploy.log unwritable: deploys anyway, still printing the log lines" 'rc 0 && head_is_remote && ran "compose up -d --build --no-deps dashboard" && said "deployed" && ran "ping http://hc.test/x" && ! ran "ping http://hc.test/x/fail"'
rmdir "$DEPLOY_LOG"

sync_vm; change dashboard/frontend/page.tsx; BREAK_LOG=1 deploy
check "deploy.log becomes unwritable mid-deploy: the deploy completes" 'rc 0 && head_is_remote && ran "compose up" && said "deployed" && said "healthy"'
rm -rf "$DEPLOY_LOG"

sync_vm; old=$(git -C "$T/vm" rev-parse HEAD); change dashboard/frontend/page.tsx
BREAK_LOG=1 BAD_SHA=$(git -C "$T/work" rev-parse HEAD) deploy
check "deploy.log becomes unwritable mid-deploy, and the deploy is unhealthy: still rolls back" 'rc 1 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && said "rolling back" && said "healthy again"'
rm -rf "$DEPLOY_LOG"

sync_vm; mkdir "$DEPLOY_STATE"; echo dirty >> "$T/vm/README.md"; DEPLOY_HEALTHCHECK_URL=http://hc.test/x deploy --auto
check "state file unwritable: the problem is still reported, with a /fail ping" 'rc 1 && said "FAILED: the checkout has local changes" && ran "ping http://hc.test/x/fail"'
git -C "$T/vm" checkout -q -- README.md

sync_vm; mkdir "$DEPLOY_STATE"; DEPLOY_HEALTHCHECK_URL=http://hc.test/x deploy
check "a failure inside a function (state can't be cleared): FAILED with the line, and /fail" 'rc 1 && said "FAILED: line " && said "rm -f" && ran "ping http://hc.test/x/fail"'

sync_vm; head -c 3000 /dev/zero | tr '\0' x > "$DEPLOY_LOG"; change README.md; DEPLOY_LOG_MAX=2000 deploy
check "deploy.log over DEPLOY_LOG_MAX: moved to deploy.log.1, a fresh one started" 'rc 0 && [ "$(wc -c < "$DEPLOY_LOG.1")" = 3000 ] && [ "$(wc -c < "$DEPLOY_LOG")" -lt 2000 ] && grep -q deploying "$DEPLOY_LOG"'
rm -f "$DEPLOY_LOG.1"

sync_vm; old=$(git -C "$T/vm" rev-parse HEAD); change dashboard/backend/app/x.py
BAD_WORKER_SHA=$(git -C "$T/work" rev-parse HEAD) CRASHING=export_worker deploy
check "a rebuilt worker crash-looping (restart count rising): rolls back" 'rc 1 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && said "export_worker container didn'"'"'t stay up" && said "healthy again"'

sync_vm; old=$(git -C "$T/vm" rev-parse HEAD); change dashboard/backend/app/x.py
BAD_WORKER_SHA=$(git -C "$T/work" rev-parse HEAD) MISSING=worker deploy
check "a rebuilt worker with no container: rolls back" 'rc 1 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && said "no worker container" && said "healthy again"'

sync_vm; old=$(git -C "$T/vm" rev-parse HEAD); change dashboard/frontend/page.tsx; HEALTH_AFTER_REBUILD=502 deploy
check "still unhealthy after rollback: says a person is needed" 'rc 1 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && said "STILL unhealthy"'

sync_vm; change dashboard/frontend/page.tsx; ci success success; HEALTH_CODE=502 deploy --auto
check "--auto, site already unhealthy: doesn't deploy, says so" 'rc 1 && ! head_is_remote && said "already unhealthy" && ! ran "compose"'
HEALTH_CODE=502 deploy --auto
check "--auto, site already unhealthy: reported only once" 'rc 0 && [ ! -s "$T/out" ]'
HEALTH_CODE=502 deploy
check "by hand, site already unhealthy: deploys anyway, no rollback" 'rc 1 && head_is_remote && said "deploying anyway" && said "still unhealthy"'

echo "$pass passed, $failures failed"
[ "$failures" = 0 ]
