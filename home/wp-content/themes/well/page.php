<?php
// The template for a page written in wp-admin (Pages), such as Contact: its title and its content.
// The About, Dashboard and News pages have their own templates (page-about.php and so on).
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

get_header();

while (have_posts()) :
  the_post();
  ?>
<header class="section-intro py-4">
  <div class="container">
    <div class="row align-items-center">
      <div class="col-sm-12">
        <h1 class="mb-4"><?php the_title(); ?></h1>
      </div>
    </div>
  </div>
</header>

<main id="site-content">
  <section class="section-padding">
    <div class="container">
      <div class="entry-content">
        <?php
        if ('' !== trim(get_the_content())) {
          the_content();
        } else {
          // A published page nobody has written yet. Point to where the team's contacts are.
          echo '<p>This page has no content yet. The WELL team\'s email addresses are on the <a href="' . esc_url(home_url('/about/')) . '">About page</a>.</p>';
        }
        ?>
      </div>
    </div>
  </section>
</main>
  <?php
endwhile;

get_footer();
