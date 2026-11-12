<?php
/**
 * Plugin Name: WELL: hide user accounts from visitors
 * Description: Answers 401 to anonymous requests for the REST API's user list (/wp-json/wp/v2/users and
 *              ?rest_route=/wp/v2/users), which otherwise names every account that has published, giving password
 *              guessers the login names. Logged-in users (the block editor's author picker) are unaffected.
 *
 * A must-use plugin: WordPress loads every PHP file in wp-content/mu-plugins on each request, and it can't be
 * turned off from wp-admin. Deleting this file undoes it.
 */

if (!defined('ABSPATH')) {
    exit;
}

add_filter('rest_pre_dispatch', function ($result, $server, $request) {
    // Runs after REST authentication, so a cookie without the REST nonce counts as anonymous here too.
    if ($result !== null || is_user_logged_in()) {
        return $result;
    }
    // Case-insensitive, as WordPress matches routes
    if (preg_match('#^/wp/v2/users(/|$)#i', $request->get_route())) {
        return new WP_Error('rest_user_cannot_view', 'Sorry, you are not allowed to list users.', ['status' => 401]);
    }
    return $result;
}, 10, 3);
