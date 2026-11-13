<?php
// The home page of the WELL WordPress theme.
// Loads the header, homepage sections, and footer in order.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

get_header();

// The "Skip to main content" link in header.php jumps to #site-content.
echo '<main id="site-content">';

get_template_part('sections/hero');

get_template_part('sections/dashboard');

get_template_part('sections/about');

get_template_part('sections/news');

echo '</main>';

get_footer();
?>