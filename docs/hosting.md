# Hosting

How the two sites are hosted: the VM, the Docker services, where data is stored, the user the containers run as,
the host firewall rule the stack depends on, and who can reach the published ports. Deploying is in [deploying.md](deploying.md); every setting is in [configuration.md](configuration.md).

## The VM and the Docker services

Both sites run in Docker on one Linux VM (`docker-compose.yml`): WordPress on port 8080 and the dashboard on port 8081.
Neither container serves HTTPS: both hostnames point at McMaster's reverse proxy (`haproxy.cas.mcmaster.ca`), which
terminates TLS and forwards to the VM. That proxy's configuration isn't in this repository. `nginx.conf` and the
commented-out `proxy` service in `docker-compose.yml` are for local development only.

- Seven Docker Compose services: `db` (MySQL), `wordpress` (the stock image with `home/` mounted), `backend`, `redis`,
  `worker`, `export_worker` and `dashboard` (`backend`, `worker` and `export_worker` are built from one image). An
  eighth, `ops` ([welldash²](../dashboard/backend/app/ops/README.md)), starts only with the `ops` compose profile.
- Each service has a memory limit (`mem_limit`, several times its normal use) and a size cap on Docker's own log
  (10 MB x 5 files). `backend`, `dashboard`, `worker`, `redis` and `ops` have health checks, shown by
  `docker compose ps`. Redis is capped at 256 MB and keeps nothing on disk; when full it evicts cache entries only,
  never the export queue.
- TLS and the public hostnames are handled by McMaster's reverse proxy, outside this repository.
- Secrets are injected through env files that aren't committed (see [configuration.md](configuration.md)).
- The VM runs `main`, deployed by `deploy.sh` (see [deploying.md](deploying.md)).

**Routing, end to end.** `welldash.mcmaster.ca` and `well.mcmaster.ca` both point at the reverse proxy, which forwards
to the dashboard container on port 8081 and to WordPress on port 8080. The browser calls the dashboard's own API routes
(`/api/...`), which pass the request to the Flask backend on the internal Docker network. The API routes are listed in
[the backend README](../dashboard/backend/README.md#api); none are versioned.

**Embedding and framing.** The dashboard is embedded with an iframe on a dedicated WordPress page. Every dashboard
response carries a `Content-Security-Policy` whose `frame-ancestors` allows only the dashboard itself,
`well.mcmaster.ca` (with and without `www`) and `NEXT_PUBLIC_WP_HOME`'s origin, so other sites can't frame it; it also
sends `X-Content-Type-Options: nosniff` and `Referrer-Policy: strict-origin-when-cross-origin` (all set in
`dashboard/frontend/next.config.ts`, see [the dashboard README](../dashboard/frontend/README.md#rate-limits-and-security-headers)).
Whether haproxy adds HSTS is outside this repository. The Flask API sends no CORS headers, so no other site's pages may
read it; it has no public port, and browsers only reach the dashboard's API routes. The data is public and read-only;
nothing on the dashboard needs a login.

**The embedded page.** The WordPress Dashboard page (`page-dashboard.php`) frames `/?embed=1`, which the dashboard
serves from a static page without its header and footer, so they never flash in the frame. The two pages exchange
`postMessage` messages, each checking the other's origin: the dashboard sends its height and the theme's
`js/dashboard-embed.js` sizes the iframe to it, so there is no scrollbar inside the frame. The dashboard only talks to
`https://well.mcmaster.ca`, `https://www.well.mcmaster.ca` and the origin of `NEXT_PUBLIC_WP_HOME` (a build argument),
and the theme only listens to the origin of `DASHBOARD_URL`. Any other framing (an old link without `?embed=1`)
still hides the header and footer, from a check that runs before the first paint. Details are in
`dashboard/frontend/src/lib/embed.ts`.

## Storage

- **PostgreSQL** 13 on the VM host: sensor readings, sampling results, export jobs, alert state, and the record of
  applied migrations (`dashboard/backend/app/db/models.py`). Readings are in `sensor_measurements`, one row per reading
  with a unique index on (station, measurement, time); creek sampling results are in `sampling_measurements`.
- Schema changes are numbered SQL migrations, applied by hand (see
  [Database migrations](../dashboard/backend/README.md#database-migrations)).
- Worker logs and the records of uploaded months are files in `dashboard/backend/app/logs/`, mounted from the host.
  Each `*.log` the worker writes is rotated at 5 MB (`name.log.1` to `.3` are the older copies; the oldest is deleted),
  and a log it can't write never stops a job (`utils/worklog.py`).
- Export CSVs stay in the `exports_data` Docker volume for `EXPORT_FILE_TTL_MINUTES`.
- WordPress keeps its own data in MySQL 5.7 (the `db` container, `db_data` volume).
- Nightly `pg_dump` backups of the database on the VM, 7 daily + 8 weekly kept
  ([Database backups](../dashboard/backend/README.md#database-backups)).
- Nightly backups of the WordPress database and uploads on the VM (`wordpress/backup.sh` from cron), 7 daily + 8
  weekly + 12 monthly kept ([Backups](../wordpress/README.md#backups)).

## Containers run unprivileged

`backend`, `worker`, `export_worker` and `ops` run as an unprivileged user, not root: uid and gid 10001 from the
image (`dashboard/backend/Dockerfile`), or `BACKEND_UID` and `BACKEND_GID` from `.env`. `dashboard` runs as the
image's `nextjs` user. All five have every Linux capability dropped and `no-new-privileges` set (`x-unprivileged` in
`docker-compose.yml`), so code running in them can't become root or use a setuid program. The stock MySQL, WordPress
and Redis images start as root to switch to their own user, so they keep Docker's defaults.

The worker writes into two folders of the checkout, `dashboard/backend/app/logs/` and `backups/`, and `backend` and
`export_worker` into the `exports_data` volume, so the containers' user must own them. On the VM, run the containers
as the user that owns the checkout, and give that user what earlier containers wrote as root. Once, from
`~/WELLWebsite` (no sudo needed: a throwaway container does the `chown`, with only the capabilities it needs):

```bash
uid=$(id -u) gid=$(id -g)
grep -q '^BACKEND_UID=' .env || printf 'BACKEND_UID=%s\nBACKEND_GID=%s\n' "$uid" "$gid" >> .env
docker compose build backend worker export_worker
docker compose run --rm --no-deps --user 0 --cap-add CHOWN --cap-add DAC_READ_SEARCH --entrypoint chown \
  worker -R "$uid:$gid" /app/app/logs /app/backups
docker compose run --rm --no-deps --user 0 --cap-add CHOWN --cap-add DAC_READ_SEARCH --entrypoint chown \
  export_worker -R "$uid:$gid" /app/app/exports
```

The backups stay private: `scripts/backup_db.py` makes their folders 0700 and the files 0600, now owned by that user
instead of root. Scripts run by hand with `docker compose exec worker ...` run as the same user, and write their
files (`logs/`, `backups/`) as that user too. CI starts these services from `docker-compose.yml` the same way and
checks that each runs unprivileged and can write where it must (`.github/scripts/test_compose_runtime.sh`).

## Host firewall (required)

PostgreSQL runs on the VM itself, not in Docker, and the containers connect to it on the host's IP, port 5432. The
host's iptables service loads `/etc/sysconfig/iptables` at boot, and that file must contain this line above its final
`-A INPUT -j REJECT` line:

```
-A INPUT -s 10.20.0.0/16 -p tcp -m tcp --dport 5432 -m comment --comment "WELL dashboard: Docker containers to host PostgreSQL (required)" -j ACCEPT
```

Without it, every container fails with "No route to host" after the next reboot, and ingestion stops. To add it without
a reboot as well, run `sudo iptables -I INPUT -s 10.20.0.0/16 -p tcp --dport 5432 -j ACCEPT`. Never run
`systemctl restart iptables`, which wipes Docker's own rules until Docker restarts. Never run
`iptables-save > /etc/sysconfig/iptables` either, which would save Docker's temporary rules into the file.

Of the Docker networks in `10.20.0.0/16`, `10.20.2.0/24` is `wp_probe`, used only by welldash²'s check of WordPress
(see [welldash²](../dashboard/backend/app/ops/README.md)). Nothing on it needs PostgreSQL, so a narrower rule should
leave it out: welldash² reaches PostgreSQL from `internal_api`, which carries its default route.

## Who can reach the published ports

WordPress (8080) and the dashboard (8081) are published on every address the VM has, so that the reverse proxy
(`haproxy.cas.mcmaster.ca`, `130.113.68.30`) can reach them; welldash² (8090) is published on `OPS_BIND` only. Ports
Docker publishes skip the host's `INPUT` rules (the rule above doesn't apply to them), so anything that can route to
the VM reaches WordPress's login and the dashboard directly, around the proxy and its TLS. Two ways to narrow that,
best used together:

- **Publish on one address**: set `WORDPRESS_BIND` and `DASHBOARD_BIND` in `.env` to the address the proxy connects
  to (unset: every address, as before). Then add `DEPLOY_SITE_HOST=<that address>` to `deploy.sh`'s cron line, since
  its health checks otherwise call `127.0.0.1`.
- **Allow only the proxy**, in Docker's `DOCKER-USER` chain, which Docker leaves to the administrator and checks
  before its own rules. The rules match the port the client connected to (conntrack's original destination, before
  Docker rewrites it), so traffic between containers and `deploy.sh`'s checks from the VM itself aren't affected:
  ```bash
  # -I inserts at the top, so the DROP rules go in first and the proxy's exceptions above them
  sudo iptables -I DOCKER-USER -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 8080 -j DROP
  sudo iptables -I DOCKER-USER -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 8081 -j DROP
  sudo iptables -I DOCKER-USER -p tcp -s 130.113.68.30 -m conntrack --ctdir ORIGINAL --ctorigdstport 8080 -j RETURN
  sudo iptables -I DOCKER-USER -p tcp -s 130.113.68.30 -m conntrack --ctdir ORIGINAL --ctorigdstport 8081 -j RETURN
  sudo iptables -L DOCKER-USER -n -v --line-numbers
  ```
  Then check that https://well.mcmaster.ca and https://welldash.mcmaster.ca still load; the same commands with `-D`
  in place of `-I` remove them. The same pattern can limit 8090 to the campus and VPN ranges when welldash² is on the
  campus address. Docker publishes the ports on IPv6 too: if the VM has a routable IPv6 address, add the same rules
  with `ip6tables`.

  Rules added this way are lost at the next reboot. To keep them, add them to `/etc/sysconfig/iptables` like the
  rule above: in its `*filter` section, a `:DOCKER-USER - [0:0]` line with the other chain lines, then the rules with
  `-A` in place of `-I` and in the opposite order (the two `RETURN` lines first, then the two `DROP` lines). Check
  `sudo iptables -L DOCKER-USER -n` after the next reboot.
