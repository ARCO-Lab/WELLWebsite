<?php
// The home page of the WELL WordPress theme.
//
// When the site's front page is a static Page with block content (seeded by
// tools/migrate-pages-to-blocks.php), that content is rendered through the_content(), so the home page
// is editable in wp-admin. The hero carousel, dashboard card and "Latest News" strip stay
// developer-owned code and appear in the content as shortcodes (see inc/shortcodes.php); only the
// "About Us" blurb is editable blocks.
//
// Fallback: if the front page is "Your latest posts", or a static page with no content yet, the
// original sections render in order, so the home page is never blank.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

get_header();

// The "Skip to main content" link in header.php jumps to #site-content.
echo '<main id="site-content">';

$front = get_queried_object();
if ($front instanceof WP_Post && 'page' === $front->post_type
    && '' !== trim(wp_strip_all_tags($front->post_content))) {
  // Static front page with block content: render it (the loop sets up the post for the_content()).
  while (have_posts()) :
    the_post();
    the_content();
  endwhile;
} else {
  // Not a content page (or not migrated yet): render the original homepage sections in order.
  get_template_part('sections/hero');
  get_template_part('sections/dashboard');
  get_template_part('sections/about');
  get_template_part('sections/news');
}

echo '</main>';

get_footer();
?>
