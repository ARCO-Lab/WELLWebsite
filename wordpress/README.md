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
  (`apache-hardening.conf`, `zz-performance.conf`, `php-hardening.ini`; each file's comments explain its rules), and
  `theme-images.mjs` (run from the repository root after changing a photo:
  `npm install --no-save sharp && node wordpress/theme-images.mjs`, then commit the files it writes).

## Settings

In the root `.env` ([docs/configuration.md](../docs/configuration.md#root-env-docker-compose)): `MYSQL_ROOT_PASSWORD`,
`WORDPRESS_DB_PASSWORD`, `DEPLOYMENT` (`PROD` makes the theme force HTTPS URLs), `WP_HOME`, `WP_SITEURL` and
`DASHBOARD_URL`.

## Deploying

A change under `home/` is live once it is pulled, with no restart. A change to a `wordpress/*.conf` or `*.ini` file
needs the container recreated, since Apache and PHP read them only at start; `deploy.sh` does that, and CI checks the
files with Apache's config test and PHP in the image compose runs. A WordPress core update also needs its database
update run from wp-admin, so `deploy.sh --auto` holds it for a person ([docs/deploying.md](../docs/deploying.md)).

## Visitor counts

`well_goatcounter_script()` in the theme's `functions.php` counts page views with GoatCounter on well.mcmaster.ca,
except for logged-in users and previews. It sets no cookies; what is counted, and how to turn it off, is in
[Visitor counts](../dashboard/frontend/README.md#visitor-counts-goatcounter).
