<?php
// The "page not found" page of the WELL WordPress theme, for any address the site does not have.
// WordPress sends it with status 404.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

get_header();
?>
<header class="section-intro py-4">
  <div class="container">
    <div class="row align-items-center">
      <div class="col-sm-12">
        <h1 class="mb-4">Page not found</h1>
      </div>
    </div>
  </div>
</header>

<main id="site-content">
  <section class="section-padding">
    <div class="container">
      <p>There is no page at this address. It may have moved, or the link may be mistyped.</p>
      <ul>
        <li><a href="<?php echo esc_url(home_url('/')); ?>">Home</a></li>
        <li><a href="<?php echo esc_url(home_url('/dashboard/')); ?>">Dashboard</a>: live and historical WELL data</li>
        <li><a href="<?php echo esc_url(home_url('/news/')); ?>">News</a></li>
        <li><a href="<?php echo esc_url(home_url('/about/')); ?>">About</a></li>
      </ul>
    </div>
  </section>
</main>
<?php
get_footer();
