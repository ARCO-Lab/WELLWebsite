<?php
// This is the "News" page template for the WELL WordPress theme.
// It displays a list of recent news posts in a card layout.
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
</main>
<?php
get_footer();
?>