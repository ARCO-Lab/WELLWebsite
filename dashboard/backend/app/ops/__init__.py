"""welldash²: a small, read-only, password-protected operations dashboard, reachable on McMaster's network only.

It runs as the `ops` service in docker-compose.yml (gunicorn "ops.app:create_app()"), from the backend image, and
shows the site's uptime, the API's traffic, data freshness, open alerts, vendor and CI status. The README's
"welldash² (operations dashboard)" section explains how to set it up.
"""
