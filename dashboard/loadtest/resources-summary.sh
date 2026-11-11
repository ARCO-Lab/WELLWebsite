#!/usr/bin/env bash
# Markdown tables of what sample-resources.sh recorded, one column per phase of the run.
#
# resources-summary.sh <samples.csv> <name:start_s:end_s>...
# e.g. resources-summary.sh resources.csv 30_at_once:0:120 30_steady:210:390 50_steady:510:630 (_ shows as a space)
set -eu
csv=$1
shift

awk -F, -v windows="$*" '
  function avg(k, unit) { return n[k] ? sprintf("%.0f%s", sum[k] / n[k], unit) : "–" }
  function top(k, unit) { return (k in hi) ? sprintf("%.0f%s", hi[k], unit) : "–" }
  NR == 1 { for (i = 1; i <= NF; i++) col[$i] = i; next }
  {
    nw = split(windows, w, " ")
    for (j = 1; j <= nw; j++) {
      split(w[j], part, ":")
      if ($1 < part[2] || $1 > part[3]) continue
      for (name in col) {
        if (name == "elapsed_s" || $col[name] == "") continue
        k = j SUBSEP name
        sum[k] += $col[name]; n[k]++
        if (!(k in hi) || $col[name] + 0 > hi[k]) hi[k] = $col[name] + 0
      }
      k = j SUBSEP "queue"
      q = $col["exports_queued"] + $col["exports_running"]
      if (!(k in hi) || q > hi[k]) hi[k] = q
    }
  }
  END {
    nw = split(windows, w, " ")
    head = "| |"; rule = "|---|"
    for (j = 1; j <= nw; j++) { split(w[j], part, ":"); gsub("_", " ", part[1]); head = head " " part[1] " |"; rule = rule "---:|" }
    print "CPU is % of one core (the runner has " cores " cores); memory is the most seen. Average / peak per phase."; print ""
    print head; print rule
    split("lt-backend:backend (gunicorn 3x4),lt-export-worker:export worker,lt-postgres:PostgreSQL,lt-redis:Redis,next:Next.js server", rows, ",")
    for (r = 1; r <= 5; r++) {
      split(rows[r], p, ":")
      line = "| " p[2] " CPU |"; mem = "| " p[2] " memory |"
      for (j = 1; j <= nw; j++) {
        line = line " " avg(j SUBSEP p[1] "_cpu_pct", "%") " / " top(j SUBSEP p[1] "_cpu_pct", "%") " |"
        mem = mem " " top(j SUBSEP p[1] "_mem_mib", " MiB") " |"
      }
      print line; print mem
    }
    a = "| PostgreSQL connections, running a query / open (peak) |"; q = "| Exports queued + running (peak) |"
    pw = "| PostgreSQL parallel workers (peak) |"
    for (j = 1; j <= nw; j++) {
      a = a " " top(j SUBSEP "pg_active", "") " / " top(j SUBSEP "pg_connections", "") " |"
      pw = pw " " top(j SUBSEP "pg_parallel_workers", "") " |"
      q = q " " top(j SUBSEP "queue", "") " |"
    }
    print a; print pw; print q
  }
' cores="$(nproc)" "$csv"
