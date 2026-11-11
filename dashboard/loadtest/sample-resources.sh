#!/usr/bin/env bash
# Samples the load test's containers and the Next.js server every few seconds while k6 runs, as CSV (one row per
# sample) for resources-summary.sh: CPU (% of one core) and memory of each, and PostgreSQL's connections and
# export queue. Runs until killed.
#
# sample-resources.sh <output.csv> <next server pid> [interval seconds]
set -u
out=$1
next_pid=$2
interval=${3:-5}
containers=(lt-backend lt-export-worker lt-postgres lt-redis)
clk=$(getconf CLK_TCK)

# CPU seconds used so far by a process and its descendants (the Next.js server may start workers).
cpu_ticks() {
  local total=0 pid stat
  for pid in $1 $(pgrep -P "$1" 2>/dev/null); do
    stat=$(cut -d' ' -f14,15 "/proc/$pid/stat" 2>/dev/null) || continue
    total=$((total + ${stat% *} + ${stat#* }))
  done
  echo "$total"
}

rss_mib() {
  local total=0 pid kb
  for pid in $1 $(pgrep -P "$1" 2>/dev/null); do
    kb=$(awk '/^VmRSS:/ {print $2}' "/proc/$pid/status" 2>/dev/null) || continue
    total=$((total + ${kb:-0}))
  done
  echo $((total / 1024))
}

# psql_at <database> <empty fields if it fails> <query>: one row, comma-separated.
psql_at() { docker exec lt-postgres psql -U postgres -d "$1" -tAF, -c "$3" 2>/dev/null || echo "$2"; }

header="elapsed_s"
for c in "${containers[@]}"; do header+=",${c}_cpu_pct,${c}_mem_mib"; done
header+=",next_cpu_pct,next_mem_mib,pg_active,pg_connections,pg_parallel_workers,exports_queued,exports_running"
echo "$header" > "$out"

start=$(date +%s)
prev_ticks=$(cpu_ticks "$next_pid")
prev_time=$(date +%s.%N)
while true; do
  row="$(( $(date +%s) - start ))"
  stats=$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}' "${containers[@]}" 2>/dev/null)
  for c in "${containers[@]}"; do
    # "lt-backend 87.31% 412.5MiB / 15.6GiB" -> 87.31,412.5
    row+=,$(awk -v name="$c" '$1 == name {
      cpu = $2; sub("%", "", cpu); mem = $3; v = mem + 0
      if (mem ~ /GiB$/) v *= 1024; else if (mem ~ /KiB$/) v /= 1024; else if (mem ~ /[0-9]B$/) v /= 1048576
      printf "%s,%.1f", cpu, v; found = 1 }
      END { if (!found) printf "," }' <<< "$stats")
  done
  ticks=$(cpu_ticks "$next_pid")
  now=$(date +%s.%N)
  row+=,$(awk -v d="$((ticks - prev_ticks))" -v t="$(awk -v a="$now" -v b="$prev_time" 'BEGIN {print a - b}')" \
    -v clk="$clk" 'BEGIN { printf "%.1f", (t > 0 ? 100 * d / clk / t : 0) }'),$(rss_mib "$next_pid")
  prev_ticks=$ticks
  prev_time=$now
  # Connections the backend and export worker opened (active: running a query), and the parallel workers
  # PostgreSQL started to help with big queries (they count against max_worker_processes, not max_connections).
  row+=,$(psql_at postgres ",," "SELECT count(*) FILTER (WHERE backend_type = 'client backend' AND state = 'active'),
                                        count(*) FILTER (WHERE backend_type = 'client backend'),
                                        count(*) FILTER (WHERE backend_type = 'parallel worker')
                                 FROM pg_stat_activity WHERE datname = 'well' AND pid <> pg_backend_pid()")
  row+=,$(psql_at well "," "SELECT count(*) FILTER (WHERE status = 'queued'), count(*) FILTER (WHERE status = 'running')
                        FROM export_jobs")
  echo "$row" >> "$out"
  sleep "$interval"
done
