#!/usr/bin/env bash
# Checks WordPress's hardening against a throwaway install: the compose image with a copy of home/ and the
# wordpress/*.conf and *.ini files mounted as docker-compose.yml mounts them, and the compose WORDPRESS_CONFIG_EXTRA,
# on a fresh MySQL 5.7. What it checks: wordpress/apache-hardening.conf (refused files, PHP under uploads even with a
# hostile .htaccess, security headers) and mu-plugins/well-hardening.php (account names, failed-login limit,
# comments, XML-RPC, version). Everything runs on a Docker network of its own and is removed at the end.
#   bash .github/scripts/test_wordpress_hardening.sh     (from the repository root; needs docker and python3)
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT" || exit 1
T=$(mktemp -d)
NET=wphard-net DB=wphard-db WP=wphard-wp
cleanup() {
    docker rm -f -v "$WP" "$DB" >/dev/null 2>&1
    docker network rm "$NET" >/dev/null 2>&1
    # Files the containers wrote (wp-config.php, the planted uploads) belong to root or www-data
    docker run --rm -v "$T:/t" alpine:3 rm -rf /t/home >/dev/null 2>&1
    rm -rf "$T"
}
trap cleanup EXIT

compose_json=$(docker compose config --format json) || exit 1
service() { python3 -c "import json, sys; print(json.load(sys.stdin)['services']['wordpress']$1)" <<<"$compose_json"; }
IMAGE=$(service "['image']")
CONFIG_EXTRA=$(service "['environment']['WORDPRESS_CONFIG_EXTRA']")

fails=0
check() {   # check <description> <command...>: passes when the command succeeds
    local what=$1; shift
    if "$@"; then echo "ok   $what"; else echo "FAIL $what"; fails=$((fails + 1)); fi
}
# GET (or other curl arguments) from inside the WordPress container, so the peer is 127.0.0.1
wpcurl() { docker exec "$WP" curl -s -H 'Host: localhost' "$@"; }
status() { wpcurl -o /dev/null -w '%{http_code}' "$@"; }
is() { [ "$1" = "$2" ] || { echo "     got '$1', expected '$2'"; return 1; }; }
has() { grep -qi -- "$2" <<<"$1" || { echo "     no '$2' in: ${1:0:300}"; return 1; }; }
lacks() { ! grep -qi -- "$2" <<<"$1" || { echo "     unexpected '$2' in: $(grep -io -- ".\{0,60\}$2.\{0,60\}" <<<"$1" | head -1)"; return 1; }; }
wpphp() { docker exec -i "$WP" php; }   # a PHP script on stdin, run inside the container

echo "== Starting MySQL and $IMAGE"
cp -a home "$T/home"
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MYSQL_ROOT_PASSWORD=ci -e MYSQL_DATABASE=wordpress \
    -e MYSQL_USER=wordpress -e MYSQL_PASSWORD=ci mysql:5.7 >/dev/null || exit 1
mounts=(-v "$T/home:/var/www/html")
for f in wordpress/*.conf; do mounts+=(-v "$PWD/$f:/etc/apache2/conf-enabled/$(basename "$f"):ro"); done
for f in wordpress/*.ini; do mounts+=(-v "$PWD/$f:/usr/local/etc/php/conf.d/zz-$(basename "$f"):ro"); done
for _ in $(seq 90); do docker exec "$DB" mysqladmin -uwordpress -pci ping >/dev/null 2>&1 && break; sleep 2; done
sleep 3
# 127.0.0.1 stands in for haproxy: requests made from inside the container may name a client in X-Forwarded-For
docker run -d --name "$WP" --network "$NET" "${mounts[@]}" -e WORDPRESS_DB_HOST="$DB:3306" \
    -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=ci -e WORDPRESS_DB_NAME=wordpress \
    -e WORDPRESS_CONFIG_EXTRA="$CONFIG_EXTRA" -e WELL_TRUSTED_PROXY_IPS=127.0.0.1 "$IMAGE" >/dev/null || exit 1
for _ in $(seq 60); do [ "$(status http://localhost/wp-admin/install.php)" = 200 ] && break; sleep 2; done

echo "== Installing WordPress, with the well theme and /%postname%/ permalinks"
PW=ci-only-password-1   # a throwaway account in a throwaway database
check "install" is "$(status -X POST 'http://localhost/wp-admin/install.php?step=2' --data-urlencode weblog_title=t \
    --data-urlencode user_name=ciadmin --data-urlencode "admin_password=$PW" --data-urlencode "admin_password2=$PW" \
    --data-urlencode pw_weak=1 --data-urlencode admin_email=ci@example.com --data-urlencode blog_public=1)" 200
wpphp <<'EOF'
<?php
$_SERVER['HTTP_HOST'] = 'localhost';
require '/var/www/html/wp-load.php';
switch_theme('well');
update_option('permalink_structure', '/%postname%/');
flush_rewrite_rules(false);
echo "theme ", get_stylesheet(), "\n";
EOF
# The container's address on its network, for requests that must not come from 127.0.0.1
WP_IP=$(docker exec "$WP" hostname -i | awk '{print $1}')
echo "container address: ${WP_IP:-none}"

echo "== Apache: refused files"
for p in /xmlrpc.php /wp-comments-post.php /wp-trackback.php /readme.html /license.txt /wp-config-sample.php \
         /wp-content/plugins/akismet/readme.txt /wp-content/plugins/jetpack/CHANGELOG.md \
         /wp-content/plugins/jetpack/composer.json /wp-content/themes/well/README.md; do
    check "$p is refused" is "$(status "http://localhost$p")" 403
done
for p in / /hello-world/ /wp-content/themes/well/style.css; do
    check "$p still answers 200" is "$(status "http://localhost$p")" 200
done
check "a comment POST is refused" is "$(status -X POST http://localhost/wp-comments-post.php \
    --data 'comment_post_ID=1&comment=spam&author=a&email=a@example.com')" 403

echo "== Apache: no PHP from uploads, even with an uploaded .htaccess that allows it"
docker exec "$WP" sh -c 'mkdir -p /var/www/html/wp-content/uploads/evil && cd /var/www/html/wp-content/uploads/evil &&
    printf "<FilesMatch \"\\\\.(php|jpg)\$\">\n  Require all granted\n</FilesMatch>\nAddHandler application/x-httpd-php .jpg\n" > .htaccess &&
    echo "<?php echo \"PW\" . \"NED\";" > shell.php && cp shell.php shell.jpg'
for p in shell.php shell.php/x.jpg SHELL.Php; do
    check "uploads/evil/$p is refused" is "$(status "http://localhost/wp-content/uploads/evil/$p")" 403
done
check "uploads/evil/shell.jpg is not run" lacks "$(wpcurl http://localhost/wp-content/uploads/evil/shell.jpg)" PWNED

echo "== Security headers"
home_headers=$(wpcurl -D - -o /dev/null http://localhost/)
for h in 'Strict-Transport-Security: max-age=86400' 'X-Content-Type-Options: nosniff' \
         'Referrer-Policy: strict-origin-when-cross-origin' 'X-Frame-Options: SAMEORIGIN' \
         "Content-Security-Policy-Report-Only: default-src 'self'"; do
    check "home page sends $h" has "$home_headers" "$h"
done
login_headers=$(wpcurl -D - -o /dev/null http://localhost/wp-login.php)
check "wp-login.php sends X-Frame-Options once (Apache replaces WordPress's own)" \
    is "$(grep -ci '^X-Frame-Options' <<<"$login_headers")" 1
rest_headers=$(wpcurl -D - -o /dev/null http://localhost/wp-json/)
check "the REST API sends nosniff once" is "$(grep -ci '^X-Content-Type-Options' <<<"$rest_headers")" 1

echo "== Account names"
for p in /wp-json/wp/v2/users '/?rest_route=/wp/v2/users' /wp-json/wp/v2/users/1; do
    check "$p is 401 for visitors" is "$(status "http://localhost$p")" 401
done
for p in '/?author=1' /author/ciadmin/; do
    check "$p redirects home" is "$(wpcurl -o /dev/null -w '%{http_code} %{redirect_url}' "http://localhost$p")" \
        "302 http://localhost/"
done
check "oEmbed has no author" lacks "$(wpcurl 'http://localhost/wp-json/oembed/1.0/embed?url=http%3A%2F%2Flocalhost%2Fhello-world%2F')" author_
check "the sitemap index has no users" lacks "$(wpcurl http://localhost/wp-sitemap.xml)" users
check "the users sitemap is gone" is "$(status http://localhost/wp-sitemap-users-1.xml)" 404
feed=$(wpcurl http://localhost/feed/)
check "the feed's creator is WELL team" has "$feed" '<dc:creator><!\[CDATA\[WELL team\]\]></dc:creator>'
check "the feed doesn't name the login" lacks "$feed" ciadmin
post=$(wpcurl http://localhost/hello-world/)
check "the post's byline is WELL team" has "$post" 'By WELL team'
check "the post page doesn't name the login" lacks "$post" ciadmin

echo "== Version and XML-RPC links"
check "no generator meta" lacks "$post" 'name="generator"'
check "no generator in the feed" lacks "$feed" 'wordpress.org/?v='
check "no RSD link" lacks "$post" EditURI
check "no X-Pingback header" lacks "$(wpcurl -D - -o /dev/null http://localhost/hello-world/)" X-Pingback

echo "== Inside WordPress"
inside=$(wpphp <<'EOF'
<?php
$_SERVER['HTTP_HOST'] = 'localhost';
require '/var/www/html/wp-load.php';
require_once ABSPATH . WPINC . '/class-IXR.php';
require_once ABSPATH . WPINC . '/class-wp-xmlrpc-server.php';
$x = new wp_xmlrpc_server();
$admin = get_user_by('login', 'ciadmin');
wp_set_current_user($admin->ID);
$users = rest_do_request(new WP_REST_Request('GET', '/wp/v2/users'));
$facts = [
    'DISALLOW_FILE_EDIT' => defined('DISALLOW_FILE_EDIT') && DISALLOW_FILE_EDIT,
    'no DISALLOW_FILE_MODS' => !defined('DISALLOW_FILE_MODS'),
    'admin cannot edit plugins' => !current_user_can('edit_plugins'),
    'admin can update plugins' => current_user_can('update_plugins'),
    'logged-in user list works' => $users->get_status() === 200,
    'xmlrpc_enabled is false' => apply_filters('xmlrpc_enabled', true) === false,
    'no pingback.ping' => !isset($x->methods['pingback.ping']),
    'other XML-RPC methods stay' => isset($x->methods['wp.getUsersBlogs']),
    'comments closed on the post' => !comments_open(1) && !pings_open(1),
    'posts have no comment support' => !post_type_supports('post', 'comments'),
];
foreach ($facts as $what => $ok) { echo ($ok ? 'ok' : 'FAIL'), " $what\n"; }
EOF
)
echo "$inside" | sed 's/^ok /ok   /; s/^FAIL /FAIL /'
fails=$((fails + $(grep -c '^FAIL' <<<"$inside")))
check "the PHP checks ran" has "$inside" "^ok DISALLOW_FILE_EDIT"

echo "== Failed-login limit"
# login <password> [curl arguments]: the HTTP status, and "in" if the login cookie was set. Posts to $LOGIN_HOST,
# localhost by default (so the peer is 127.0.0.1).
login() {
    wpcurl -o /dev/null -D - -b 'wordpress_test_cookie=WP%20Cookie%20check' -X POST "${@:2}" \
        "http://${LOGIN_HOST:-localhost}/wp-login.php" \
        --data-urlencode log=ciadmin --data-urlencode "pwd=$1" --data-urlencode testcookie=1 \
        | awk 'NR == 1 {s = $2} /^[Ss]et-[Cc]ookie: wordpress_logged_in_/ {c = " in"} END {print s c}'
}
for _ in 1 2 3 4 5; do login wrong -H 'X-Forwarded-For: 203.0.113.7' >/dev/null; done
check "after 5 failures, that client's right password is refused" \
    is "$(login "$PW" -H 'X-Forwarded-For: 203.0.113.7')" 200
check "and the page says why" has "$(wpcurl -b 'wordpress_test_cookie=WP%20Cookie%20check' -X POST \
    http://localhost/wp-login.php -H 'X-Forwarded-For: 203.0.113.7' --data-urlencode log=ciadmin \
    --data-urlencode "pwd=$PW" --data-urlencode testcookie=1)" 'Too many failed login attempts'
check "another client still logs in" is "$(login "$PW" -H 'X-Forwarded-For: 203.0.113.8')" "302 in"
# Posted to the container's network address, the peer is that address, not a trusted proxy, so X-Forwarded-For is
# ignored: five failures under five made-up addresses still lock out the one real peer. (curl always sends localhost
# to loopback, whatever --resolve says, hence the address in the URL.)
check "the container's address is known" is "$([ -n "$WP_IP" ] && [ "$WP_IP" != 127.0.0.1 ] && echo yes)" yes
for i in 1 2 3 4 5; do LOGIN_HOST=$WP_IP login wrong -H "X-Forwarded-For: 198.51.100.$i" >/dev/null; done
check "an untrusted peer can't dodge the limit with X-Forwarded-For" \
    is "$(LOGIN_HOST=$WP_IP login "$PW" -H 'X-Forwarded-For: 198.51.100.99')" 200

echo
if [ "$fails" -eq 0 ]; then echo "All WordPress hardening checks passed"; else echo "$fails check(s) failed"; exit 1; fi
