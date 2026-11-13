<?php
/**
 * Plugin Name: WELL: hardening
 * Description: Keeps account names away from visitors, limits failed logins per client address, turns off
 *              comments, pingbacks and XML-RPC logins, and stops advertising the WordPress version.
 *
 * A must-use plugin: WordPress loads every PHP file in wp-content/mu-plugins on each request, and it can't be
 * turned off from wp-admin. Deleting this file undoes it. Apache also refuses xmlrpc.php, wp-comments-post.php and
 * wp-trackback.php outright (wordpress/apache-hardening.conf); the filters here still apply if those rules go.
 */

if (!defined('ABSPATH')) {
    exit;
}

/* ---- Account names ------------------------------------------------------------------------------------------- */

// The REST API's user list (/wp-json/wp/v2/users, ?rest_route=/wp/v2/users, /users/<id>) names every account that
// has published, giving password guessers the login names: 401 for anonymous requests. Runs after REST
// authentication, so a cookie without the REST nonce counts as anonymous too; logged-in users (the block editor's
// author picker) are unaffected.
add_filter('rest_pre_dispatch', function ($result, $server, $request) {
    if ($result !== null || is_user_logged_in()) {
        return $result;
    }
    // Case-insensitive, as WordPress matches routes
    if (preg_match('#^/wp/v2/users(/|$)#i', $request->get_route())) {
        return new WP_Error('rest_user_cannot_view', 'Sorry, you are not allowed to list users.', ['status' => 401]);
    }
    return $result;
}, 10, 3);

// /?author=N redirects to /author/<login-slug>/, and author archives show the slug: send anonymous visitors to the
// home page instead. Priority 1 runs before WordPress's own canonical redirect, which would reveal the slug.
add_action('template_redirect', function () {
    if (!is_user_logged_in() && (isset($_GET['author']) || is_author())) {
        wp_safe_redirect(home_url('/'), 302);
        exit;
    }
}, 1);

// oEmbed answers (/wp-json/oembed/1.0/embed?url=...) carry the post author's name and archive URL.
add_filter('oembed_response_data', function ($data) {
    unset($data['author_name'], $data['author_url']);
    return $data;
});

// The core sitemap's users part (/wp-sitemap-users-1.xml, linked from /wp-sitemap.xml and robots.txt) lists every
// author archive, whose URL holds the login slug.
add_filter('wp_sitemaps_add_provider', function ($provider, $name) {
    return $name === 'users' ? false : $provider;
}, 10, 2);

// Post bylines and feeds (<dc:creator>) print the author's display name, which WordPress sets to the login name
// until someone changes it. Show "WELL team" instead whenever the two are the same; a display name set in the
// profile (Users > Profile > "Display name publicly as") is shown as it is. Not in wp-admin, where it is useful.
add_filter('the_author', function ($name) {
    global $authordata;
    if (is_admin() || !($authordata instanceof WP_User)) {
        return $name;
    }
    return strcasecmp((string) $authordata->display_name, (string) $authordata->user_login) === 0 ? 'WELL team' : $name;
});

/* ---- Failed logins ------------------------------------------------------------------------------------------- */

// The campus proxy restricts /wp-admin/ but not /wp-login.php, so nothing else limits password guessing. After
// WELL_LOGIN_MAX_FAILURES failed logins from one client address, with less than WELL_LOGIN_WINDOW_S between each and
// the next, that address can't log in until WELL_LOGIN_WINDOW_S has passed since its last failure; its password
// isn't even checked. Kept in transients (the options table), one per address that has failed recently.
const WELL_LOGIN_MAX_FAILURES = 5;
const WELL_LOGIN_WINDOW_S = 15 * 60;

// The client's address. Apache sees the campus proxy's address for every visitor, so the proxy's X-Forwarded-For is
// used, but only when the connection comes from a proxy listed in WELL_TRUSTED_PROXY_IPS (comma-separated; unset
// means 130.113.68.30, haproxy.cas.mcmaster.ca; set but empty trusts none). Anyone else could write any address in
// that header. The proxy appends the address it saw, so the last entry is the one to believe.
function well_client_ip() {
    $peer = isset($_SERVER['REMOTE_ADDR']) ? (string) $_SERVER['REMOTE_ADDR'] : '';
    $setting = getenv('WELL_TRUSTED_PROXY_IPS');
    $trusted = array_filter(array_map('trim', explode(',', $setting === false ? '130.113.68.30' : $setting)));
    if (in_array($peer, $trusted, true) && !empty($_SERVER['HTTP_X_FORWARDED_FOR'])) {
        $hops = array_map('trim', explode(',', (string) $_SERVER['HTTP_X_FORWARDED_FOR']));
        $client = end($hops);
        if (filter_var($client, FILTER_VALIDATE_IP)) {
            return $client;
        }
    }
    return $peer;
}

function well_login_key() {
    return 'well_login_fail_' . md5(well_client_ip());
}

function well_login_locked() {
    return (int) get_transient(well_login_key()) >= WELL_LOGIN_MAX_FAILURES;
}

// Before any password check (priority 1): a locked-out address gets an error, and the password checks that would
// run next are taken off for this request, so guessing costs no hashing either.
add_filter('authenticate', function ($user) {
    if (!well_login_locked()) {
        return $user;
    }
    remove_filter('authenticate', 'wp_authenticate_username_password', 20);
    remove_filter('authenticate', 'wp_authenticate_email_password', 20);
    remove_filter('authenticate', 'wp_authenticate_application_password', 20);
    return new WP_Error('well_login_locked', 'Too many failed login attempts. Try again in 15 minutes.');
}, 1);

// And last: if anything let a locked-out address through, refuse it anyway.
add_filter('authenticate', function ($user) {
    return ($user instanceof WP_User && well_login_locked())
        ? new WP_Error('well_login_locked', 'Too many failed login attempts. Try again in 15 minutes.')
        : $user;
}, PHP_INT_MAX);

add_action('wp_login_failed', function () {
    $key = well_login_key();
    set_transient($key, (int) get_transient($key) + 1, WELL_LOGIN_WINDOW_S);
});

add_action('wp_login', function () {
    delete_transient(well_login_key());
});

/* ---- Comments, pingbacks, XML-RPC ---------------------------------------------------------------------------- */

// The theme shows no comments and has no comment form, but comments and pingbacks were open on posts, so bots could
// post them straight to wp-comments-post.php and fill the moderation queue. Closed everywhere, existing ones aren't
// shown, and no post type offers them in the editor.
add_filter('comments_open', '__return_false', 20);
add_filter('pings_open', '__return_false', 20);
add_filter('comments_array', '__return_empty_array', 20);
add_action('init', function () {
    foreach (get_post_types() as $type) {
        remove_post_type_support($type, 'comments');
        remove_post_type_support($type, 'trackbacks');
    }
}, 100);

// XML-RPC: no methods that log in with a user name and password, and no pingbacks.
add_filter('xmlrpc_enabled', '__return_false');
add_filter('xmlrpc_methods', function ($methods) {
    unset($methods['pingback.ping'], $methods['pingback.extensions.getPingbacks']);
    return $methods;
});

// Stop advertising them: the RSD link in <head>, the X-Pingback header, and the pingback URL (empty, should any
// template print it with bloginfo('pingback_url')).
remove_action('wp_head', 'rsd_link');
add_filter('wp_headers', function ($headers) {
    unset($headers['X-Pingback']);
    return $headers;
});
add_filter('bloginfo_url', function ($output, $show) {
    return $show === 'pingback_url' ? '' : $output;
}, 10, 2);

/* ---- Version ------------------------------------------------------------------------------------------------- */

// <meta name="generator" content="WordPress x.y.z"> in pages, and the generator line in feeds and OPML.
remove_action('wp_head', 'wp_generator');
add_filter('the_generator', '__return_empty_string');
