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

    // 2. Register the menu location.
    register_nav_menus( array(
        'primary' => __( 'Primary Menu', 'well' ),
    ) );
}
// This hook runs our setup function as WordPress loads.
add_action( 'after_setup_theme', 'well_theme_setup' );

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
            '1.0'
        );
    }

    // 3. Enqueue McMaster header styles
    wp_enqueue_style(
        'well-mcmaster-header',
        get_template_directory_uri() . '/css/mcmaster-header.css',
        ['well-google-fonts'],
        '1.0'
    );

    // --- JAVASCRIPT (.js files) ---

    // 4. Enqueue all the theme's JS files from the /js/ folder.
    // We list 'jquery' as a dependency since many old themes use it.
    $js_files = [
        'popper.min', 'theme.min', 'ekko-lightbox.min', 'header_footer',
        'hfcopy', 'mcmaster', 'countdown-timer', 'video_slider',
        'wp-form-name-fields', 'comm100-wrapper'
    ];

    foreach ($js_files as $file) {
        wp_enqueue_script(
            'well-' . str_replace('.min', '', $file), // A unique name for each script, e.g., 'well-popper'
            get_template_directory_uri() . '/js/' . $file . '.js',
            ['jquery'], // Dependency
            '1.0',
            true // Load the script in the footer
        );
    }

    // 5. Enqueue McMaster header JavaScript
    wp_enqueue_script(
        'well-mcmaster-header-js',
        get_template_directory_uri() . '/js/mcmaster-header.js',
        ['jquery'],
        '1.0',
        true
    );
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

?>