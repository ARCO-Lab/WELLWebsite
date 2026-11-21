<?php
// This is the "News" page template for the WELL WordPress theme.
// It displays a list of recent news posts in a card layout.
//
// The listing itself lives in sections/news-list.php and is placed in the page's block content as the
// well/news-list dynamic block (see inc/blocks.php and tools/page-blocks.php), so the News page editor
// PREVIEWS the real listing instead of opening to a blank canvas. An editor can also write an OPTIONAL
// intro above that block in wp-admin, which renders above the listing via the_content() below.
//
// Fallback: if the page has no block content yet (not migrated — see tools/migrate-pages-to-blocks.php),
// the listing partial is included directly, so the page is never blank and the front end is unchanged.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

// 9 published posts per page, newest first (well_news_query() in functions.php explains what counts
// as news). Later pages are /news/page/2/ and so on. Queried before get_header(), so that a page
// past the last one can still be answered with a 404.
$news_page  = max(1, (int) get_query_var('paged'), (int) get_query_var('page'));
$news_query = well_news_query(9, array(), $news_page);
$news_pages = (int) $news_query->max_num_pages;

if ($news_page > max(1, $news_pages)) {
  // /news/page/N/ beyond the last page (or any page past 1 while there are no posts): not found.
  global $wp_query;
  $wp_query->set_404();
  status_header(404);
  nocache_headers();
  include get_404_template();
  return;
}

get_header();
?>
<nav aria-label="breadcrumb" class="breadcrumb-nav">
  <div class="container">
    <ol class="breadcrumb">
      <li class="breadcrumb-item"><a href="https://sees.mcmaster.ca">Home</a></li>
      <li class="breadcrumb-item"><a href="https://sees.mcmaster.ca/news-events/">News &amp; Events</a></li>
      <li class="breadcrumb-item active">News</li>
    </ol>
  </div>
</nav>

<header class="section-intro py-4">
  <div class="container">
    <div class="row align-items-center">
      <div class="col-sm-12">
        <h1 class="mb-4">News</h1>
      </div>
    </div>
  </div>
</header>

<main id="site-content">
<?php
while (have_posts()) :
  the_post();

  // An empty block-editor paragraph still counts as empty.
  if ('' !== trim(wp_strip_all_tags(get_the_content()))) {
    // Migrated: render the block content (the optional editable intro, then the well/news-list block).
    the_content();
  } else {
    // Not migrated yet: render the listing partial directly so the page is never blank.
    get_template_part('sections/news-list');
  }
endwhile;
?>
</main>
<?php
get_footer();
?>