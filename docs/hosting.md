# Hosting

How the two sites are hosted: the VM, the Docker services, where data is stored, and the host firewall rule the stack
depends on. Deploying is in [deploying.md](deploying.md); every setting is in [configuration.md](configuration.md).

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

**Embedding and framing.** The dashboard is embedded with an iframe on a dedicated WordPress page. This repository sets
no Content-Security-Policy, `frame-ancestors` or `X-Frame-Options` header, so any site can frame the dashboard. The
Flask API accepts requests from any origin (`CORS(app)` in `server.py`), but it has no public port: browsers only reach
the dashboard's API routes. The data is public and read-only; nothing on the dashboard needs a login.

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
