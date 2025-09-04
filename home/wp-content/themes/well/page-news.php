<?php
// This is the "News" page template for the WELL WordPress theme.
// It displays a list of recent news posts in a card layout.

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
        $news_query = new WP_Query([
          'post_type' => 'post',
          'posts_per_page' => 9, // Change as needed
        ]);
        if ($news_query->have_posts()) :
          while ($news_query->have_posts()) : $news_query->the_post(); ?>
            <div class="col-lg-4 col-md-6">
              <div class="card card-shadow border-top-0">
                <div class="card-main border-top h-100">
                  <div class="card border-0 no-shadow card-hover">
                    <div class="card-body pb-0">
                      <h3 class="card-title">
                        <a href="<?php the_permalink(); ?>">
                          <?php the_title(); ?>
                        </a>
                      </h3>
                      <div class="card-text mb-0">
                        <p class="card-subtitle mt-2 text-maroon">News</p>
                        <p><?php echo wp_trim_words(get_the_excerpt(), 20); ?></p>
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
  </section>
</main>
<?php
get_footer();
?>