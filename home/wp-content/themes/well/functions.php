<?php
// This file contains theme setup, asset loading, widget registration, and helper functions for the WELL WordPress theme.
// It registers navigation menus, enqueues CSS/JS, sets up widget areas, and provides utility functions.

/**
 * Register navigation menus and load the Navwalker.
 * This function runs when the theme is initialized.
 */
function well_theme_setup() {
    // 1. Load the Bootstrap Navwalker file.
    require_once get_template_directory() . '/inc/class-wp-bootstrap-navwalker.php';

    add_theme_support('post-thumbnails');

    // Standardized responsive image targets used across homepage/section media.
    add_image_size('well-mobile', 414, 0, false);
    add_image_size('well-tablet', 720, 0, false);
    add_image_size('well-desktop', 1080, 0, false);
    add_image_size('well-large', 1600, 0, false);

    // 2. Register the menu location.
    register_nav_menus( array(
        'primary' => __( 'Primary Menu', 'well' ),
    ) );
}
// This hook runs our setup function as WordPress loads.
add_action( 'after_setup_theme', 'well_theme_setup' );

/**
 * Resolve deployment mode from environment.
 * Expected values: PROD or DEV.
 */
function well_get_deployment_mode() {
    $deployment = getenv('DEPLOYMENT');

    if (!is_string($deployment) || $deployment === '') {
        return 'DEV';
    }

    return strtoupper(trim($deployment));
}

/**
 * Force HTTPS URLs for all assets/content in production mode.
 */
function well_should_force_https_urls() {
    if (well_get_deployment_mode() === 'PROD') {
        return true;
    }

    if (well_get_deployment_mode() === 'DEV') {
        return false;
    }

    // Safe fallback for unexpected values: keep host-based production detection.
    $host = isset($_SERVER['HTTP_HOST']) ? strtolower($_SERVER['HTTP_HOST']) : '';
    $host = preg_replace('/:\\d+$/', '', $host);

    $production_hosts = array(
        'well.mcmaster.ca',
        'www.well.mcmaster.ca',
    );

    return in_array($host, $production_hosts, true);
}

function well_force_https_urls($url) {
    if (is_string($url)) {
        return str_replace('http://', 'https://', $url);
    }
    return $url;
}

if (well_should_force_https_urls()) {
    // PROD mode: apply URL normalization globally (legacy behavior).
    add_filter('option_home', 'well_force_https_urls');
    add_filter('option_siteurl', 'well_force_https_urls');
    add_filter('content_url', 'well_force_https_urls');
    add_filter('plugins_url', 'well_force_https_urls');
    add_filter('theme_root_uri', 'well_force_https_urls');
    add_filter('stylesheet_directory_uri', 'well_force_https_urls');
    add_filter('template_directory_uri', 'well_force_https_urls');
    add_filter('script_loader_src', 'well_force_https_urls');
    add_filter('style_loader_src', 'well_force_https_urls');
    add_filter('wp_get_attachment_url', 'well_force_https_urls');
    add_filter('wp_get_attachment_image_src', 'well_force_https_urls');
    add_filter('the_content', 'well_force_https_urls');
    add_filter('bloginfo_url', 'well_force_https_urls');

    // Catch remaining hardcoded production URLs in rendered HTML.
    function well_force_https_output_buffer($buffer) {
        return str_replace('http://well.mcmaster.ca', 'https://well.mcmaster.ca', $buffer);
    }

    add_action('template_redirect', function() {
        ob_start('well_force_https_output_buffer');
    });
}

/**
 * Version string for a theme CSS/JS file: its modification time. WordPress adds it to the URL
 * (?ver=...), so an edited file gets a new URL and browsers can cache each URL for a long time
 * (see wordpress/zz-performance.conf). Falls back to '1.0' if the file is missing.
 */
function well_asset_version($relative_path) {
    $mtime = @filemtime(get_template_directory() . $relative_path);
    return $mtime ? (string) $mtime : '1.0';
}

/**
 * This function is the proper WordPress way to load all of our theme's
 * CSS stylesheets and JavaScript files.
 */
function well_theme_enqueue_assets() {

    // --- STYLESHEETS (.css files) ---

    // 1. Enqueue Google Fonts (Poppins)
    // This is required by your typography.css file.
    wp_enqueue_style(
        'well-google-fonts',
        'https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,400;0,600;0,700;1,400&display=swap',
        [],
        null
    );

    // 2. Enqueue all the theme's CSS files from the /css/ folder.
    // We list 'well-google-fonts' as a dependency to ensure fonts load first.
    $css_files = [
        'theme', 'mcm-bw', 'typography', 'btn', 'footer', 'new-cards',
        'dynamic-filters', 'element-left-nav', 'aoda', 'ldap', 'loader'
    ];

    foreach ($css_files as $file) {
        wp_enqueue_style(
            'well-' . $file, // A unique name for each stylesheet, e.g., 'well-theme'
            get_template_directory_uri() . '/css/' . $file . '.css',
            ['well-google-fonts'], // Dependency
            well_asset_version('/css/' . $file . '.css')
        );
    }

    // --- JAVASCRIPT (.js files) ---

    // 3. Enqueue all the theme's JS files from the /js/ folder.
    // We list 'jquery' as a dependency since many old themes use it.
    // js/video_slider.js is not loaded: it is for YouTube hero videos this site doesn't have, and
    // it loaded the YouTube player API on every page before stopping with an error.
    $js_files = [
        'popper.min', 'theme.min', 'ekko-lightbox.min', 'header_footer',
        'hfcopy', 'mcmaster', 'countdown-timer',
        'wp-form-name-fields', 'comm100-wrapper'
    ];

    foreach ($js_files as $file) {
        wp_enqueue_script(
            'well-' . str_replace('.min', '', $file), // A unique name for each script, e.g., 'well-popper'
            get_template_directory_uri() . '/js/' . $file . '.js',
            ['jquery'], // Dependency
            well_asset_version('/js/' . $file . '.js'),
            true // Load the script in the footer
        );
    }
}

// This is the WordPress "hook" that tells WordPress to run our function at the right time.
add_action('wp_enqueue_scripts', 'well_theme_enqueue_assets');

function well_widgets_init() {
    register_sidebar( array(
        'name'          => __( 'Footer 1', 'well' ),
        'id'            => 'footer-1',
        'before_widget' => '<div class="footer-widget">',
        'after_widget'  => '</div>',
        'before_title'  => '<h4 class="footer-widget-title">',
        'after_title'   => '</h4>',
    ) );
    register_sidebar( array(
        'name'          => __( 'Footer 2', 'well' ),
        'id'            => 'footer-2',
        'before_widget' => '<div class="footer-widget">',
        'after_widget'  => '</div>',
        'before_title'  => '<h4 class="footer-widget-title">',
        'after_title'   => '</h4>',
    ) );
    register_sidebar( array(
        'name'          => __( 'Footer 3', 'well' ),
        'id'            => 'footer-3',
        'before_widget' => '<div class="footer-widget">',
        'after_widget'  => '</div>',
        'before_title'  => '<h4 class="footer-widget-title">',
        'after_title'   => '</h4>',
    ) );
}
add_action( 'widgets_init', 'well_widgets_init' );

function well_enqueue_flickity_assets() {
    // Flickity CSS
    wp_enqueue_style(
        'flickity-css',
        'https://cdnjs.cloudflare.com/ajax/libs/flickity/2.1.1/flickity.min.css',
        [],
        '2.1.1'
    );
    // Flickity JS
    wp_enqueue_script(
        'flickity-js',
        'https://cdnjs.cloudflare.com/ajax/libs/flickity/2.2.2/flickity.pkgd.min.js',
        [],
        '2.2.2',
        true
    );
}
add_action('wp_enqueue_scripts', 'well_enqueue_flickity_assets');

/**
 * Open the connections to Google Fonts early. The Poppins stylesheet comes from fonts.googleapis.com
 * and its font files from fonts.gstatic.com; without this the browser finds the second host only
 * after the first stylesheet has downloaded.
 */
function well_resource_hints($urls, $relation_type) {
    if ('preconnect' === $relation_type) {
        $urls[] = 'https://fonts.googleapis.com';
        $urls[] = array('href' => 'https://fonts.gstatic.com', 'crossorigin');
    }
    return $urls;
}
add_filter('wp_resource_hints', 'well_resource_hints', 10, 2);

/**
 * Print an <img> for a photo the theme ships pre-sized in img/media/ as <name>-<width>.webp
 * (made from the originals in wp-content/uploads by wordpress/theme-images.mjs).
 *
 * The templates used to link the uploaded originals directly: camera photos up to 4032 px and
 * 13 MB, shown at 300-1300 px. With srcset and sizes the browser downloads only the copy its
 * screen needs; width and height let it reserve the space before the image arrives.
 *
 * $widths: the copies that exist, e.g. array(414, 720, 1080); array() for a single <name>.webp.
 * $size:   the largest copy's width and height in pixels, e.g. array(1080, 463).
 * $attrs:  other attributes (alt, class, sizes, loading, fetchpriority, ...).
 */
function well_media_img($name, $widths, $size, $attrs = array()) {
    $base = get_template_directory_uri() . '/img/media/' . $name;
    if (empty($widths)) {
        $src = $base . '.webp';
    } else {
        $srcset = array();
        foreach ($widths as $w) {
            $srcset[] = esc_url($base . '-' . $w . '.webp') . ' ' . (int) $w . 'w';
        }
        $attrs = array('srcset' => implode(', ', $srcset)) + $attrs;
        // Browsers that ignore srcset get a middle size.
        $src = $base . '-' . $widths[(int) floor((count($widths) - 1) / 2)] . '.webp';
    }

    $attrs = array(
        'src'      => $src,
        'width'    => (int) $size[0],
        'height'   => (int) $size[1],
        'decoding' => 'async',
    ) + $attrs;

    $html = '<img';
    foreach ($attrs as $key => $value) {
        if ('src' === $key) {
            $html .= ' src="' . esc_url($value) . '"';
        } elseif ('srcset' === $key) {
            $html .= ' srcset="' . esc_attr($value) . '"';
        } else {
            $html .= ' ' . $key . '="' . esc_attr($value) . '"';
        }
    }
    echo $html . '>';
}

/**
 * Add McMaster navigation menu items (as used in the original site)
 */
function well_get_mcmaster_nav_menu() {
    return array(
        array(
            'title' => 'McMaster',
            'url' => 'https://www.mcmaster.ca',
            'id' => 'sub-macmain',
            'children' => array(
                array('title' => 'Overview', 'url' => 'https://www.mcmaster.ca/opr/html/academics/main/academics.html')
            )
        ),
        array(
            'title' => 'Discover McMaster',
            'url' => '#',
            'id' => 'sub-discover-mcmaster',
            'children' => array(
                array('title' => 'About McMaster', 'url' => 'https://www.mcmaster.ca/about'),
                array('title' => 'Campus Tours', 'url' => 'https://www.mcmaster.ca/visit'),
                array('title' => 'News & Events', 'url' => 'https://dailynews.mcmaster.ca')
            )
        ),
        array(
            'title' => 'Academics',
            'url' => '#',
            'id' => 'sub-academics',
            'children' => array(
                array('title' => 'Overview', 'url' => 'https://www.mcmaster.ca/opr/html/academics/main/academics.html'),
                array('title' => 'Undergraduate Programs', 'url' => 'https://future.mcmaster.ca'),
                array('title' => 'Graduate Programs', 'url' => 'https://gs.mcmaster.ca')
            )
        ),
        array(
            'title' => 'Library',
            'url' => '#',
            'id' => 'sub-library',
            'expanded' => true,
            'children' => array(
                array('title' => 'Home', 'url' => 'https://library.mcmaster.ca'),
                array('title' => 'Services', 'url' => 'https://library.mcmaster.ca/services')
            )
        )
    );
}

/**
 * Normalize image attributes in post content.
 * - Remove WordPress 6.7+ sizes="auto, ..." token.
 * - Strip malformed inline aspect-ratio styles that can force image squish.
 */
function well_remove_auto_sizes_from_content_images($content) {
    if (is_singular() && in_the_loop() && is_main_query() && is_string($content) && $content !== '') {
        // Remove "auto, " from sizes attributes in post content images.
        $content = preg_replace('/\s+sizes="auto,\s*([^"]+)"/i', ' sizes="$1"', $content);

        // Remove inline aspect-ratio declarations that can distort images.
        $content = preg_replace(
            '/(<img[^>]*\sstyle="[^"]*)\s*aspect-ratio\s*:\s*[^;\"]+;?\s*([^"]*")/i',
            '$1 $2',
            $content
        );

        // Clean up empty style attributes left after removals.
        $content = preg_replace('/\sstyle="\s*"/i', '', $content);
    }

    return $content;
}
add_filter('the_content', 'well_remove_auto_sizes_from_content_images', 20);

/**
 * Count page views with GoatCounter (https://www.goatcounter.com): no cookies, nothing stored in the browser, and
 * GoatCounter keeps only aggregated counts. The site shares one GoatCounter site with the dashboard, so each path is
 * counted with the host in front ("well.mcmaster.ca/news/"), which keeps the two sites' "/" apart. Query strings are
 * left out of the path. Nothing is counted for logged-in users (editors checking their pages), in previews, or on
 * any host other than well.mcmaster.ca (count.js also skips localhost and pages shown inside a frame).
 */
function well_goatcounter_script() {
    if (is_admin() || is_user_logged_in() || is_preview() || is_customize_preview()) {
        return;
    }
    ?>
<script>
window.goatcounter = {
    path: function (p) {
        var host = location.hostname.replace(/^www\./, '');
        return host === 'well.mcmaster.ca' ? host + p.split(/[?#]/)[0] : null;
    }
};
</script>
<script data-goatcounter="https://well.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
    <?php
}
add_action('wp_footer', 'well_goatcounter_script');

?>