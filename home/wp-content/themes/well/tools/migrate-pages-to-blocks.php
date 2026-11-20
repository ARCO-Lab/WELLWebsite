<?php
/**
 * Seed the WELL pages' block-editor content, so prose that used to be hard-coded in the templates
 * becomes editable in wp-admin. Idempotent and safe to re-run: it writes a page's post_content ONLY
 * when that page is still empty (never migrated, or a brand-new install), so it never clobbers text an
 * editor has since changed.
 *
 * The block markup itself lives in tools/page-blocks.php.
 *
 * HOW TO RUN (on the VM, from the WordPress root — do NOT edit the database by hand):
 *
 *   # Preview what would change, without writing anything:
 *   wp eval-file wp-content/themes/well/tools/migrate-pages-to-blocks.php --dry-run
 *
 *   # Apply:
 *   wp eval-file wp-content/themes/well/tools/migrate-pages-to-blocks.php
 *
 * (wp-cli runs inside the WELL Docker wordpress container; see deploy.sh for how wp-cli is invoked
 * there. Pass extra args after the file path; --dry-run and --verbose are both understood.)
 *
 * It can also be included from an admin-only context; in that case it requires the current user to be
 * able to edit pages and a defined WELL_RUN_PAGE_MIGRATION === true, so a stray web request cannot
 * trigger it.
 */

defined( 'ABSPATH' ) || exit; // Only WordPress (wp-cli included) may load this file.

// Only ever run from wp-cli, or from an explicitly-guarded admin include. Never from a plain request.
if ( defined( 'WP_CLI' ) && WP_CLI ) {
    // ok: command line
} elseif ( defined( 'WELL_RUN_PAGE_MIGRATION' ) && WELL_RUN_PAGE_MIGRATION && current_user_can( 'edit_pages' ) ) {
    // ok: a privileged admin include that opted in
} else {
    return;
}

require_once __DIR__ . '/page-blocks.php';

/**
 * The pages to seed. Each 'find' returns a WP_Post or null; 'content' is the block markup to store.
 * Add a page here once its block content exists in page-blocks.php.
 */
function well_migration_targets() {
    return array(
        array(
            'label'   => 'About (/about/)',
            'find'    => function () { return get_page_by_path( 'about' ); },
            'content' => 'well_blocks_about',
        ),
        array(
            'label'   => 'Dashboard (/dashboard/)',
            'find'    => function () { return get_page_by_path( 'dashboard' ); },
            'content' => 'well_blocks_dashboard',
        ),
        array(
            // Only seeds the home page when the site uses a static front page (Settings > Reading).
            'label'   => 'Home (static front page)',
            'find'    => function () {
                $id = (int) get_option( 'page_on_front' );
                return $id ? get_post( $id ) : null;
            },
            'content' => 'well_blocks_front_page',
        ),
        array(
            // The Sampling Data Upload Guide: found by its page template, not a fixed slug/id.
            'label'   => 'Sampling Data Upload Guide',
            'find'    => function () {
                $pages = get_posts( array(
                    'post_type'   => 'page',
                    'post_status' => 'any',
                    'numberposts' => 1,
                    'meta_key'    => '_wp_page_template',
                    'meta_value'  => 'template-sampling-upload.php',
                ) );
                return ! empty( $pages ) ? $pages[0] : null;
            },
            'content' => 'well_blocks_sampling',
        ),
    );
}

/**
 * A page counts as "not yet migrated" when its content has no blocks at all and no real text — an
 * empty string or whitespace. If it already contains ANY blocks (even a single empty paragraph or a
 * lone shortcode an editor added), we leave it untouched, so we never overwrite editor changes.
 */
function well_migration_page_is_empty( $post ) {
    if ( ! $post instanceof WP_Post ) {
        return false;
    }
    $content = (string) $post->post_content;
    if ( has_blocks( $content ) ) {
        return false; // already has block content
    }
    return '' === trim( wp_strip_all_tags( $content ) );
}

/**
 * Run the migration. Returns a list of human-readable result lines.
 */
function well_run_page_migration( $dry_run = false ) {
    $results = array();

    // Block comments (<!-- wp:... -->) would be stripped by post-content kses filtering when the run
    // has no user with unfiltered_html (e.g. wp-cli). Remove those filters for the write, then restore.
    $restore_kses = ! $dry_run;
    if ( $restore_kses ) {
        kses_remove_filters();
    }

    foreach ( well_migration_targets() as $target ) {
        $label = $target['label'];
        $post  = call_user_func( $target['find'] );

        if ( ! $post instanceof WP_Post ) {
            $results[] = "SKIP  {$label}: page not found.";
            continue;
        }

        if ( ! well_migration_page_is_empty( $post ) ) {
            $results[] = "SKIP  {$label}: already has content (left untouched).";
            continue;
        }

        if ( ! is_callable( $target['content'] ) ) {
            $results[] = "SKIP  {$label}: no block content defined yet.";
            continue;
        }

        $content = call_user_func( $target['content'] );

        if ( $dry_run ) {
            $results[] = "WOULD SET  {$label}: " . strlen( $content ) . " bytes of block content.";
            continue;
        }

        $updated = wp_update_post(
            array(
                'ID'           => $post->ID,
                'post_content' => $content,
            ),
            true
        );

        if ( is_wp_error( $updated ) ) {
            $results[] = "ERROR {$label}: " . $updated->get_error_message();
        } else {
            $results[] = "SET   {$label}: wrote " . strlen( $content ) . " bytes (post {$post->ID}).";
        }
    }

    if ( $restore_kses ) {
        kses_init_filters();
    }

    return $results;
}

// --- Entry point ---------------------------------------------------------

$well_migration_args = array();
if ( defined( 'WP_CLI' ) && WP_CLI && isset( $args ) && is_array( $args ) ) {
    $well_migration_args = $args; // positional args after the file path
}
// wp eval-file passes flags in $assoc_args too; accept --dry-run from either place.
$well_dry_run = false;
if ( isset( $assoc_args ) && is_array( $assoc_args ) && ! empty( $assoc_args['dry-run'] ) ) {
    $well_dry_run = true;
}
if ( in_array( 'dry-run', $well_migration_args, true ) || in_array( '--dry-run', $well_migration_args, true ) ) {
    $well_dry_run = true;
}

$well_migration_results = well_run_page_migration( $well_dry_run );

$well_migration_header = $well_dry_run
    ? 'WELL page migration (dry run — nothing written):'
    : 'WELL page migration:';

if ( defined( 'WP_CLI' ) && WP_CLI ) {
    WP_CLI::log( $well_migration_header );
    foreach ( $well_migration_results as $line ) {
        WP_CLI::log( '  ' . $line );
    }
} else {
    echo esc_html( $well_migration_header ) . "\n";
    foreach ( $well_migration_results as $line ) {
        echo '  ' . esc_html( $line ) . "\n";
    }
}
