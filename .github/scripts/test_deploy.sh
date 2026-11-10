#!/usr/bin/env bash
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
mkdir -p dashboard/frontend dashboard/backend/app/db/migrations home/wp-includes wordpress
for f in README.md dashboard/frontend/page.tsx dashboard/backend/app/x.py home/wp-includes/version.php docker-compose.yml; do echo 0 > "$f"; done
cp "$ROOT/deploy.sh" .
git add -A && git commit -qm init && git push -q origin HEAD:main

# The VM's checkout
git clone -q -b main "$T/remote.git" "$T/vm"

# Stubs
mkdir "$T/bin"
cat > "$T/bin/docker" <<'EOF'
#!/bin/sh
echo "docker $*" >> "$STUB_LOG"
[ "$1" = inspect ] && echo "${WORKER_RUNNING:-true}"
exit 0
EOF
cat > "$T/bin/curl" <<'EOF'
#!/bin/sh
for a in "$@"; do
  case "$a" in *check-runs*) cat "$CHECKS_FILE"; exit 0 ;; esac
done
case "$*" in
  *http_code*)
    if [ -n "${BAD_SHA:-}" ] && [ "$(git -C "$VM" rev-parse HEAD)" = "$BAD_SHA" ]; then printf 500; else printf "${HEALTH_CODE:-200}"; fi ;;
esac
exit 0
EOF
chmod +x "$T/bin/docker" "$T/bin/curl"
export DOCKER=$T/bin/docker CURL=$T/bin/curl STUB_LOG=$T/stub.log DEPLOY_LOG=$T/deploy.log DEPLOY_STATE=$T/state \
  CHECKS_FILE=$T/checks.json DEPLOY_HEALTH_TRIES=2 DEPLOY_HEALTH_WAIT=0 VM=$T/vm

ci() { # ci <backend conclusion|pending> <dashboard conclusion|pending>
  python3 - "$1" "$2" > "$CHECKS_FILE" <<'EOF'
import json, sys
def run(name, c):
    return {"name": name, "status": "in_progress" if c == "pending" else "completed",
            "conclusion": None if c == "pending" else c}
print(json.dumps({"check_runs": [run("Backend image and tests", sys.argv[1]), run("Dashboard build", sys.argv[2]),
                                 run("Deploy script", "success")]}))
EOF
}
change() { # commit and push edits to the given paths
  (cd "$T/work" && for f in "$@"; do mkdir -p "$(dirname "$f")"; echo "$RANDOM" >> "$f"; done \
    && git add -A && git commit -qm "change $*" && git push -q origin HEAD:main)
}
sync_vm() { git -C "$T/vm" fetch -q && git -C "$T/vm" reset -q --hard origin/main; : > "$STUB_LOG"; rm -f "$DEPLOY_STATE"; }
deploy() { (cd "$T/vm" && bash ./deploy.sh "$@") > "$T/out" 2>&1; echo $? > "$T/rc"; }
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
check "frontend change: rebuilds only the dashboard" 'rc 0 && head_is_remote && ran "compose up -d --build --no-deps dashboard" && ! ran "backend"'

sync_vm; change dashboard/backend/app/x.py; ci success success; deploy --auto
check "--auto, CI passed: rebuilds backend, worker, export_worker" 'rc 0 && head_is_remote && ran "--no-deps backend worker export_worker"'

sync_vm; change dashboard/backend/app/x.py; ci pending success; deploy --auto
check "--auto, CI still running: waits, changes nothing" 'rc 0 && ! head_is_remote && [ ! -s "$STUB_LOG" ] && [ ! -s "$T/out" ]'

sync_vm; change dashboard/backend/app/x.py; ci failure success; deploy --auto
check "--auto, CI failed: refuses and says so" 'rc 1 && ! head_is_remote && said "CI didn'"'"'t pass" && ! ran "compose"'
deploy --auto
check "--auto, CI failed: reports it only once" 'rc 0 && [ ! -s "$T/out" ]'

sync_vm; change dashboard/backend/app/db/migrations/2026-12-01_x.sql; ci success success; deploy --auto
check "--auto, new migration: held" 'rc 0 && ! head_is_remote && said "HELD" && said "migration" && ! ran "compose"'
deploy --auto
check "--auto, held: reports it only once" 'rc 0 && [ ! -s "$T/out" ]'

sync_vm; change docker-compose.yml; ci success success; deploy --auto
check "--auto, docker-compose.yml change: held" 'rc 0 && ! head_is_remote && said "docker-compose.yml"'

sync_vm; change home/wp-includes/version.php; ci success success; deploy --auto
check "--auto, WordPress core update: held" 'rc 0 && ! head_is_remote && said "WordPress core"'

sync_vm; change docker-compose.yml; deploy
check "by hand, docker-compose.yml change: rebuilds everything" 'rc 0 && head_is_remote && ran "compose up -d --build" && ! ran "--no-deps"'

sync_vm; change README.md; deploy
check "docs-only change: merged, nothing rebuilt" 'rc 0 && head_is_remote && ! ran "compose"'

sync_vm; change dashboard/frontend/page.tsx; deploy --dry-run
check "--dry-run: says what it would do, changes nothing" 'rc 0 && ! head_is_remote && said "Would deploy" && said "services: dashboard" && [ ! -s "$STUB_LOG" ]'

sync_vm; echo dirty >> "$T/vm/README.md"; change dashboard/frontend/page.tsx; deploy
check "local edits on the VM: refuses" 'rc 1 && said "local changes" && ! ran "compose"'
git -C "$T/vm" checkout -q -- README.md

sync_vm; old=$(git -C "$T/vm" rev-parse HEAD); change dashboard/frontend/page.tsx
export BAD_SHA; BAD_SHA=$(git -C "$T/work" rev-parse HEAD); deploy; unset BAD_SHA
check "unhealthy after deploy: rolls back to the previous commit" 'rc 1 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && said "rolling back" && said "healthy again"'

sync_vm; old=$(git -C "$T/vm" rev-parse HEAD); change dashboard/frontend/page.tsx; HEALTH_CODE=502 deploy
check "still unhealthy after rollback: says a person is needed" 'rc 1 && [ "$(git -C "$T/vm" rev-parse HEAD)" = "$old" ] && said "STILL unhealthy"'

echo "$pass passed, $failures failed"
[ "$failures" = 0 ]
