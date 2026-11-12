<?php
/**
 * Plugin Name: WELL: hardening
 * Description: Keeps account names away from visitors (REST user list, ?author=N, oEmbed author fields) and turns
 *              off XML-RPC logins and pingbacks, along with the links that advertise them.
 *
 * A must-use plugin: WordPress loads every PHP file in wp-content/mu-plugins on each request, and it can't be
 * turned off from wp-admin. Deleting this file undoes it. Apache also refuses xmlrpc.php outright
 * (wordpress/apache-hardening.conf); the XML-RPC filters here still apply if that rule is ever removed.
 */

if (!defined('ABSPATH')) {
    exit;
}

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

// XML-RPC: no methods that log in with a user name and password, and no pingbacks.
add_filter('xmlrpc_enabled', '__return_false');
add_filter('xmlrpc_methods', function ($methods) {
    unset($methods['pingback.ping'], $methods['pingback.extensions.getPingbacks']);
    return $methods;
});

// Stop advertising them: the RSD link in <head>, the X-Pingback header, and the pingback URL. The theme's header.php
// prints <link rel="pingback" href="..."> itself, so its URL is emptied here (the link then points nowhere).
remove_action('wp_head', 'rsd_link');
add_filter('wp_headers', function ($headers) {
    unset($headers['X-Pingback']);
    return $headers;
});
add_filter('bloginfo_url', function ($output, $show) {
    return $show === 'pingback_url' ? '' : $output;
}, 10, 2);
