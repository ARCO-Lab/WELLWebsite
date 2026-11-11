#!/usr/bin/env bash
# shellcheck disable=SC2016  # check's conditions are single-quoted on purpose: check evals them later
# Tests canary_issue.sh against a stub `gh` that records each call and answers `issue list` with $OPEN_ISSUE
# (empty: no open canary issue). Nothing contacts GitHub.
#   bash .github/scripts/test_canary_issue.sh
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT

# The stub saves the body of each --body-file it is given, since the script deletes that file when it exits.
cat > "$T/gh" <<'EOF'
#!/bin/sh
echo "gh $*" >> "$STUB_LOG"
prev=
for a in "$@"; do
  [ "$prev" = --body-file ] && cat "$a" >> "$STUB_BODY"
  prev=$a
done
case "$*" in
  "issue list"*) [ -n "${OPEN_ISSUE:-}" ] && echo "$OPEN_ISSUE" ;;
  "issue create"*) echo "https://github.test/issues/9" ;;
esac
exit 0
EOF
chmod +x "$T/gh"
export GH=$T/gh STUB_LOG=$T/log STUB_BODY=$T/body
RUN=https://github.test/actions/runs/1

printf 'OK   LI-COR: HTTP 200, 12 records\nFAIL Borealis: HTTP 401\nTraceback: https://secret.test/?key=abc\n' > "$T/failed.txt"
: > "$T/empty.txt"

run() { # run <outcome> <report file>
  : > "$STUB_LOG"; : > "$STUB_BODY"
  bash "$ROOT/.github/scripts/canary_issue.sh" "$1" "$2" "$RUN" > "$T/out" 2>&1; echo $? > "$T/rc"
}
ran() { grep -qF -- "$1" "$STUB_LOG"; }
posted() { grep -qF -- "$1" "$STUB_BODY"; }
calls() { [ "$(wc -l < "$STUB_LOG")" -eq "$1" ]; }
rc() { [ "$(cat "$T/rc")" = "$1" ]; }

pass=0 failures=0
check() {
  if eval "$2"; then echo "PASS  $1"; pass=$((pass + 1))
  else
    echo "FAIL  $1"; echo "      output: $(tr '\n' ' ' < "$T/out")"; echo "      gh: $(tr '\n' ';' < "$STUB_LOG")"
    failures=$((failures + 1))
  fi
}

OPEN_ISSUE="" run failure "$T/failed.txt"
check "failure, no open issue: creates the label and opens an assigned issue" \
  'rc 0 && ran "issue list --state open --label canary" && ran "label create canary" \
   && ran "issue create --title API canary failing --label canary --assignee lukhsaankumar --body-file" \
   && ! ran "issue comment" && calls 3'
check "failure: posts the OK/FAIL lines and the run link" \
  'posted "OK   LI-COR: HTTP 200, 12 records" && posted "FAIL Borealis: HTTP 401" && posted "$RUN"'
check "failure: posts nothing but the result lines" '! posted "Traceback" && ! posted "secret.test"'

OPEN_ISSUE=7 run failure "$T/failed.txt"
check "failure, issue #7 open: comments on it, opens nothing" \
  'rc 0 && ran "issue comment 7 --body-file" && ! ran "issue create" && ! ran "label create" && calls 2 \
   && posted "FAIL Borealis: HTTP 401" && posted "$RUN"'

OPEN_ISSUE=7 run failure "$T/empty.txt"
check "failure with no result lines (canary didn't run): still reported, says so" \
  'rc 0 && ran "issue comment 7" && posted "printed no results" && posted "$RUN"'

OPEN_ISSUE=7 run failure "$T/missing.txt"
check "failure with no output file at all: still reported" 'rc 0 && ran "issue comment 7" && posted "printed no results"'

OPEN_ISSUE=7 run success "$T/failed.txt"
check "success, issue #7 open: closes it with a recovered comment and the run link" \
  'rc 0 && ran "issue close 7 --comment Recovered: every source passed in $RUN" && calls 2'

OPEN_ISSUE="" run success "$T/empty.txt"
check "success, no open issue: only looks" 'rc 0 && calls 1 && ran "issue list"'

# A step with no `shell:` runs as `bash -e` without pipefail, so `canary | tee` would pass when the canary fails
# (and close the issue as recovered). Every canary.yml step with a pipe on its run: line must set `shell: bash`.
: > "$STUB_LOG"
awk '/^      - /             { if (pipe && !bash) print step; pipe = 0; bash = 0; step = $0 }
     /^        shell: bash$/ { bash = 1 }
     /^        run: .* \| /  { pipe = 1 }
     END                     { if (pipe && !bash) print step }' "$ROOT/.github/workflows/canary.yml" > "$T/out"
check "canary.yml: every step that pipes its run: line sets shell: bash (pipefail)" \
  '[ ! -s "$T/out" ] && grep -q "api_canary.py | tee" "$ROOT/.github/workflows/canary.yml"'

echo "$pass passed, $failures failed"
[ "$failures" = 0 ]
