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

/**
 * A core/html block wrapping exact HTML (used for pieces whose markup must stay byte-identical, such as
 * logos with inline sizing or figures with a specific mask structure).
 */
function well_blocks_html($inner) {
    return "<!-- wp:html -->\n" . $inner . "\n<!-- /wp:html -->";
}

/**
 * A core/shortcode block for one of the developer-owned shortcodes (see inc/shortcodes.php).
 */
function well_blocks_shortcode($shortcode) {
    return "<!-- wp:shortcode -->\n[" . $shortcode . "]\n<!-- /wp:shortcode -->";
}

/**
 * The Dashboard page body: the live dashboard embed (developer-owned shortcode), then the editable
 * "Archived Datasets" section with the Borealis and SharePoint repository links.
 */
function well_blocks_dashboard() {
    $embed = well_blocks_shortcode('well_dashboard_embed');

    // Borealis logo (an uploaded image with specific inline sizing) and SharePoint logo (theme media),
    // kept as exact HTML so they match the original.
    $borealis_img = well_blocks_html(
        '<div class="text-center"><figure class="mw-100"><img alt="Borealis Logo" srcset="/wp-content/uploads/2025/09/borealislogo.jpg 414w, /wp-content/uploads/2025/09/borealislogo.jpg 720w, /wp-content/uploads/2025/09/borealislogo.jpg 1080w, /wp-content/uploads/2025/09/borealislogo.jpg 1600w" sizes="(max-width: 480px) 140px, (max-width: 800px) 220px, 280px" src="/wp-content/uploads/2025/09/borealislogo.jpg" class="img-fluid d-block mx-auto" style="max-width: 200px; width: 100%; height: auto;" loading="lazy" decoding="async"></figure></div>'
    );

    $sharepoint_img = well_blocks_html(
        '<div class="text-center"><figure class="mw-100">'
        . well_blocks_media_img('logo-sharepoint', array(280, 560, 840), array(840, 560), array(
            'alt'     => 'SharePoint Logo',
            'sizes'   => '(max-width: 480px) 140px, (max-width: 800px) 220px, 280px',
            'class'   => 'img-fluid d-block mx-auto',
            'loading' => 'lazy',
        ))
        . '</figure></div>'
    );

    $buttons = well_blocks_html(
        '<p style="text-align: left;"><a class="btn btn-primary btn-lg text-center d-inline-block mb-2 mr-sm-2" style="background-color: #fdbf57; color: black; border-color: #FDBF57;" href="https://borealisdata.ca/dataverse/WELL" target="_blank" rel="noopener noreferrer">Borealis</a> <a class="btn btn-primary btn-lg text-center d-inline-block mb-2" style="background-color: #fdbf57; color: black; border-color: #FDBF57;" href="https://mcmasteru365.sharepoint.com/sites/WELL" target="_blank" rel="noopener noreferrer">Sharepoint</a></p>'
    );

    $center = "<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">Archived Datasets</h2>\n<!-- /wp:heading -->\n\n"
        . "<!-- wp:paragraph -->\n<p>For premade datasets uploaded monthly, visit the <strong>WELL</strong> data repositories:</p>\n<!-- /wp:paragraph -->\n\n"
        . $buttons;

    $left_col   = "<!-- wp:column {\"verticalAlignment\":\"center\",\"width\":\"33.33%\"} -->\n<div class=\"wp-block-column is-vertically-aligned-center\" style=\"flex-basis:33.33%\">\n" . $borealis_img . "\n</div>\n<!-- /wp:column -->";
    $center_col = "<!-- wp:column {\"verticalAlignment\":\"center\",\"width\":\"33.33%\"} -->\n<div class=\"wp-block-column is-vertically-aligned-center\" style=\"flex-basis:33.33%\">\n" . $center . "\n</div>\n<!-- /wp:column -->";
    $right_col  = "<!-- wp:column {\"verticalAlignment\":\"center\",\"width\":\"33.33%\"} -->\n<div class=\"wp-block-column is-vertically-aligned-center\" style=\"flex-basis:33.33%\">\n" . $sharepoint_img . "\n</div>\n<!-- /wp:column -->";

    $archived = "<!-- wp:group {\"className\":\"content-area cool-grey my-4\",\"layout\":{\"type\":\"default\"}} -->\n"
        . "<div class=\"wp-block-group content-area cool-grey my-4\">\n"
        . "<!-- wp:group {\"className\":\"container\",\"layout\":{\"type\":\"default\"}} -->\n"
        . "<div class=\"wp-block-group container\">\n"
        . "<!-- wp:columns {\"verticalAlignment\":\"center\"} -->\n"
        . "<div class=\"wp-block-columns are-vertically-aligned-center\">\n"
        . $left_col . "\n\n" . $center_col . "\n\n" . $right_col . "\n"
        . "</div>\n<!-- /wp:columns -->\n"
        . "</div>\n<!-- /wp:group -->\n"
        . "</div>\n<!-- /wp:group -->";

    return $embed . "\n\n" . $archived;
}

/**
 * The home page body, top to bottom: the hero carousel and the dashboard card (both developer-owned
 * shortcodes), the editable "About Us" blurb, then the live "Latest News" strip (shortcode). This
 * mirrors front-page.php's section order; only the About blurb becomes editable blocks, matching how
 * the McSCert home page keeps its hero, feature rows and news strip as code.
 */
function well_blocks_front_page() {
    $hero = well_blocks_shortcode('well_hero_carousel');
    $card = well_blocks_shortcode('well_dashboard_card');
    $news = well_blocks_shortcode('well_latest_news');

    $logo = well_blocks_html(
        '<div class="text-center"><figure class="mw-100"><img alt="WELL Logo" srcset="/wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-32x32.png 32w, /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-150x150.png 150w, /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-180x180.png 180w, /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-192x192.png 192w, /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-270x270.png 270w, /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-300x300.png 300w, /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG.png 600w" sizes="(max-width: 480px) 140px, (max-width: 800px) 220px, 280px" src="/wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG.png" class="img-fluid d-block mx-auto" loading="lazy" decoding="async"></figure></div>'
    );

    $button = well_blocks_html(
        '<p style="text-align: left;"><a class="btn btn-primary btn-lg text-center" style="background-color: #fdbf57; color: black; border-color: #FDBF57;" href="/about">Learn More</a></p>'
    );

    $text = "<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">About Us</h2>\n<!-- /wp:heading -->\n\n"
        . "<!-- wp:paragraph -->\n<p>The <strong> Watershed and Ecosystems Living Lab (WELL) </strong> at McMaster University is an interdisciplinary initiative that brings together students, researchers, and the community to monitor and learn from real-time environmental data. <strong>WELL</strong> provides hands-on learning opportunities and valuable data through its network of real-time environmental sensors and comprehensive watershed-wide sampling regime within the Ancaster Creek watershed in Hamilton. </p>\n<!-- /wp:paragraph -->\n\n"
        . $button;

    $logo_col = "<!-- wp:column {\"verticalAlignment\":\"center\",\"width\":\"33.33%\"} -->\n<div class=\"wp-block-column is-vertically-aligned-center\" style=\"flex-basis:33.33%\">\n" . $logo . "\n</div>\n<!-- /wp:column -->";
    $text_col = "<!-- wp:column {\"verticalAlignment\":\"center\",\"width\":\"66.66%\"} -->\n<div class=\"wp-block-column is-vertically-aligned-center\" style=\"flex-basis:66.66%\">\n" . $text . "\n</div>\n<!-- /wp:column -->";

    $about = "<!-- wp:group {\"className\":\"content-area cool-grey my-4\",\"layout\":{\"type\":\"default\"}} -->\n"
        . "<div class=\"wp-block-group content-area cool-grey my-4\">\n"
        . "<!-- wp:group {\"className\":\"container\",\"layout\":{\"type\":\"default\"}} -->\n"
        . "<div class=\"wp-block-group container\">\n"
        . "<!-- wp:columns {\"verticalAlignment\":\"center\"} -->\n"
        . "<div class=\"wp-block-columns are-vertically-aligned-center\">\n"
        . $logo_col . "\n\n" . $text_col . "\n"
        . "</div>\n<!-- /wp:columns -->\n"
        . "</div>\n<!-- /wp:group -->\n"
        . "</div>\n<!-- /wp:group -->";

    return $hero . "\n\n" . $card . "\n\n" . $about . "\n\n" . $news;
}

/**
 * An editable core/heading block. $level 2 is the default (no "level" attribute, matching core).
 */
function well_blocks_heading($text, $level = 2, $class = '') {
    $attrs = array();
    if (2 !== $level) {
        $attrs['level'] = $level;
    }
    if ('' !== $class) {
        $attrs['className'] = $class;
    }
    $json = empty($attrs) ? '' : ' ' . wp_json_encode($attrs);
    $cls  = 'wp-block-heading' . ('' !== $class ? ' ' . $class : '');
    return "<!-- wp:heading{$json} -->\n<h{$level} class=\"{$cls}\">{$text}</h{$level}>\n<!-- /wp:heading -->";
}

/**
 * An editable core/paragraph block. $html may contain inline markup (strong/em/code/a).
 */
function well_blocks_paragraph($html, $class = '') {
    if ('' !== $class) {
        return "<!-- wp:paragraph {\"className\":\"{$class}\"} -->\n<p class=\"{$class}\">{$html}</p>\n<!-- /wp:paragraph -->";
    }
    return "<!-- wp:paragraph -->\n<p>{$html}</p>\n<!-- /wp:paragraph -->";
}

/**
 * The Sampling Data Upload Guide body. The narrative headings and paragraphs are editable blocks; the
 * pieces that are wired to JavaScript or must stay byte-exact (the reference lists/tables that
 * js/sampling-check.js refreshes by id, the SVG diagrams, the screenshot figures, the alert boxes and
 * the styled download/Borealis buttons) are kept as core/html; the live checker is the
 * [well_sampling_checker] shortcode. Everything renders inside .container.sampling-guide (the template),
 * which the guide's CSS is scoped to.
 */
function well_blocks_sampling() {
    $img = '/wp-content/themes/well/img/sampling';
    $b   = array();

    // --- Intro: how the pipeline works (prose) + pipeline diagram (SVG, preserved) ---
    $intro_prose = well_blocks_heading('How your data reaches the dashboard')
        . "\n\n" . well_blocks_paragraph('When you have sampling results from the Ancaster Creek watershed, you share them as a spreadsheet saved as a <strong>CSV file</strong> and upload it to our <strong>Borealis</strong> data repository. From there, nobody has to copy anything by hand:')
        . "\n\n" . well_blocks_html('<ol><li>You upload your CSV to the <em>Ancaster Watershed Sampling Uploads</em> dataset on Borealis.</li><li>Once a week, WELL picks up any new files from that dataset.</li><li>Each file is <strong>checked against the standard format</strong>, and if it passes, every reading in it is imported for you.</li><li>Your readings show up on the dashboard\'s <strong>Ancaster Watershed</strong> tab, where anyone can view and download them.</li></ol>')
        . "\n\n" . well_blocks_paragraph('If a file doesn\'t match the format, <strong>none of it is imported</strong> and the WELL team gets a heads-up to look into it. Your data is never half-imported, so it really is worth getting the format right the first time. That is what the rest of this page is for.');

    $pipeline_svg = well_blocks_html(
        '<figure class="sampling-pipeline" aria-hidden="false">'
        . '<svg viewBox="0 0 220 300" width="100%" height="auto" role="img" aria-labelledby="pipe-title pipe-desc">'
        . '<title id="pipe-title">The sampling data pipeline</title>'
        . '<desc id="pipe-desc">Your CSV goes to Borealis, is downloaded and checked weekly, then imported into the dashboard.</desc>'
        . '<g font-family="Poppins, sans-serif" font-size="12" text-anchor="middle">'
        . '<rect x="20" y="10" width="180" height="46" rx="8" fill="#7a003c"></rect>'
        . '<text x="110" y="31" fill="#fff">Your CSV file</text>'
        . '<text x="110" y="47" fill="#fdbf57" font-size="10">(from the template)</text>'
        . '<line x1="110" y1="56" x2="110" y2="78" stroke="#495965" stroke-width="2" marker-end="url(#arrow)"></line>'
        . '<rect x="20" y="80" width="180" height="46" rx="8" fill="#fff" stroke="#7a003c" stroke-width="2"></rect>'
        . '<text x="110" y="101" fill="#7a003c">Upload to Borealis</text>'
        . '<text x="110" y="117" fill="#495965" font-size="10">Sampling Uploads dataset</text>'
        . '<line x1="110" y1="126" x2="110" y2="148" stroke="#495965" stroke-width="2" marker-end="url(#arrow)"></line>'
        . '<rect x="20" y="150" width="180" height="46" rx="8" fill="#fff" stroke="#7a003c" stroke-width="2"></rect>'
        . '<text x="110" y="171" fill="#7a003c">Weekly download</text>'
        . '<text x="110" y="187" fill="#495965" font-size="10">checked &amp; validated</text>'
        . '<line x1="110" y1="196" x2="110" y2="218" stroke="#495965" stroke-width="2" marker-end="url(#arrow)"></line>'
        . '<rect x="20" y="220" width="180" height="46" rx="8" fill="#7a003c"></rect>'
        . '<text x="110" y="241" fill="#fff">Dashboard</text>'
        . '<text x="110" y="257" fill="#fdbf57" font-size="10">Ancaster Watershed tab</text>'
        . '</g><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">'
        . '<path d="M0,0 L8,4 L0,8 Z" fill="#495965"></path></marker></defs></svg>'
        . '<figcaption>How a sampling file travels from your computer to the dashboard.</figcaption></figure>'
    );

    $b[] = "<!-- wp:columns -->\n<div class=\"wp-block-columns\">\n"
        . "<!-- wp:column {\"width\":\"66.66%\"} -->\n<div class=\"wp-block-column\" style=\"flex-basis:66.66%\">\n" . $intro_prose . "\n</div>\n<!-- /wp:column -->\n\n"
        . "<!-- wp:column {\"width\":\"33.33%\"} -->\n<div class=\"wp-block-column\" style=\"flex-basis:33.33%\">\n" . $pipeline_svg . "\n</div>\n<!-- /wp:column -->\n"
        . "</div>\n<!-- /wp:columns -->";

    $b[] = well_blocks_html('<hr class="my-5">');
    $b[] = well_blocks_heading('Step by step');

    // --- Step 1 ---
    $step1 = well_blocks_html('<h3><span class="sampling-step__num">1</span> Download the template</h3>')
        . "\n\n" . well_blocks_paragraph('The easiest way to start is from the blank template. It already has the column headings in the right order, plus a few example rows to show you the idea:')
        . "\n\n" . well_blocks_html('<p><a class="btn btn-primary" style="background-color:#fdbf57;color:#000;border-color:#fdbf57;" href="https://welldash.mcmaster.ca/api/sampling-template">Download the CSV template</a></p>')
        . "\n\n" . well_blocks_paragraph('Open it in Excel, Google Sheets or Numbers, whatever you normally use. Leave the heading row exactly as it is.', 'text-muted')
        . "\n\n" . well_blocks_html('<div class="alert-box alert-box--info"><strong>Seeing <code>#####</code> where a date should be?</strong> That is just Excel saying the column is too narrow to show the whole date, not a sign that anything is wrong. Double-click the line between the column letters (or drag it wider) and the date comes right back. The one thing to check is that your dates read as <code>YYYY-MM-DD</code>, for example <code>2026-05-06</code>, when the column is wide enough to see them.</div>')
        . "\n\n" . well_blocks_html('<figure class="sampling-figure"><img src="' . $img . '/sampling-excel-hash.webp" width="1200" height="207" loading="lazy" decoding="async" alt="A spreadsheet with a date column too narrow to read, showing #####, next to the same column widened to show 2026-05-06."><figcaption>Left: a narrow column hides the date behind <code>#####</code>. Right: widen the column and the date is there, in <code>YYYY-MM-DD</code> form.</figcaption></figure>');
    $b[] = "<!-- wp:group {\"className\":\"sampling-step\",\"layout\":{\"type\":\"default\"}} -->\n<div class=\"wp-block-group sampling-step\">\n" . $step1 . "\n</div>\n<!-- /wp:group -->";

    // --- Step 2 ---
    $step2 = well_blocks_html('<h3><span class="sampling-step__num">2</span> Fill in your readings</h3>')
        . "\n\n" . well_blocks_paragraph('The one rule to remember: <strong>one reading per row</strong>. If you measured nine things at a site on a single visit, that is nine rows, one for each parameter. Here is what goes in each column:')
        . "\n\n" . well_blocks_heading('Required in every row', 4, 'h5 mt-4')
        . "\n\n" . well_blocks_html('<ul class="sampling-cols" id="required-columns"><li><code>date</code>: the sampling date as <code>YYYY-MM-DD</code>, for example <code>2026-05-06</code>.</li><li><code>site</code>: one of the sites in the table below.</li><li><code>parameter</code>: one of the parameters in the table below.</li><li><code>value</code>: a plain number, for example <code>1295</code> or <code>0.015</code>.</li><li><code>unit</code>: the parameter\'s unit, exactly as listed below.</li></ul>')
        . "\n\n" . well_blocks_heading('Optional (fill in if you have them)', 4, 'h5 mt-4')
        . "\n\n" . well_blocks_html('<ul class="sampling-cols" id="optional-columns"><li><code>time</code>: the time of sampling in 24-hour <code>HH:MM</code>, for example <code>14:05</code>, in local Hamilton time.</li><li><code>creek</code>: the creek\'s name. We use it to double-check you picked the right site.</li><li><code>below_detection</code>: <code>true</code> if the value was below the detection limit.</li><li><code>qc_flag</code>: <code>ok</code>, <code>suspect</code> or <code>rejected</code>.</li><li><code>sampler</code>, <code>method</code>, <code>notes</code>: anything else worth keeping with the reading.</li></ul>')
        . "\n\n" . well_blocks_html('<figure class="sampling-figure"><img src="' . $img . '/sampling-template-spreadsheet.webp" width="1200" height="259" loading="lazy" decoding="async" alt="The template open in a spreadsheet: a header row of column names and example rows, one reading per row, with dates in YYYY-MM-DD form."><figcaption>A filled-in template, one reading per row. (This is an example; your sites and parameters will differ.)</figcaption></figure>')
        . "\n\n" . well_blocks_html('<div class="alert-box alert-box--info"><strong>A few things that trip people up:</strong><ul class="mb-0"><li><strong>Dates must be <code>YYYY-MM-DD</code>.</strong> Something like <code>05/06/2026</code> is turned away, because it could mean 5 June or 6 May and the system won\'t guess.</li><li><strong>Values are plain numbers.</strong> No commas for thousands, and no units in the cell. The unit goes in the <code>unit</code> column.</li><li><strong>Below the detection limit?</strong> Write the limit with a <code>&lt;</code> in front, like <code>&lt;0.01</code>.</li><li><strong>Didn\'t measure something?</strong> Just leave that row out, or leave <code>value</code> empty. Please don\'t write <code>0</code> to mean "not measured".</li><li><strong>Save as CSV UTF-8.</strong> In Excel that is <em>File &gt; Save As &gt; CSV UTF-8 (Comma delimited)</em>.</li></ul></div>')
        . "\n\n" . well_blocks_heading('Sites', 4, 'h5 mt-4')
        . "\n\n" . well_blocks_paragraph('You can use the site\'s name, its number, or both (for example <code>Falkirk Forest</code>, <code>1</code>, or <code>#1 Falkirk Forest</code>). Spelling matters; capitals and extra spaces don\'t.')
        . "\n\n" . well_blocks_html('<div class="table-responsive"><table class="table table-sm sampling-ref" id="sites-table"><thead><tr><th>Site number</th><th>Name</th><th>Creek</th></tr></thead><tbody><tr><td>1</td><td>Falkirk Forest</td><td>Tiffany Creek</td></tr><tr><td>2</td><td>Maple Lane Pk</td><td>Ancaster Creek</td></tr><tr><td>3</td><td>Jerseyville Rd</td><td>Sulphur Creek</td></tr><tr><td>4</td><td>Sulphur Springs</td><td>Sulphur Creek</td></tr><tr><td>5</td><td>Sherman Falls</td><td>Ancaster Creek</td></tr><tr><td>6</td><td>Tiffany Falls</td><td>Tiffany Creek</td></tr><tr><td>8</td><td>Osler Dr</td><td>Coldwater Creek</td></tr><tr><td>9</td><td>McMaster Lot P</td><td>Coldwater Creek</td></tr><tr><td>10</td><td>Cootes Dr</td><td>Spencer\'s Creek</td></tr></tbody></table></div>')
        . "\n\n" . well_blocks_paragraph('There is no site 7. A site that isn\'t on this list has to be added to the dashboard first, so please <a href="/about/">get in touch with the WELL team</a> before uploading data for a new site.', 'text-muted')
        . "\n\n" . well_blocks_heading('Parameters and units', 4, 'h5 mt-4')
        . "\n\n" . well_blocks_paragraph('Each value needs to be in the unit shown here. A different unit is treated as an error (we don\'t convert it for you), so do the conversion yourself before you upload.')
        . "\n\n" . well_blocks_html('<div class="table-responsive"><table class="table table-sm sampling-ref" id="parameters-table"><thead><tr><th>Parameter</th><th>Unit</th><th>Also accepted as</th></tr></thead><tbody><tr><td>E. coli</td><td>CFU/100 mL</td><td>E.coli, E coli</td></tr><tr><td>Total coliform</td><td>CFU/100 mL</td><td></td></tr><tr><td>Turbidity</td><td>NTU</td><td></td></tr><tr><td>pH</td><td>pH units (or pH)</td><td></td></tr><tr><td>Conductivity</td><td>µS/cm</td><td>Specific conductance</td></tr><tr><td>Chloride</td><td>mg/L</td><td></td></tr><tr><td>Total phosphorus</td><td>µg/L</td><td>TP</td></tr><tr><td>Soluble reactive phosphorus</td><td>µg/L</td><td>SRP</td></tr><tr><td>Total nitrogen</td><td>mg/L</td><td>TN</td></tr><tr><td>Nitrate nitrogen</td><td>mg/L</td><td>Nitrate-N</td></tr><tr><td>Ammonia nitrogen</td><td>mg/L</td><td>Ammonia-N</td></tr></tbody></table></div>');
    $b[] = "<!-- wp:group {\"className\":\"sampling-step\",\"layout\":{\"type\":\"default\"}} -->\n<div class=\"wp-block-group sampling-step\">\n" . $step2 . "\n</div>\n<!-- /wp:group -->";

    // --- Step 3 ---
    $step3 = well_blocks_html('<h3><span class="sampling-step__num">3</span> Check your file (right here)</h3>')
        . "\n\n" . well_blocks_paragraph('Before you upload anything, drop your file into the <a href="#sampling-checker">Check my CSV format</a> tool at the bottom of this page. It tells you straight away whether the file will import, and if it won\'t, it points you to exactly what to fix.')
        . "\n\n" . well_blocks_html('<figure class="sampling-figure"><img src="' . $img . '/sampling-checker-pass.webp" width="1100" height="716" loading="lazy" decoding="async" alt="The Check my CSV format tool showing a green \'Looks good\' banner after checking a valid file."><figcaption>When a file is good to go, you get a green "Looks good" and a quick count of what it holds.</figcaption></figure>')
        . "\n\n" . well_blocks_html('<figure class="sampling-figure"><img src="' . $img . '/sampling-checker-fix.webp" width="1100" height="946" loading="lazy" decoding="async" alt="The Check my CSV format tool showing a red \'Not ready yet\' banner and a table listing each problem with its row, column and what to fix."><figcaption>When something is off, it lists each problem with its row, column and a plain-English note on what to change.</figcaption></figure>');
    $b[] = "<!-- wp:group {\"className\":\"sampling-step\",\"layout\":{\"type\":\"default\"}} -->\n<div class=\"wp-block-group sampling-step\">\n" . $step3 . "\n</div>\n<!-- /wp:group -->";

    // --- Step 4 ---
    $step4 = well_blocks_html('<h3><span class="sampling-step__num">4</span> Upload to Borealis</h3>')
        . "\n\n" . well_blocks_paragraph('Sign in to Borealis and open the <strong>Ancaster Watershed Sampling Uploads</strong> dataset, then add your CSV as a new file.')
        . "\n\n" . well_blocks_html('<p><a class="btn btn-primary" style="background-color:#fdbf57;color:#000;border-color:#fdbf57;" href="https://borealisdata.ca/dataverse/WELL" target="_blank" rel="noopener noreferrer">Open WELL on Borealis</a></p>')
        . "\n\n" . well_blocks_paragraph('If you don\'t have access to the dataset yet, just ask the WELL team to add you.', 'text-muted')
        . "\n\n" . well_blocks_html('<figure class="sampling-figure" aria-hidden="false"><svg viewBox="0 0 640 150" width="100%" height="auto" role="img" aria-labelledby="bor-title bor-desc"><title id="bor-title">Uploading a file on Borealis, in three steps</title><desc id="bor-desc">Open the Sampling Uploads dataset, use Edit then Upload Files to add your CSV, then save the changes.</desc><g font-family="Poppins, sans-serif" font-size="13" text-anchor="middle"><rect x="10" y="30" width="180" height="70" rx="10" fill="#fff" stroke="#7a003c" stroke-width="2"></rect><text x="100" y="60" fill="#7a003c" font-weight="600">1. Open the dataset</text><text x="100" y="80" fill="#495965" font-size="11">Sampling Uploads</text><line x1="190" y1="65" x2="228" y2="65" stroke="#495965" stroke-width="2" marker-end="url(#bor-arrow)"></line><rect x="230" y="30" width="180" height="70" rx="10" fill="#fff" stroke="#7a003c" stroke-width="2"></rect><text x="320" y="60" fill="#7a003c" font-weight="600">2. Add your CSV</text><text x="320" y="80" fill="#495965" font-size="11">Edit &gt; Upload Files</text><line x1="410" y1="65" x2="448" y2="65" stroke="#495965" stroke-width="2" marker-end="url(#bor-arrow)"></line><rect x="450" y="30" width="180" height="70" rx="10" fill="#7a003c"></rect><text x="540" y="60" fill="#fff" font-weight="600">3. Save</text><text x="540" y="80" fill="#fdbf57" font-size="11">then publish (step 5)</text></g><defs><marker id="bor-arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#495965"></path></marker></defs></svg><figcaption>The three steps on Borealis. This is an illustration, not a Borealis screenshot; the buttons may be labelled slightly differently depending on your role.</figcaption></figure>');
    $b[] = "<!-- wp:group {\"className\":\"sampling-step\",\"layout\":{\"type\":\"default\"}} -->\n<div class=\"wp-block-group sampling-step\">\n" . $step4 . "\n</div>\n<!-- /wp:group -->";

    // --- Step 5 ---
    $step5 = well_blocks_html('<h3><span class="sampling-step__num">5</span> Publish, and confirm it worked</h3>')
        . "\n\n" . well_blocks_paragraph('On Borealis, a file you\'ve just added is only picked up once the dataset version is <strong>published</strong>. Depending on your role, you can either publish it yourself or a dataset curator publishes it for you. If you aren\'t sure which, just let the WELL team know you\'ve uploaded a file.')
        . "\n\n" . well_blocks_paragraph('After the next weekly import, your readings will appear on the dashboard\'s <strong>Ancaster Watershed</strong> tab. If something was off with the format, the file is set aside (nothing from it is imported) and the WELL team is told exactly what the problems were, so your upload is never quietly lost. You fix it, upload a corrected file, and it goes in on the following run.');
    $b[] = "<!-- wp:group {\"className\":\"sampling-step\",\"layout\":{\"type\":\"default\"}} -->\n<div class=\"wp-block-group sampling-step\">\n" . $step5 . "\n</div>\n<!-- /wp:group -->";

    $b[] = well_blocks_html('<hr class="my-5">');

    // --- Common mistakes ---
    $b[] = well_blocks_heading('Common reasons a file is turned away');
    $b[] = well_blocks_paragraph('The checker and the weekly import both refuse a file for any of these, and each one tells you the exact row and column so you can go straight to it:');
    $b[] = well_blocks_html('<ul class="sampling-mistakes"><li>A required column (<code>date</code>, <code>site</code>, <code>parameter</code>, <code>value</code>, <code>unit</code>) is missing or duplicated, or a heading is mis-typed.</li><li>A <code>date</code> that isn\'t <code>YYYY-MM-DD</code>, or an impossible one like <code>2026-02-30</code>.</li><li>A <code>time</code> that isn\'t a 24-hour <code>HH:MM</code>.</li><li>A <code>site</code> that isn\'t one of the known sites (a typo, or a site not added yet).</li><li>A <code>parameter</code> that isn\'t on the list, or a <code>unit</code> that doesn\'t match the parameter.</li><li>A <code>value</code> that isn\'t a plain number, or is impossible (a negative concentration, or a pH above 14).</li><li>The same reading twice (same site, parameter, date and time). Report one value per reading; if you have replicates, average them and say so in <code>notes</code>.</li><li>The file saved as something other than CSV UTF-8, or a file with no readings in it at all.</li></ul>');

    $b[] = well_blocks_html('<hr class="my-5">');

    // --- The live checker (developer-owned shortcode; includes its own heading and intro) ---
    $b[] = well_blocks_shortcode('well_sampling_checker');

    return implode("\n\n", $b);
}
