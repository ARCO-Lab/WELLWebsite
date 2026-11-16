"""welldash²'s settings, all from the environment. Missing or malformed secrets stop the service from starting.

Required:
  OPS_PASSWORD_HASH    werkzeug hash of the one shared password (python -m ops.hashpw prints it)
  OPS_SECRET_KEY       random string, at least 32 characters, that signs the session cookie
  OPS_BIND             the address docker-compose.yml publishes the port on (127.0.0.1 for an SSH tunnel, or the
                       VM's campus address). Unset or every address (0.0.0.0, ::) stops the service from starting,
                       unless OPS_ALLOW_ANY_ADDRESS=1 says that is meant.
Optional:
  OPS_DATABASE_URL     database to read (default DATABASE_URL); ideally a read-only role, see README.md here
  OPS_COOKIE_SECURE    1 to mark the session cookie Secure on every response. Unset, it is Secure whenever the
                       request came over HTTPS, and left off over plain HTTP (an SSH tunnel), where browsers drop it
  OPS_RETENTION_DAYS   days of request_metrics and uptime_probes to keep (default 90)
  OPS_PROBE_INTERVAL_S seconds between uptime checks (default 60; 0 turns the checks off)
  OPS_PROBE_DASHBOARD_URL, OPS_PROBE_API_URL, OPS_PROBE_WORDPRESS_URL, OPS_PROBE_WORDPRESS_HOST
                       what the uptime checks request (ops/probe.py; an empty URL turns that check off)
  OPS_LOGS_DIR         read-only folder of log files whose sizes are shown (default /ops/logs)
  OPS_GITHUB_REPO, OPS_GITHUB_TOKEN          CI status of main (the token is optional: public repo)
  SENTRY_API_TOKEN, SENTRY_ORG, SENTRY_API_URL   recent Sentry issues (read-only token; skipped when unset);
                                                 docker-compose.yml fills them from OPS_SENTRY_* in .env
  HEALTHCHECKS_API_KEY, HEALTHCHECKS_API_URL     Healthchecks.io check states (read-only key; skipped when unset);
                                                 from OPS_HEALTHCHECKS_API_KEY in .env
  OPS_GOATCOUNTER_CODE, OPS_GOATCOUNTER_TOKEN    visitor statistics from GoatCounter (skipped when unset)
"""
import hashlib
import ipaddress
import os
import re
from dataclasses import dataclass
from datetime import timedelta

SESSION_LIFETIME = timedelta(hours=8)
MIN_SECRET_KEY_LENGTH = 32
# werkzeug's generate_password_hash format: "<method>$<salt>$<hash>", method scrypt:... or pbkdf2:...
HASH_FORMAT = re.compile(r"^(scrypt|pbkdf2)(:[A-Za-z0-9:]+)?\$[^$\s]+\$[0-9a-f]+$")


class ConfigError(Exception):
    pass


def flag(value, default=False):
    # An on/off setting: 1/true/yes/on (any case) is on; unset or empty gives the default.
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def whole_number(env, name, default):
    # A whole-number setting; anything that isn't digits stops the app (ConfigError) rather than being guessed.
    raw = (env.get(name) or "").strip()
    if not raw:
        return default
    if not raw.isdigit():
        raise ConfigError(f"{name} must be a whole number, got {raw!r}")
    return int(raw)


@dataclass(frozen=True)
class Settings:
    password_hash: str
    secret_key: str
    database_url: str
    bind: str = "127.0.0.1"
    cookie_secure: bool = False
    retention_days: int = 90
    probe_interval_s: int = 60
    probe_dashboard_url: str = "http://dashboard:8081/"
    probe_api_url: str = "http://backend:5000/api/latest"
    # On the wp_probe network (docker-compose.yml), which only WordPress and welldash² join
    probe_wordpress_url: str = "http://wordpress/"
    probe_wordpress_host: str = "well.mcmaster.ca"
    logs_dir: str = "/ops/logs"
    github_repo: str = "ARCO-Lab/WELLWebsite"
    github_token: str = ""
    sentry_token: str = ""
    sentry_org: str = ""
    sentry_api_url: str = "https://sentry.io"
    healthchecks_key: str = ""
    healthchecks_api_url: str = "https://healthchecks.io"
    goatcounter_code: str = ""
    goatcounter_token: str = ""

    @property
    def password_version(self):
        """A short fingerprint of the password hash, kept in each session, so changing the password signs
        everyone out. Not secret-bearing: a hash of a salted hash."""
        return hashlib.sha256(self.password_hash.encode()).hexdigest()[:16]


def bind_address(env):
    """OPS_BIND, which docker-compose.yml publishes the port on and also passes in here, so that a missing or
    every-address value stops the service: ports Docker publishes bypass the VM's own firewall, so 0.0.0.0 would offer
    the login page on every address the VM has. OPS_ALLOW_ANY_ADDRESS=1 accepts 0.0.0.0 or :: on purpose."""
    raw = (env.get("OPS_BIND") or "").strip()
    if not raw:
        raise ConfigError("OPS_BIND is not set. Set it in .env to 127.0.0.1 (and reach welldash² through an SSH "
                          "tunnel) or to the VM's campus address (see dashboard/backend/app/ops/README.md).")
    try:
        address = ipaddress.ip_address(raw.strip("[]"))
    except ValueError:
        raise ConfigError(f"OPS_BIND must be an IP address, such as 127.0.0.1, got {raw!r}") from None
    if address.is_unspecified and not flag(env.get("OPS_ALLOW_ANY_ADDRESS")):
        raise ConfigError(f"OPS_BIND={raw} publishes welldash² on every address the VM has. Set it to 127.0.0.1 "
                          "or the VM's campus address, or set OPS_ALLOW_ANY_ADDRESS=1 if that is really meant.")
    return raw


def load_settings(env=None):
    """Settings from the environment. ConfigError (saying what to fix, never echoing a secret) if the password
    hash, the secret key or OPS_BIND is missing or malformed, or another setting is malformed."""
    env = os.environ if env is None else env
    password_hash = (env.get("OPS_PASSWORD_HASH") or "").strip().strip("'\"")
    if not password_hash:
        raise ConfigError("OPS_PASSWORD_HASH is not set. Run `python -m ops.hashpw` to make one and put it in the "
                          "env file (see dashboard/backend/app/ops/README.md). Refusing to start without a password.")
    if not HASH_FORMAT.match(password_hash):
        raise ConfigError("OPS_PASSWORD_HASH doesn't look like a hash from `python -m ops.hashpw` (method$salt$hash). "
                          "If it was written without single quotes, Docker Compose may have read the $ signs as "
                          "variables: put the whole value in single quotes.")
    secret_key = env.get("OPS_SECRET_KEY") or ""
    if len(secret_key.strip()) < MIN_SECRET_KEY_LENGTH:
        raise ConfigError(f"OPS_SECRET_KEY is not set or shorter than {MIN_SECRET_KEY_LENGTH} characters. "
                          "`python -m ops.hashpw` prints a random one. Refusing to start without it.")
    database_url = (env.get("OPS_DATABASE_URL") or env.get("DATABASE_URL") or "").strip()
    if not database_url:
        raise ConfigError("Set OPS_DATABASE_URL (or DATABASE_URL) to the database to read.")
    defaults = Settings("", "", "")
    text = lambda name, default: (env.get(name) or "").strip() or default   # noqa: E731
    return Settings(
        password_hash=password_hash,
        secret_key=secret_key.strip(),
        database_url=database_url,
        bind=bind_address(env),
        cookie_secure=flag(env.get("OPS_COOKIE_SECURE")),
        retention_days=max(1, whole_number(env, "OPS_RETENTION_DAYS", defaults.retention_days)),
        probe_interval_s=whole_number(env, "OPS_PROBE_INTERVAL_S", defaults.probe_interval_s),
        # Set but empty turns that check off.
        probe_dashboard_url=env.get("OPS_PROBE_DASHBOARD_URL", defaults.probe_dashboard_url).strip(),
        probe_api_url=env.get("OPS_PROBE_API_URL", defaults.probe_api_url).strip(),
        probe_wordpress_url=env.get("OPS_PROBE_WORDPRESS_URL", defaults.probe_wordpress_url).strip(),
        probe_wordpress_host=text("OPS_PROBE_WORDPRESS_HOST", defaults.probe_wordpress_host),
        logs_dir=text("OPS_LOGS_DIR", defaults.logs_dir),
        github_repo=text("OPS_GITHUB_REPO", defaults.github_repo),
        github_token=text("OPS_GITHUB_TOKEN", ""),
        sentry_token=text("SENTRY_API_TOKEN", ""),
        sentry_org=text("SENTRY_ORG", ""),
        sentry_api_url=text("SENTRY_API_URL", defaults.sentry_api_url).rstrip("/"),
        healthchecks_key=text("HEALTHCHECKS_API_KEY", ""),
        healthchecks_api_url=text("HEALTHCHECKS_API_URL", defaults.healthchecks_api_url).rstrip("/"),
        goatcounter_code=text("OPS_GOATCOUNTER_CODE", ""),
        goatcounter_token=text("OPS_GOATCOUNTER_TOKEN", ""),
    )
