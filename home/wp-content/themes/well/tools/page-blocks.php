<?php
/**
 * Block-editor content for the WELL pages, as functions that return Gutenberg block markup strings.
 *
 * tools/migrate-pages-to-blocks.php uses these to seed each page's post_content (only when the page is
 * still empty), so the prose that used to be hard-coded in the templates becomes editable in wp-admin.
 * The markup here mirrors the serialization WordPress itself produces for core blocks (see the theme's
 * patterns/ files for verified examples), reuses the site's existing CSS classes so the pages look
 * identical, and places the interactive, developer-owned pieces as shortcodes (see inc/shortcodes.php).
 *
 * Images use root-relative URLs (/wp-content/themes/well/img/media/...), the same convention the theme
 * already uses in sections/about.php, so they resolve wherever the site is served.
 *
 * These functions only BUILD strings; they are safe to load anywhere and have no side effects.
 */
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

/**
 * An <img> string matching well_media_img() (functions.php), but with a root-relative URL so it can be
 * stored in post_content. $widths: the pre-sized copies that exist (array() for a single <name>.webp);
 * $size: the largest copy's [width, height]; $attrs: alt, class, sizes, loading, ...
 */
function well_blocks_media_img($name, $widths, $size, $attrs = array()) {
    $base = '/wp-content/themes/well/img/media/' . $name;
    if (empty($widths)) {
        $src = $base . '.webp';
    } else {
        $srcset = array();
        foreach ($widths as $w) {
            $srcset[] = $base . '-' . $w . '.webp' . ' ' . (int) $w . 'w';
        }
        $attrs = array('srcset' => implode(', ', $srcset)) + $attrs;
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
        $html .= ' ' . $key . '="' . esc_attr($value) . '"';
    }
    return $html . '>';
}

/**
 * The circular profile image used in the About page's text-and-photo sections, as a core/html block
 * (its figure > mask > img structure is what makes the image a dotted circle, so it is preserved as
 * exact HTML rather than a core/image block).
 */
function well_blocks_about_circle($name, $widths, $size, $alt, $lazy = false) {
    $attrs = array('alt' => $alt, 'class' => 'img-fluid', 'sizes' => '300px');
    if ($lazy) {
        $attrs['loading'] = 'lazy';
    }
    $img = well_blocks_media_img($name, $widths, $size, $attrs);
    return "<!-- wp:html -->\n"
        . "<div class=\"text-center\"><figure class=\"mb-0 profile mx-auto\"><div class=\"fig-img-mask rounded-circle\">{$img}</div></figure></div>\n"
        . "<!-- /wp:html -->";
}

/**
 * One "content-area" section of the About page: a heading and paragraphs on one side, a circular photo
 * on the other, inside the site's .content-area > .container banded layout.
 *
 * $heading    the section heading text.
 * $paragraphs array of paragraph HTML (inner text).
 * $circle     a core/html block string (from well_blocks_about_circle()).
 * $text_width flex-basis for the text column, e.g. "66.66%" or "50%".
 * $img_first  true to put the photo on the left (image column first).
 */
function well_blocks_about_section($heading, $paragraphs, $circle, $text_width, $img_first) {
    $img_width = ('50%' === $text_width) ? '50%' : '33.33%';

    $text_inner = "<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">" . $heading . "</h2>\n<!-- /wp:heading -->";
    foreach ($paragraphs as $p) {
        $text_inner .= "\n\n<!-- wp:paragraph -->\n<p>" . $p . "</p>\n<!-- /wp:paragraph -->";
    }

    $text_col = "<!-- wp:column {\"verticalAlignment\":\"center\",\"width\":\"{$text_width}\"} -->\n"
        . "<div class=\"wp-block-column is-vertically-aligned-center\" style=\"flex-basis:{$text_width}\">\n"
        . $text_inner . "\n"
        . "</div>\n<!-- /wp:column -->";

    $img_col = "<!-- wp:column {\"verticalAlignment\":\"center\",\"width\":\"{$img_width}\"} -->\n"
        . "<div class=\"wp-block-column is-vertically-aligned-center\" style=\"flex-basis:{$img_width}\">\n"
        . $circle . "\n"
        . "</div>\n<!-- /wp:column -->";

    $columns = $img_first ? ($img_col . "\n\n" . $text_col) : ($text_col . "\n\n" . $img_col);

    return "<!-- wp:group {\"className\":\"content-area white my-4\",\"layout\":{\"type\":\"default\"}} -->\n"
        . "<div class=\"wp-block-group content-area white my-4\">\n"
        . "<!-- wp:group {\"className\":\"container\",\"layout\":{\"type\":\"default\"}} -->\n"
        . "<div class=\"wp-block-group container\">\n"
        . "<!-- wp:columns {\"verticalAlignment\":\"center\"} -->\n"
        . "<div class=\"wp-block-columns are-vertically-aligned-center\">\n"
        . $columns . "\n"
        . "</div>\n<!-- /wp:columns -->\n"
        . "</div>\n<!-- /wp:group -->\n"
        . "</div>\n<!-- /wp:group -->";
}

/**
 * The About page body: four editable text-and-photo sections, then the developer-owned team grid placed
 * as the [well_team] shortcode.
 */
function well_blocks_about() {
    $sections = array();

    $sections[] = well_blocks_about_section(
        'About WELL',
        array(
            'The Watershed and Ecosystems Living Lab (WELL) is an environmental monitoring initiative based at McMaster University. WELL consists of two components: a network of real-time environmental monitoring sensors in West Campus (near parking Lot P) and a comprehensive sampling regime across the Ancaster Creek watershed from the headwaters, through Mac Forest to Cootes Drive. Data collected though WELL provides continuous insights into the hydrology, climate, and ecological health indicators in the watershed to support teaching, research, professional development workshops, and community engagement.',
            'Led by a team of researchers at McMaster University in partnership with undergraduate and graduate student teams, WELL is a unique resource for environmental science teaching, learning, research, and community engagement.',
        ),
        well_blocks_about_circle('about-watershed', array(300, 600), array(600, 600), 'Ancaster Watershed'),
        '66.66%',
        false
    );

    $sections[] = well_blocks_about_section(
        'What is WELL measuring?',
        array(
            'In West Campus, a fully remote sensor network is collecting real-time data on weather, soil moisture and temperature, water levels, and water quality in Ancaster Creek. A network of nine additional monitoring stations across the Ancaster Creek watershed are sampled bi-weekly for nutrient and water quality parameter, and seasonally for geomorphic processes. Plans to expand sampling to include fish and benthic community monitoring are in place.',
        ),
        well_blocks_about_circle('about-weatherstation', array(300, 600, 900), array(900, 900), 'Ancaster Creek'),
        '50%',
        true
    );

    $sections[] = well_blocks_about_section(
        'What type of teaching does WELL support?',
        array(
            'With plans to expand the instrumentation, WELL is poised to become a cornerstone of environmental education at McMaster. It’s convenient on-campus location makes it easy to integrate into courses of all levels and has already been integrated into several courses across the Faculty of Science and the Faculty of Engineering. WELL has also been used for industry-focused workshops on river monitoring.',
            'WELL also serves as a unique experiential learning opportunity for students. The sensor network in West Campus was installed by a team of undergraduate and graduate students, providing them with hands-on site selection, instrumentation, and fieldwork experience. The sampling regime at the monitoring station across the watershed is also conducted by a team of students. Even this website was designed and built by an undergraduate student research assistant!',
        ),
        well_blocks_about_circle('about-installation', array(300, 600, 900), array(900, 900), 'Ancaster Watershed', true),
        '66.66%',
        false
    );

    $sections[] = well_blocks_about_section(
        'What type of research does WELL support?',
        array(
            'WELL is not connected to a single research project but is rather a shared data collection effort that can support a multitude of research projects in various fields. Some early examples include measuring stream health indicators to assess the success of naturalization projects in West Campus and serving as a testing ground for new sensor technology and geomorphic monitoring techniques.',
        ),
        well_blocks_about_circle('about-research', array(300, 600, 900), array(900, 900), 'Ancaster Creek', true),
        '50%',
        true
    );

    $team = "<!-- wp:shortcode -->\n[well_team]\n<!-- /wp:shortcode -->";

    return implode("\n\n", $sections) . "\n\n" . $team;
}
