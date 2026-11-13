# The WordPress site (well.mcmaster.ca)

The WELL home page. It runs as the `wordpress` service in `docker-compose.yml`, with its data in MySQL 5.7 (the `db`
container, `db_data` volume). This README sits here rather than in `home/` because `home/` is the web root: any file
in it can be fetched from the site.

## What is where

- **`home/`** is WordPress itself: core, plugins and the theme, tracked in git and bind-mounted into the container as
  `/var/www/html`. Only PHP and Apache come from the `wordpress` image, so its tag in `docker-compose.yml` is bumped
  for PHP/Apache fixes, and WordPress core and plugins are updated in `home/` (through WordPress itself; Dependabot
  doesn't cover them).
- **The theme** is `home/wp-content/themes/well`, a custom PHP template:
  - **Bootstrap** grid and utility classes for responsive layout;
  - a **Flickity** banner carousel with adaptive height;
  - responsive images via `srcset`/`sizes` (pre-sized WebP copies in `img/media/`, made by
    `wordpress/theme-images.mjs`), and alt text throughout;
  - a dedicated Dashboard page (`page-dashboard.php`) that embeds the dashboard in an iframe, from `DASHBOARD_URL`.
  How to add, edit and delete news posts is in [the theme's README](../home/wp-content/themes/well/README.md).
- **This folder** holds the Apache and PHP settings mounted into the container one file at a time
  (`apache-hardening.conf`, `zz-performance.conf`, `remoteip.conf`, `php-hardening.ini`; each file's comments explain
  its rules);
  `theme-images.mjs` (run from the repository root after changing a photo:
  `npm install --no-save sharp && node wordpress/theme-images.mjs`, then commit the files it writes); and `backup.sh`,
  the nightly backup of the database and uploads ([Backups](#backups)).
- **Hardening** (details in [Hardening](#hardening) below): Apache rules and security headers in
  `apache-hardening.conf`, the must-use plugin `home/wp-content/mu-plugins/well-hardening.php`, and
  `DISALLOW_FILE_EDIT` through `WORDPRESS_CONFIG_EXTRA` in `docker-compose.yml`.

## Hardening

- **Apache** (`apache-hardening.conf`) refuses `xmlrpc.php`, `wp-comments-post.php`, `wp-trackback.php`,
  `readme.html`, `license.txt`, `wp-config-sample.php`, and plugins' and themes' readmes, changelogs and package
  files (they name versions). It never runs PHP from `wp-content/uploads`, and ignores `.htaccess` files there, so an
  uploaded one can't allow PHP again.
- **Client addresses.** `remoteip.conf` replaces the image's own, which made Apache believe `X-Forwarded-For` from any
  private or loopback address. Apache's logs therefore show the campus proxy (130.113.68.30) as the client of every
  visitor. Only the failed-login limit reads the forwarded address, and only from `WELL_TRUSTED_PROXY_IPS`.
- **Security headers**, from the same file: `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: SAMEORIGIN`, and:
  - `Strict-Transport-Security: max-age=86400` (one day), kept short at first so a mistake can't strand visitors for
    long. Once the site has worked over HTTPS for a few weeks, raise it to `max-age=31536000`.
  - A `Content-Security-Policy-Report-Only` header listing what the theme loads. Browsers enforce nothing yet; they
    log what the policy would block in the developer console. When the site's pages show no such messages, rename the
    header to `Content-Security-Policy` to enforce it, and add any new outside host (a new script, font or embed)
    to it first.
- **The must-use plugin** (`home/wp-content/mu-plugins/well-hardening.php`; deleting the file undoes it):
  - keeps account names from anonymous visitors: 401 for the REST API's `/wp-json/wp/v2/users`; `/?author=N` and
    author archives redirect to the home page; no author fields in oEmbed answers; no users in the core sitemap; and
    bylines and feeds say "WELL team" while an account's display name is its login name (set a different display
    name in Users > Profile to show it instead);
  - limits failed logins: every attempt is counted before its password is checked, in one database statement, so
    parallel requests can't slip past. After 5 from one client address with less than 15 minutes between them, that
    address is refused until 15 minutes after its last counted attempt. Refused attempts and opening the login page
    don't count, and a successful login clears the count. IPv6 clients are counted per /64. The client address
    comes from the proxy's `X-Forwarded-For` only when the connection comes from a proxy in
    `WELL_TRUSTED_PROXY_IPS` (`docker-compose.yml`; haproxy by default). The counts are `well_login_fail_*` rows in
    the options table; old ones are deleted now and then;
  - closes comments and pingbacks everywhere, turns off XML-RPC logins and pingbacks, and removes the links
    advertising them and the WordPress version (`<meta name="generator">`).
- **The login page.** The campus proxy blocks `/wp-admin/` from outside McMaster's network, but not
  `/wp-login.php`, so the login form (and its "lost password" page, which says whether a user name exists) is open
  to the internet, with only the limit above. Ask McMaster IT, who run `haproxy.cas.mcmaster.ca`, to restrict
  `/wp-login.php` the same way as `/wp-admin/`.
- **`DISALLOW_FILE_EDIT`** (`WORDPRESS_CONFIG_EXTRA` in `docker-compose.yml`) turns off the theme and plugin editors
  in wp-admin. `DISALLOW_FILE_MODS` is deliberately not set, so plugins and core can still be updated from wp-admin
  (which also means an administrator can upload a plugin, if Apache can write to `home/`).
- **Jetpack** isn't connected to WordPress.com, so blocking `xmlrpc.php` breaks nothing. If it is ever connected and
  reports a connection problem, remove the `xmlrpc.php` block from `apache-hardening.conf` and recreate the container.

A change to `apache-hardening.conf` needs the container recreated (`docker compose up -d --no-deps wordpress`); one
to the plugin is live once pulled.

## Settings

In the root `.env` ([docs/configuration.md](../docs/configuration.md#root-env-docker-compose)): `MYSQL_ROOT_PASSWORD`,
`WORDPRESS_DB_PASSWORD`, `DEPLOYMENT` (`PROD` makes the theme force HTTPS URLs), `WP_HOME`, `WP_SITEURL` and
`DASHBOARD_URL`.

## Deploying

A change under `home/` is live once it is pulled, with no restart. A change to a `wordpress/*.conf` or `*.ini` file
needs the container recreated, since Apache and PHP read them only at start; `deploy.sh` does that, and CI checks the
files with Apache's config test and PHP in the image compose runs. A WordPress core update also needs its database
update run from wp-admin, so `deploy.sh --auto` holds it for a person ([docs/deploying.md](../docs/deploying.md)).

## Backups

The MySQL volume (`db_data`) is the only copy of the site's posts, pages and settings, and `home/wp-content/uploads`
is the only copy of its media library. `wordpress/backup.sh` backs up both. It runs from cron on the VM, not in a
container.

- **What**: a `mysqldump --single-transaction` of the WordPress database, run inside the `db` container (a consistent
  snapshot that doesn't lock the site) and gzipped, plus a tar.gz of `home/wp-content/uploads`. The dump runs as
  MySQL's root user with the password the container already has: `MYSQL_ROOT_PASSWORD` is read inside the container
  and handed to mysqldump in `MYSQL_PWD`, so the password is never on a command line, in the log or in the crontab.
- **Where**: `~/WELLWebsite/wp-backups/` (gitignored; set `WP_BACKUP_DIR` to change it), as
  `wordpress-db-YYYYmmdd-HHMM.sql.gz` and `wordpress-uploads-YYYYmmdd-HHMM.tar.gz`, both with the same Toronto-time
  stamp. The folder is 0700 and the files are 0600, owned by the user whose crontab runs the script, because the dump
  holds password hashes and unpublished posts. The umask is set only in the subshells that write these files, never
  for the whole shell or for git, so it can't leave files in `home/` that Apache can't read.
- **Readable uploads**: the archive is made as the cron user, so every file under `home/wp-content/uploads` must stay
  readable by that user. They are today (owned by the checkout's user, folders 755 and files 644). If WordPress is
  ever given its own uploads folder (owned by `www-data`), keep its files world-readable (WordPress's default, 644);
  one the cron user can't read fails the run with tar's "Permission denied".
- **Checked**: each file is written as a hidden `.partial` file and renamed only once it passes its check. The dump
  must decompress, end with mysqldump's `-- Dump completed` line (a dump cut short has none) and create the options
  table; the archive must list back. The dump is checked and kept first, so if the uploads archive then fails, the
  run fails (exit 1, a `/fail` ping naming the uploads) but the night's database dump is still there, without its
  archive; `--restore-check` on that backup checks the dump and says the archive is missing. A failed step leaves
  nothing that looks like a good file, and the next run deletes whatever a killed run left behind. Only one run goes at a time (`.backup.lock`; a second run waits up to 15 minutes). A run
  refuses to start if a backup the size of the last one would leave less than `WP_BACKUP_MIN_FREE_MB` (default
  2048) free.
- **Retention**, applied only after a good backup: it keeps the newest backup of each of the last 7 days
  (`WP_BACKUP_KEEP_DAILY`), 8 ISO weeks (`WP_BACKUP_KEEP_WEEKLY`) and 12 months (`WP_BACKUP_KEEP_MONTHLY`), so at
  most 27 backups. Both files of a backup are deleted together. Only files with exactly those names are ever deleted,
  so a copy saved under another name, such as `wordpress-db-before-update.sql.gz`, is kept.
- **Monitoring**: when `HEALTHCHECK_URL_WP_BACKUP` is set (a Healthchecks.io ping URL), the script pings `<url>/start`
  when it begins, `<url>` with a one-line summary when it succeeds, and `<url>/fail` with the reason when it fails.
  Set the check's period to 1 day.

**Setting it up** (once, on the VM): add this line to the crontab of the user that owns `~/WELLWebsite`
(`crontab -e`). It runs at 03:45, after the PostgreSQL backup at 03:15, and appends to `wp-backup.log` (gitignored):

```
45 3 * * * cd ~/WELLWebsite && HEALTHCHECK_URL_WP_BACKUP=https://hc-ping.com/<uuid> ./wordpress/backup.sh >>wp-backup.log 2>&1
```

Then run it once by hand (`./wordpress/backup.sh`) and check that both files appear in `wp-backups/`. `--no-prune`
backs up without deleting anything (for example, before a WordPress core update). `--prune-only` only applies
retention.

**Restore check** (optional; once a month is enough): `./wordpress/backup.sh --restore-check` loads the newest dump
(or the one named with `--restore-check YYYYmmdd-HHMM`) into a throwaway container running the same MySQL image, with
no network. It checks that every table came back and that the options table has a `siteurl`, lists the uploads
archive, and then deletes the container. It changes nothing else and pings nothing.

**Restoring for real.** First take a backup of the current state, even if it is broken
(`./wordpress/backup.sh --no-prune`). Then:

```bash
cd ~/WELLWebsite
STAMP=YYYYmmdd-HHMM                     # the backup to restore
docker compose stop wordpress           # nothing writes while the database is replaced
# The database: empty the wordpress database, then load the dump into it, as root inside the db container
docker compose exec -T db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "DROP DATABASE IF EXISTS \`$MYSQL_DATABASE\`; CREATE DATABASE \`$MYSQL_DATABASE\` DEFAULT CHARACTER SET utf8mb4"'
gunzip -c "wp-backups/wordpress-db-$STAMP.sql.gz" | docker compose exec -T db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --default-character-set=utf8mb4 "$MYSQL_DATABASE"'
# The uploads: note who owns the current folder, move it aside, unpack the archive in its place (-p keeps the
# archived modes), then give the restored folder the same owner, through the wordpress container (which runs as root)
OWNER=$(stat -c %u:%g home/wp-content/uploads)
mv home/wp-content/uploads home/wp-content/uploads.before-restore
tar -p -C home/wp-content -xzf "wp-backups/wordpress-uploads-$STAMP.tar.gz"
docker compose run --rm --no-deps --entrypoint chown wordpress -R "$OWNER" /var/www/html/wp-content/uploads
docker compose start wordpress
```

The `wordpress` MySQL user keeps its access, because MySQL keeps database grants when a database is dropped. `tar`
run as you makes you the owner of every restored file, so the `chown` puts back whoever owned the folder before:
on the VM that is the checkout's user (the same user, so nothing changes), and on an install where WordPress
writes its own uploads it is `www-data` (uid 33), which Apache needs in order to save new media. Check the site and
wp-admin, including uploading an image, then delete the old folder. Do this through the container too, since files
WordPress wrote belong to `www-data` and you can't delete them as yourself:
`docker compose run --rm --no-deps --entrypoint rm wordpress -rf /var/www/html/wp-content/uploads.before-restore`.

If the `db_data` volume itself is lost, `docker compose up -d db` creates an empty volume with the `wordpress`
database and user from `.env`; restore into it the same way.

These backups are on the VM's own disk. They protect against mistakes (a bad plugin or core update, deleted posts),
not against losing the VM. To keep a copy off the VM, copy one to private storage, for example
`scp <vm>:WELLWebsite/wp-backups/wordpress-db-<stamp>.sql.gz .`. Never put one anywhere public: the dump holds
password hashes.

## Visitor counts

`well_goatcounter_script()` in the theme's `functions.php` counts page views with GoatCounter on well.mcmaster.ca,
except for logged-in users and previews. It sets no cookies; what is counted, and how to turn it off, is in
[Visitor counts](../dashboard/frontend/README.md#visitor-counts-goatcounter).
