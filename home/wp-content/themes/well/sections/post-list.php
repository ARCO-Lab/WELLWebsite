<?php
// This section lists the posts of the page's main query (search results, a category, a month...)
// as news cards, with page links under them. Used by search.php and index.php.
// $args['empty']: the text shown when nothing matches.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

$empty_text = isset($args['empty']) ? $args['empty'] : 'Nothing found.';
?>
<section class="section-padding">
  <div class="container">
    <?php if (have_posts()) : ?>
      <div class="row row-eq-height">
        <?php while (have_posts()) : the_post(); ?>
          <div class="col-lg-4 col-md-6">
            <div class="card card-shadow border-top-0">
              <div class="card-main border-top h-100">
                <div class="card border-0 no-shadow card-hover">
                  <?php well_news_card_image(); ?>
                  <div class="card-body pb-0">
                    <h2 class="card-title h3">
                      <a href="<?php the_permalink(); ?>"><?php the_title(); ?></a>
                    </h2>
                    <div class="card-text mb-0">
                      <p class="card-subtitle mt-2 text-maroon"><?php echo 'post' === get_post_type() ? 'News' : 'Page'; ?></p>
                      <?php if ('post' === get_post_type()) : ?>
                        <p><?php echo esc_html(wp_trim_words(get_the_excerpt(), 20)); ?></p>
                      <?php endif; ?>
                    </div>
                  </div>
                  <?php if ('post' === get_post_type()) : ?>
                    <div class="card-footer border-top-0 px-4 py-3">
                      <p class="small m-0"><strong><?php echo esc_html(get_the_date()); ?></strong></p>
                    </div>
                  <?php endif; ?>
                </div>
              </div>
            </div>
          </div>
        <?php endwhile; ?>
      </div>
      <?php
      // Page links, styled by Bootstrap's .pagination like the News page's.
      $list_links = paginate_links(array(
        'type'      => 'array',
        'prev_text' => 'Previous',
        'next_text' => 'Next',
      ));
      if (!empty($list_links)) : ?>
        <nav class="mt-4" aria-label="Result pages">
          <ul class="pagination justify-content-center flex-wrap">
            <?php foreach ($list_links as $link) : ?>
              <li class="page-item<?php echo false !== strpos($link, 'current') ? ' active' : ''; ?>">
                <?php echo str_replace('page-numbers', 'page-numbers page-link', $link); ?>
              </li>
            <?php endforeach; ?>
          </ul>
        </nav>
      <?php endif; ?>
    <?php else : ?>
      <p><?php echo esc_html($empty_text); ?></p>
    <?php endif; ?>
  </div>
</section>
