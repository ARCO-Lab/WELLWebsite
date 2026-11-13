# welldash² (operations dashboard)

welldash² ("WELLdashSquared") is a small, read-only dashboard for whoever runs the site. The recommended way to reach
it is **an SSH tunnel to the VM** ([below](#reaching-it-through-an-ssh-tunnel-recommended)), with `OPS_BIND=127.0.0.1`
so no network can reach the port at all. It can instead be published on the VM's campus address, for McMaster's network
and VPN only, at **http://well.cas.mcmaster.ca:8090** (the port is `OPS_PORT`). It asks for one shared password; there
is no user name. It has five pages:

- **Overview**: whether the dashboard (with its data API and database) and the WordPress site answer right now; data
  freshness per group (the `/health/data` rules); open and recently cleared email alerts; the vendor APIs' latest call
  outcome; CI of `main` (GitHub Actions); recent deploys (from `deploy.log`, see below); and, when their read-only keys
  are set, unresolved Sentry issues of the last 24 h and the Healthchecks.io job heartbeats.
- **Uptime**: availability over 24 h, 7 and 30 days, response time, and every stretch of downtime in the last 30
  days. welldash² itself checks the dashboard's home page, the data API's `/api/latest` (which reads the database) and
  the WordPress home page once a minute, from inside the VM (WordPress over a small network of its own, `wp_probe`, so
  welldash² never shares a network with MySQL). These checks aren't counted as traffic.
- **Traffic**: the data API's requests, server and client errors, p95 response time, data sent, busiest minute and CSV
  downloads, per hour or day and per route; plus the export jobs (by status, rows written, run times, failures, the
  queue now). The backend counts its requests per minute by route pattern, method and status class
  (`utils/traffic.py`); no IP addresses, query strings or browser details are recorded. The daily digest has a
  "Traffic yesterday" summary from the same numbers.
- **System**: database version and size, the largest tables, applied migrations, and the size of each log file in
  `dashboard/backend/app/logs`. Container states and disk space aren't shown: they would need the Docker socket, which
  gives full control of the VM.
- **Visitors**: page-view counts from GoatCounter when it is set up
  ([Visitor counts](../../../frontend/README.md#visitor-counts-goatcounter)); otherwise "not configured".

It runs as the `ops` service in `docker-compose.yml` (code in this folder, built from the backend's image, with no
JavaScript or outside files), and stores its uptime checks and the request counts in two tables from migration
`0005_ops_metrics.sql`, kept for 90 days (`OPS_RETENTION_DAYS`). The service starts only when the `ops` compose
profile is on, and refuses to start without its password hash, secret key and `OPS_BIND`.

**Never route it through the public proxy.** `haproxy.cas.mcmaster.ca` forwards `welldash.mcmaster.ca` to port 8081
and `well.mcmaster.ca` to port 8080; it must never forward anything to 8090. welldash² takes the client's address
straight from the connection for its login limit, and is meant to be reachable from the McMaster network only.

## Setting it up

On the VM, from `~/WELLWebsite`:

1. Apply the migration (take a backup first, as in
   [Database migrations](../../README.md#database-migrations)) and rebuild the backend, which then starts counting
   requests:
   ```bash
   ./deploy.sh
   docker compose exec backend python scripts/migrate.py           # applies 0005_ops_metrics
   ```
2. Make the password hash and a secret key. This asks for the password twice (at least 12 characters; nothing is
   shown or stored) and prints two lines, `OPS_PASSWORD_HASH='...'` and `OPS_SECRET_KEY='...'`:
   ```bash
   docker compose exec backend python -m ops.hashpw
   ```
3. Add those two lines, `COMPOSE_PROFILES=ops` and `OPS_BIND` to `.env` in `~/WELLWebsite` (the env file docker
   compose reads, which already holds the other passwords), and keep it readable by you only. `OPS_BIND=127.0.0.1`
   (recommended) is for the SSH tunnel below; `OPS_BIND=130.113.68.63` is the VM's campus address, which
   `well.cas.mcmaster.ca` resolves to (check with `getent hosts well.cas.mcmaster.ca`). Keep `umask` in a subshell, so
   files created later in the same shell aren't private too:
   ```bash
   (umask 077 && nano .env)   # paste the two lines as printed (keep the single quotes); add COMPOSE_PROFILES=ops and OPS_BIND=...
   chmod 600 .env
   ```
   `OPS_BIND` publishes the port on that address only. Ports Docker publishes bypass the VM's own firewall rules
   (ufw, iptables INPUT), so welldash² refuses to start when `OPS_BIND` is unset or `0.0.0.0`/`::` (every address),
   unless `OPS_ALLOW_ANY_ADDRESS=1` is also set. The single quotes matter: the hash contains `$` signs, which compose
   would otherwise read as variables (welldash² then refuses to start, and says so). Never put the password itself in
   any file, only its hash.
4. Start it:
   ```bash
   docker compose up -d --build --no-deps ops
   ```
5. Check it:
   ```bash
   docker compose logs --tail 20 ops      # no "welldash² not started" line
   curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/login   # 200 (use your OPS_BIND address)
   curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/        # 302 (to the login page)
   ```
   Then open it through the tunnel below, or, with the campus address, on the VPN at
   http://well.cas.mcmaster.ca:8090, and sign in. The Uptime page shows its first checks after a minute, and the
   Traffic page the first requests a minute or two after someone uses the dashboard. With the campus address, if the
   page doesn't load from your laptop but the `curl` lines work on the VM, a firewall blocks port 8090: McMaster IT can
   allow TCP 8090 to the VM from the campus network and the VPN address ranges.

### Reaching it through an SSH tunnel (recommended)

With `OPS_BIND=127.0.0.1` the port is open on the VM's loopback only, and SSH carries the password and the session
cookie encrypted, with no certificate and no firewall rule needed. From your laptop (on the VPN, with the SSH access
you already use for the VM):
```bash
ssh -N -L 8090:127.0.0.1:8090 <you>@well.cas.mcmaster.ca
```
then open http://localhost:8090 and leave the command running while you use it (Ctrl+C ends the tunnel). Any free
local port works in place of the first `8090`. Everyone using the tunnel reaches welldash² from the same Docker
address, so they share one failed-login count.

With `COMPOSE_PROFILES=ops` set, `docker compose up -d --build` includes welldash², and `./deploy.sh` rebuilds it with
the backend whenever it is running. To stop it: `docker compose stop ops`, and remove `COMPOSE_PROFILES=ops` from
`.env` to keep it off.

**Changing the password.** Run `docker compose exec backend python -m ops.hashpw --hash-only`, replace the
`OPS_PASSWORD_HASH` line in `.env` with the one it prints, and recreate the container:
`docker compose up -d --no-deps ops`. Everyone is signed out. A new `OPS_SECRET_KEY` also signs everyone out.

## How it is protected

One password, checked against its scrypt hash in constant time, and only after the form's CSRF token and the
failed-login limit have passed, so nobody can make the service hash passwords faster than the limit allows. After 5
failed attempts (a wrong password or a bad CSRF token) from one address in 15 minutes, that address is refused until
the 15 minutes have passed. Other addresses' failures never lock anyone out: when 50 or more have failed from all
addresses together, each address that has failed must also wait a minute between tries, and an address with no
failures can still sign in. (Clients that reach the VM from the same address, as through some NAT paths or the SSH
tunnel, share one count; at worst a stranger's attempts lock them out for 15 minutes.) The session is a signed cookie
(`OPS_SECRET_KEY`), HttpOnly and SameSite=Strict, that lasts 8 hours from login however it is used. Each login also
has a random id that the service keeps in memory: "Sign out" deletes it, so the cookie stops working even if a copy
of it was taken, and restarting the service (a deploy that rebuilds it, for example) signs everyone out. The login
and sign-out forms carry a CSRF token.
Every page except the login page needs the session, and every page is read-only: the pages read the database in
read-only transactions, and no value from a request reaches the SQL. Pages send a Content-Security-Policy
(`default-src 'self'`, no scripts, `frame-ancestors 'none'`), `nosniff` and `noindex`. welldash²'s only writes are its
uptime checks and the daily deletion of rows older than 90 days.

**HTTP or HTTPS.** Published on the campus address over plain HTTP, the password and the session cookie travel
unencrypted between the VPN and the VM, so someone able to watch McMaster's internal network could read them. The SSH
tunnel avoids that. If TLS is set up in front of port 8090 instead (with a certificate from McMaster's internal
certificate authority), the cookie is marked Secure on every request that came over HTTPS without any setting; set
`OPS_COOKIE_SECURE=1` in `.env` as well (and recreate the container) if the TLS proxy's `X-Forwarded-Proto` isn't
trusted by gunicorn (its `FORWARDED_ALLOW_IPS`), so the cookie is never sent over HTTP. With `OPS_COOKIE_SECURE=1`
but no HTTPS, signing in silently fails (the browser drops the cookie).

### A read-only database role (recommended)

By default welldash² uses the backend's role (`BACKEND_DATABASE_URL`). A role of its own limits what it could do if it
were ever compromised. `dashboard/backend/app/db/roles.sql` creates it, `well_ops`, together with the backend's
`well_app`: `SELECT` on every table, and as its only writes `INSERT` and `DELETE` on `uptime_probes` (its uptime
checks and their 90-day cleanup) and `DELETE` on `request_metrics` (the cleanup). The steps (running it, a password,
`pg_hba.conf`, `.env`, checking, rolling back) are in
[Database roles](../../README.md#database-roles). In short, set
`OPS_DATABASE_URL=postgresql://well_ops:<password>@host.docker.internal:5432/<database>` in `.env` and recreate the
container. The System page shows which role welldash² reads with.

### Showing deploys

The Overview lists deploys from `deploy.log` in the logs folder it can read (`dashboard/backend/app/logs`, mounted
read-only). `deploy.sh` writes `~/WELLWebsite/deploy.log` by default, which welldash² can't see; to show deploys, set
`DEPLOY_LOG=$HOME/WELLWebsite/dashboard/backend/app/logs/deploy.log` in the cron line
([docs/deploying.md](../../../../docs/deploying.md)) and send cron's stderr there too, if that folder is writable by
your user.

## Settings

In `.env` at the repository root; recreate the container after changing them.

| Variable | Default | Meaning |
|---|---|---|
| `OPS_PORT` | `8090` | Port on the VM. |
| `OPS_BIND` | required | Address the port is published on: `127.0.0.1` for the SSH tunnel, or the VM's campus address (setup step 3). Unset or every address (`0.0.0.0`, `::`), the service refuses to start. |
| `OPS_ALLOW_ANY_ADDRESS` | off | `1` lets `OPS_BIND` be `0.0.0.0` or `::`, for when publishing on every address is really meant. |
| `OPS_COOKIE_SECURE` | unset | Unset, the cookie is marked Secure on requests that came over HTTPS. `1` marks it Secure always (see above). |
| `OPS_DATABASE_URL` | `BACKEND_DATABASE_URL` | Database URL, with the read-only `well_ops` role above. |
| `OPS_GITHUB_TOKEN` | none | Optional: GitHub allows 60 unauthenticated API requests an hour, plenty with the 5-minute cache. |
| `OPS_SENTRY_API_TOKEN`, `OPS_SENTRY_ORG` | none | A Sentry auth token with read-only scopes (`org:read`, `project:read`, `event:read`) and the organisation's slug. `OPS_SENTRY_API_URL` if the organisation isn't on `https://sentry.io`. |
| `OPS_HEALTHCHECKS_API_KEY` | none | The Healthchecks.io project's **read-only** API key (Project Settings, API Access). |
| `OPS_GOATCOUNTER_CODE`, `OPS_GOATCOUNTER_TOKEN` | none | A GoatCounter site's code (the `<code>` of `<code>.goatcounter.com`) and an API token allowed to read statistics. With the code only, the page links to GoatCounter. Both sites count into the site `well` (see [Visitor counts](../../../frontend/README.md#visitor-counts-goatcounter)). |
| `REQUEST_METRICS` | on | In `dashboard/backend/app/.env`: `0` stops the backend counting requests (recreate `backend`). |
