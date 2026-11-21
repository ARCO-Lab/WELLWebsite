<?php
// Shortcodes that let the block editor place the WELL pieces that must stay developer-owned code,
// without being able to break them. Each one renders a section partial (sections/*.php) that holds
// the real, interactive markup; an editor drops the shortcode into a page (via a Shortcode block or a
// WELL pattern) and can move or remove it, but cannot edit its internals in a way that breaks it.
//
// Why these stay code (not editable blocks):
//   [well_hero_carousel]   the homepage hero is a Flickity carousel engine (sections/hero.php).
//   [well_latest_news]     the homepage "Latest News" strip queries live posts (sections/news.php).
//   [well_news_list]       the News page's full listing is a live, paginated query (sections/news-list.php).
//   [well_dashboard_embed] embeds the separate Next.js dashboard app over a fixed message origin.
//   [well_dashboard_card]  the homepage dashboard card is a CSS-coupled card (flex-lg-row, hover).
//   [well_team]            each About team card is wired to its own modal by a matching id.
//   [well_sampling_checker] posts files to the dashboard's real CSV validator endpoint.
//
// Each partial echoes its markup, so we capture it with output buffering and return it: a shortcode
// callback must RETURN its output, never echo (echoing prints it above the content).
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

/**
 * Render a section partial to a string, for use as a shortcode's return value.
 */
function well_render_section_shortcode($slug) {
    ob_start();
    get_template_part('sections/' . $slug);
    return (string) ob_get_clean();
}

add_shortcode('well_hero_carousel', function () {
    return well_render_section_shortcode('hero');
});

add_shortcode('well_latest_news', function () {
    return well_render_section_shortcode('news');
});

// The News page's full listing (sections/news-list.php): a live, paginated grid of post cards. It is a
// live query (newest posts first), so like [well_latest_news] it stays developer-owned code; the News
// page carries it as the well/news-list block so the editor previews the real listing.
add_shortcode('well_news_list', function () {
    return well_render_section_shortcode('news-list');
});

add_shortcode('well_dashboard_embed', function () {
    return well_render_section_shortcode('dashboard-embed');
});

// The homepage "The WELL Dashboard" card (sections/dashboard.php): a styled, CSS-coupled card
// (flex-lg-row, card-img-mask-full, hover states) describing the dashboard. Like McSCert's home
// "What We Do" rows, it stays developer-owned code rather than editable blocks; its prose is
// maintained in sections/dashboard.php.
add_shortcode('well_dashboard_card', function () {
    return well_render_section_shortcode('dashboard');
});

add_shortcode('well_team', function () {
    return well_render_section_shortcode('team');
});

add_shortcode('well_sampling_checker', function () {
    return well_render_section_shortcode('sampling-checker');
});
