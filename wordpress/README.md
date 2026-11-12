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
  (`apache-hardening.conf`, `zz-performance.conf`, `php-hardening.ini`; each file's comments explain its rules);
  `theme-images.mjs` (run from the repository root after changing a photo:
  `npm install --no-save sharp && node wordpress/theme-images.mjs`, then commit the files it writes); and `backup.sh`,
  the nightly backup of the database and uploads ([Backups](#backups)).

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
- **Checked**: both files are written as hidden `.partial` files. They are renamed only once the dump decompresses,
  ends with mysqldump's `-- Dump completed` line (a dump cut short has none) and creates the options table, and the
  archive lists back. A failed run leaves nothing that looks like a backup, and the next run deletes whatever a
  killed run left behind. Only one run goes at a time (`.backup.lock`; a second run waits up to 15 minutes). A run
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
# The uploads: move the current folder aside, then unpack the archive in its place
mv home/wp-content/uploads home/wp-content/uploads.before-restore
tar -C home/wp-content -xzf "wp-backups/wordpress-uploads-$STAMP.tar.gz"
docker compose start wordpress
```

The `wordpress` MySQL user keeps its access, because MySQL keeps database grants when a database is dropped. Check
the site and wp-admin, then delete `home/wp-content/uploads.before-restore`. If the `db_data` volume itself is lost,
`docker compose up -d db` creates an empty volume with the `wordpress` database and user from `.env`; restore into it
the same way.

These backups are on the VM's own disk. They protect against mistakes (a bad plugin or core update, deleted posts),
not against losing the VM. To keep a copy off the VM, copy one to private storage, for example
`scp <vm>:WELLWebsite/wp-backups/wordpress-db-<stamp>.sql.gz .`. Never put one anywhere public: the dump holds
password hashes.

## Visitor counts

`well_goatcounter_script()` in the theme's `functions.php` counts page views with GoatCounter on well.mcmaster.ca,
except for logged-in users and previews. It sets no cookies; what is counted, and how to turn it off, is in
[Visitor counts](../dashboard/frontend/README.md#visitor-counts-goatcounter).
