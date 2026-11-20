<?php
// Dynamic blocks for the WELL pieces that must stay developer-owned code (hero carousel, dashboard
// embed, live news strip, dashboard card, team cards, sampling checker).
//
// These used to be placed as raw [shortcode] blocks, which show in the block editor as a bare
// "Shortcode" placeholder: the editor could not SEE the team cards, the dashboard embed or the
// checker. Each is now a dynamic block instead:
//
//   - the SAME section partial (sections/*.php) is the render output, so the FRONT END is byte-for-byte
//     unchanged from the old shortcode (well_render_section_shortcode() is shared with inc/shortcodes.php);
//   - in the editor the block previews its real server-rendered HTML with a <ServerSideRender>, so an
//     editor sees the actual team cards / dashboard / checker while editing (see js/blocks.js).
//
// The matching shortcodes stay registered (inc/shortcodes.php) so any page or content that still uses
// [well_team] etc. keeps working; tools/page-blocks.php now emits these block comments instead.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

/**
 * The developer-owned blocks, as block name => the section partial (sections/<slug>.php) it renders.
 * The names mirror the old shortcodes so the mapping is obvious.
 */
function well_dynamic_blocks() {
    return array(
        'well/hero-carousel'    => 'hero',
        'well/latest-news'      => 'news',
        'well/dashboard-embed'  => 'dashboard-embed',
        'well/dashboard-card'   => 'dashboard',
        'well/team'             => 'team',
        'well/sampling-checker' => 'sampling-checker',
    );
}

/**
 * Register the blocks on both sides: a render_callback (server + the ServerSideRender REST endpoint the
 * editor uses) and one shared editor script that defines each block's edit/preview (js/blocks.js).
 */
function well_register_blocks() {
    // well_render_section_shortcode() lives in inc/shortcodes.php; both are required by functions.php.
    if ( ! function_exists( 'well_render_section_shortcode' ) ) {
        require_once get_template_directory() . '/inc/shortcodes.php';
    }

    wp_register_script(
        'well-blocks-editor',
        get_template_directory_uri() . '/js/blocks.js',
        array( 'wp-blocks', 'wp-element', 'wp-block-editor', 'wp-components', 'wp-server-side-render', 'wp-i18n' ),
        well_asset_version( '/js/blocks.js' ),
        true
    );

    foreach ( well_dynamic_blocks() as $name => $slug ) {
        register_block_type( $name, array(
            'api_version'     => 3,
            'editor_script'   => 'well-blocks-editor',
            // No attributes and no inner content: the partial owns all the markup.
            'render_callback' => function ( $attributes, $content ) use ( $slug ) {
                return well_render_section_shortcode( $slug );
            },
        ) );
    }
}
add_action( 'init', 'well_register_blocks' );

/**
 * Add a "WELL" block category so these blocks group together in the inserter, next to the WELL
 * pattern category registered in functions.php.
 */
function well_block_categories( $categories ) {
    foreach ( $categories as $category ) {
        if ( isset( $category['slug'] ) && 'well' === $category['slug'] ) {
            return $categories; // already present
        }
    }
    array_unshift( $categories, array(
        'slug'  => 'well',
        'title' => __( 'WELL', 'well' ),
        'icon'  => null,
    ) );
    return $categories;
}
add_filter( 'block_categories_all', 'well_block_categories' );
