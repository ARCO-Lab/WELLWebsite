#!/usr/bin/env bash
# Keeps one GitHub issue in step with the daily API canary (.github/workflows/canary.yml):
#  - failed run: comments on the open issue labelled "canary", or opens one (assigned, labelled) if none is open;
#  - passed run: if one is open, comments that the canary recovered and closes it. Nothing happens otherwise.
# The issue text is the canary's OK/FAIL lines (which never contain URLs, keys or response bodies) and a link to
# the run. Uses the gh CLI with GH_TOKEN and GH_REPO from the environment.
#   bash .github/scripts/canary_issue.sh <success|failure> <file with the canary's output> <run URL>
set -euo pipefail

outcome=$1 report=$2 run_url=$3
GH=${GH:-gh}
LABEL=canary
TITLE="API canary failing"
ASSIGNEE=${CANARY_ISSUE_ASSIGNEE:-lukhsaankumar}

open=$("$GH" issue list --state open --label "$LABEL" --limit 1 --json number --jq '.[0].number // empty')

body=$(mktemp)
trap 'rm -f "$body"' EXIT

if [ "$outcome" = success ]; then
  if [ -n "$open" ]; then
    "$GH" issue close "$open" --comment "Recovered: every source passed in $run_url"
    echo "closed issue #$open"
  else
    echo "canary passed, no open issue"
  fi
  exit 0
fi

# Only the canary's own result lines are posted, as a second guard against anything else reaching the issue.
lines=$(grep -E '^(OK|FAIL) ' "$report" 2>/dev/null || true)
fence='```'
{
  echo "The API canary failed in $run_url"
  echo
  if [ -n "$lines" ]; then
    printf '%s\n%s\n%s\n' "$fence" "$lines" "$fence"
  else
    echo "The canary printed no results: it may not have started, or GitHub withheld its output because it"
    echo "matched a secret's value (the run log says \"Skip output 'report'\" then). See the run log."
  fi
} > "$body"

if [ -n "$open" ]; then
  "$GH" issue comment "$open" --body-file "$body"
  echo "commented on issue #$open"
else
  {
    echo
    echo "This issue is updated by each failing run and closed by the next passing one. See .github/workflows/README.md,"
    echo "\"API canary\", for what each source checks and how to rotate a key."
  } >> "$body"
  "$GH" label create "$LABEL" --color D93F0B --description "Opened by the daily API canary" --force > /dev/null
  "$GH" issue create --title "$TITLE" --label "$LABEL" --assignee "$ASSIGNEE" --body-file "$body"
fi
