<?php
// This section renders the "Latest News" carousel for the WELL WordPress theme.
// It queries and displays the latest 6 blog posts as cards in a Flickity carousel.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.
?>
<section class="dynamic-content post white my-5">
  <div class="container">
    <h2 class="text-left">Latest News</h2>
    <div class="row row-eq-height justify-content-start">
      <div class="col-md-12 col-sm-10 col-xs-10 mx-auto">
        <div class="flickity-carousel multi-carousel multi-carousel-eq-height" data-flickity='{ "cellAlign": "left", "contain": true, "groupCells": "true" }'>
          <?php
          // The latest 6 published posts (well_news_query() in functions.php explains what counts as news)
          $news_query = well_news_query(6);
          if ($news_query->have_posts()) :
            while ($news_query->have_posts()) : $news_query->the_post(); ?>
              <div class="col-lg-4">
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
                        </div>
                        <div class="card-text mb-0">
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
      </div>
    </div>
    <div class="text-left mt-4">
      <a class="btn btn-info btn-arrow" href="<?php echo esc_url(home_url('/news/')); ?>">
        More News
      </a>
    </div>
  </div>
</section>