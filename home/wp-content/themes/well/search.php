<?php
// The search results page of the WELL WordPress theme (/?s=...): the posts and pages that match.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

get_header();
?>
<header class="section-intro py-4">
  <div class="container">
    <div class="row align-items-center">
      <div class="col-sm-12">
        <h1 class="mb-4">Search results for &ldquo;<?php echo esc_html(get_search_query(false)); ?>&rdquo;</h1>
      </div>
    </div>
  </div>
</header>

<main id="site-content">
  <div class="container">
    <form role="search" method="get" action="<?php echo esc_url(home_url('/')); ?>" class="form-inline mt-4">
      <label class="sr-only" for="well-search-again">Search this site</label>
      <input type="search" id="well-search-again" name="s" class="form-control mr-2 mb-2" value="<?php echo esc_attr(get_search_query(false)); ?>">
      <button type="submit" class="btn btn-primary mb-2">Search</button>
    </form>
  </div>
  <?php get_template_part('sections/post-list', null, array('empty' => 'Nothing on this site matches your search. Try other words, or go to the News page.')); ?>
</main>
<?php
get_footer();
