<?php
// The News listing: the live, paginated grid of news-post cards with page links under them.
//
// This is BOTH the body of the News page (page-news.php) and the render of the well/news-list dynamic
// block (inc/blocks.php / the [well_news_list] shortcode). Keeping the listing in one partial means the
// News page editor PREVIEWS the real listing (via the block's ServerSideRender) instead of opening to a
// blank canvas, while the front-end output is the same markup it always was.
//
// The listing is a live query (the latest published posts, newest first, nine per page) so it stays
// developer-owned code rather than editable blocks. It uses a paged query from the current URL
// (get_query_var), exactly as the News template used to, so /news/page/2/ and so on keep working whether
// this partial is reached through the_content() (migrated page) or included directly (fallback).
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

// 9 published posts per page, newest first (well_news_query() in functions.php explains what counts as
// news). Later pages are /news/page/2/ and so on.
$news_page = max(1, (int) get_query_var('paged'), (int) get_query_var('page'));
if ( isset($GLOBALS['well_news_list_query']) && $GLOBALS['well_news_list_query'] instanceof WP_Query ) {
  // The News template (page-news.php) already built this query for its 404 bounds check; reuse it so
  // the posts are fetched once per request. rewind_posts() makes it safe to loop here however it was
  // reached (directly, or through the well/news-list block in the_content()).
  $news_query = $GLOBALS['well_news_list_query'];
  $news_query->rewind_posts();
} else {
  // Standalone contexts that have no template to build the query first: the editor's block preview and
  // the [well_news_list] shortcode. Build it here so the partial is self-contained.
  $news_query = well_news_query(9, array(), $news_page);
}
$news_pages = (int) $news_query->max_num_pages;
?>
  <section class="section-padding">
    <div class="container">
      <h2 class="sr-only">News Listing</h2>
      <div class="row row-eq-height">
        <?php
        if ($news_query->have_posts()) :
          while ($news_query->have_posts()) : $news_query->the_post(); ?>
            <div class="col-lg-4 col-md-6">
              <div class="card card-shadow border-top-0">
                <div class="card-main border-top h-100">
                  <div class="card border-0 no-shadow card-hover">
                    <?php well_news_card_image(); ?>
                    <div class="card-body pb-0">
                      <h3 class="card-title">
                        <a href="<?php the_permalink(); ?>">
                          <?php the_title(); ?>
                        </a>
                      </h3>
                      <div class="card-text mb-0">
                        <p class="card-subtitle mt-2 text-maroon">News</p>
                        <p><?php echo esc_html(wp_trim_words(get_the_excerpt(), 20)); ?></p>
                      </div>
                    </div>
                    <div class="card-footer border-top-0 px-4 py-3">
                      <p class="small m-0"><strong><?php echo get_the_date(); ?></strong></p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
        <?php
          endwhile;
          wp_reset_postdata();
        else :
          echo '<p>No news articles found.</p>';
        endif;
        ?>
      </div>
      <?php
      // Page links under the cards, once there are more than 9 posts. Bootstrap's .pagination
      // styles them; the current page is a <span aria-current="page">, not a link.
      $news_base  = trailingslashit(get_permalink());
      $news_links = paginate_links(array(
        'base'      => $news_base . 'page/%#%/',
        'format'    => '',
        'current'   => $news_page,
        'total'     => $news_pages,
        'type'      => 'array',
        'prev_text' => 'Newer',
        'next_text' => 'Older',
      ));
      if (!empty($news_links)) : ?>
        <nav class="mt-4" aria-label="News pages">
          <ul class="pagination justify-content-center flex-wrap">
            <?php foreach ($news_links as $link) : ?>
              <li class="page-item<?php echo false !== strpos($link, 'current') ? ' active' : ''; ?>">
                <?php
                // Page 1 is the News page itself, not /news/page/1/.
                echo str_replace(
                  array('page-numbers', '"' . $news_base . 'page/1/"'),
                  array('page-numbers page-link', '"' . $news_base . '"'),
                  $link
                ); ?>
              </li>
            <?php endforeach; ?>
          </ul>
        </nav>
      <?php endif; ?>
    </div>
  </section>
