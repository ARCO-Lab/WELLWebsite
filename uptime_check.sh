#!/usr/bin/env bash
# Checks from outside that the dashboard API is actually serving data, and pings a Healthchecks.io dead-man's-switch
# so a silent outage is noticed. Run every few minutes from cron on the VM (see docs/deploying.md).
#
# Why this exists: Sentry only reports exceptions thrown by running code, so a backend that is stopped, crash-looping
# or answering 502 throws nothing and stays invisible. The VM's other Healthchecks.io heartbeats are all worker or
# scheduler tasks (ingestion, upload, backup, digest, download, alerts, restore); none proves the public API is up.
# This probe is that missing check: it calls the API the way a visitor's browser does, independently of the app
# containers, and only reports healthy when a real reading comes back.
#
# Settings (environment, all optional):
#   UPTIME_URL             the API endpoint to probe (default https://welldash.mcmaster.ca/api/latest)
#   HEALTHCHECK_URL_UPTIME a Healthchecks.io ping URL: pinged on success, <url>/fail on a failure. Unset (the
#                          default), the script only prints the result and sets the exit code, pinging nothing, so it
#                          is safe to run by hand.
#   UPTIME_CURL_TIMEOUT    seconds to wait for the API (default 20)
# CURL exists for tests.
#
# Healthy means HTTP 200 and a body that contains a reading ("recorded_at"): a 200 serving an empty "[]" or an error
# page that happens to return 200 is treated as down, because the dashboard would show no data.
#
# Setting it up (once, on the VM): add this to the crontab of the user that owns ~/WELLWebsite (crontab -e). It runs
# every 5 minutes and appends to uptime.log (gitignored):
#
#   */5 * * * * cd ~/WELLWebsite && HEALTHCHECK_URL_UPTIME=https://hc-ping.com/<uuid> ./uptime_check.sh >>uptime.log 2>&1
#
set -euo pipefail

URL=${UPTIME_URL:-https://welldash.mcmaster.ca/api/latest}
TIMEOUT=${UPTIME_CURL_TIMEOUT:-20}
CURL=${CURL:-curl}

# A UTC ISO-8601 timestamp at the start of each line, so log entries sort and read unambiguously wherever the VM runs
log() { echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') $*"; }
# Pings HEALTHCHECK_URL_UPTIME (if set) with the suffix in $1 ("" for success, /fail); a failed ping is ignored and
# never changes the exit code. The ping URL is never printed, so it stays out of the log.
ping_hc() {
  if [ -n "${HEALTHCHECK_URL_UPTIME:-}" ]; then
    "$CURL" -fsS -m 10 --retry 3 -o /dev/null "$HEALTHCHECK_URL_UPTIME$1" || true
  fi
}

# One request: the response body followed by a newline and the HTTP status code. A connection failure (the backend is
# down, DNS fails, the request times out) leaves an empty response, caught below. The body may hold newlines, so the
# status is taken as everything after the last one.
response=$("$CURL" -s -m "$TIMEOUT" -w '\n%{http_code}' "$URL" 2>/dev/null || true)
code=${response##*$'\n'}
body=${response%$'\n'*}

reason=""
if [ -z "$response" ] || [ "$code" = 000 ] || ! [[ "$code" =~ ^[0-9]{3}$ ]]; then
  reason="no response"
elif [ "$code" != 200 ]; then
  reason="HTTP $code"
elif [[ "$body" != *'"recorded_at"'* ]]; then
  reason="200 but no readings"
fi

if [ -z "$reason" ]; then
  log "OK $URL is serving readings (HTTP 200)"
  ping_hc ""
  exit 0
fi
log "FAIL $URL: $reason"
ping_hc /fail
exit 1
