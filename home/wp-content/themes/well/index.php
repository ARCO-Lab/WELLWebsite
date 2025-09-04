<?php
// Main template file for the WELL WordPress theme.
// Loads the header, homepage sections, and footer in order.

get_header();

get_template_part('sections/hero');

get_template_part('sections/dashboard');

get_template_part('sections/about');

get_template_part('sections/news');

get_footer();
?>