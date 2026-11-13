<?php
// The fallback template of the WELL WordPress theme: WordPress uses it for any list of posts that
// has no template of its own (a category, tag, author or month). The home page is front-page.php.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

get_header();
?>
<header class="section-intro py-4">
  <div class="container">
    <div class="row align-items-center">
      <div class="col-sm-12">
        <h1 class="mb-4"><?php echo esc_html(wp_strip_all_tags(get_the_archive_title())); ?></h1>
      </div>
    </div>
  </div>
</header>

<main id="site-content">
  <?php get_template_part('sections/post-list', null, array('empty' => 'There is nothing here yet.')); ?>
</main>
<?php
get_footer();
