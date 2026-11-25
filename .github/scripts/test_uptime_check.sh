#!/usr/bin/env bash
# shellcheck disable=SC2016  # check's conditions are single-quoted on purpose: check evals them later
# Tests uptime_check.sh against a stub `curl`. The stub answers the probe request with a body and HTTP status chosen
# by $SCENARIO, and records each Healthchecks.io ping it is asked to make, so the test can assert both the exit code
# and which ping suffix ("" for success, /fail) was requested. Nothing real is contacted.
#   bash .github/scripts/test_uptime_check.sh
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SCRIPT=$ROOT/uptime_check.sh
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT

mkdir -p "$T/bin"
# The probe call carries -w (it asks curl to append the status code); the ping call carries -o. The stub tells them
# apart that way: for the probe it prints "<body>\n<status>" as the real `curl -w '\n%{http_code}'` would (or, for a
# connection failure, nothing and a non-zero exit); for the ping it records the exact URL it was given.
cat > "$T/bin/curl" <<'EOF'
#!/bin/sh
is_probe=0 url=""
for a in "$@"; do
  case "$a" in
    -w) is_probe=1 ;;
    http*) url=$a ;;
  esac
done
if [ "$is_probe" = 1 ]; then
  case "$SCENARIO" in
    ok)       printf '%s\n%s' '[{"recorded_at":"2026-11-24T21:30:00","value":1.5}]' 200 ;;
    http502)  printf '%s\n%s' '<html><body>502 Bad Gateway</body></html>' 502 ;;
    empty)    printf '%s\n%s' '[]' 200 ;;
    connfail) exit 7 ;;   # curl's connect error: no output, non-zero exit
  esac
  exit 0
fi
echo "ping $url" >> "$STUB_LOG"
exit 0
EOF
chmod +x "$T/bin/curl"

export CURL=$T/bin/curl STUB_LOG=$T/log
UPTIME_URL=https://welldash.test/api/latest
HC=http://hc.test/uuid

# Runs the script with cron's minimal environment plus the test's settings. $SCENARIO drives the stub; HEALTHCHECK_URL_UPTIME
# is passed only when $HC is non-empty (empty $HC tests the unset case).
run() {
  : > "$STUB_LOG"
  local envs=(SCENARIO="$SCENARIO" UPTIME_URL="$UPTIME_URL" CURL="$CURL" STUB_LOG="$STUB_LOG")
  [ -n "${HC:-}" ] && envs+=(HEALTHCHECK_URL_UPTIME="$HC")
  env -i PATH="$PATH" "${envs[@]}" bash "$SCRIPT" > "$T/out" 2>&1
  echo $? > "$T/rc"
}
rc() { [ "$(cat "$T/rc")" = "$1" ]; }
said() { grep -qF -- "$1" "$T/out"; }
pinged() { grep -qxF -- "ping $1" "$STUB_LOG"; }   # whole-line match, so a base-URL ping never matches a /fail ping
no_ping() { [ ! -s "$STUB_LOG" ]; }

pass=0 failures=0
check() {
  if eval "$2"; then echo "PASS  $1"; pass=$((pass + 1))
  else
    echo "FAIL  $1"; echo "      output: $(tr '\n' ' ' < "$T/out")"; echo "      pings: $(tr '\n' ';' < "$STUB_LOG")"
    failures=$((failures + 1))
  fi
}

SCENARIO=ok HC=$HC run
check "200 with a reading: OK, exit 0, pings the base URL (not /fail)" \
  'rc 0 && said "OK" && pinged "$HC" && ! pinged "$HC/fail"'

SCENARIO=http502 HC=$HC run
check "HTTP 502: FAIL, exit 1, pings /fail" \
  'rc 1 && said "FAIL" && said "HTTP 502" && pinged "$HC/fail" && ! pinged "$HC"'

SCENARIO=empty HC=$HC run
check "200 with an empty [] (no readings): FAIL, exit 1, pings /fail" \
  'rc 1 && said "200 but no readings" && pinged "$HC/fail"'

SCENARIO=connfail HC=$HC run
check "connection failure (non-zero, no output): FAIL, exit 1, pings /fail" \
  'rc 1 && said "no response" && pinged "$HC/fail"'

SCENARIO=ok HC="" run
check "HEALTHCHECK_URL_UPTIME unset, healthy: exit 0, pings nothing" 'rc 0 && said "OK" && no_ping'

SCENARIO=http502 HC="" run
check "HEALTHCHECK_URL_UPTIME unset, unhealthy: exit still reflects health (1), pings nothing" \
  'rc 1 && said "HTTP 502" && no_ping'

echo "$pass passed, $failures failed"
[ "$failures" = 0 ]
