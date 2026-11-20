<?php
// This is the "Dashboard" page template for the WELL WordPress theme.
//
// The page's editable prose (the "Archived Datasets" section with the Borealis and SharePoint links)
// now lives in the page's block content and is rendered by the_content() below. The live dashboard
// embed stays developer-owned code and is placed in the content as the [well_dashboard_embed]
// shortcode (see sections/dashboard-embed.php and inc/shortcodes.php).
//
// Fallback: if the page has no block content yet (not migrated — see
// tools/migrate-pages-to-blocks.php), the original embed and "Archived Datasets" section render, so
// the page is never blank.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

get_header();
?>

<main id="site-content">
<?php
while (have_posts()) :
  the_post();

  if ('' !== trim(wp_strip_all_tags(get_the_content()))) {
    the_content();
  } else {
    // Not migrated yet: render the original embed and section so the page is never blank.
    get_template_part('sections/dashboard-embed');
    ?>
<section class="content-area cool-grey my-4">
  <div class="container">
    <div class="row">
      <div class="col-12">
        <div class="row">
          <!-- Left image -->
          <div class="col-md-4 pr-md-4 my-3 align-self-center">
            <div class="text-center">
              <figure class="mw-100">
                <img
                  alt="Borealis Logo"
                  srcset="
                      /wp-content/uploads/2025/09/borealislogo.jpg 414w,
                      /wp-content/uploads/2025/09/borealislogo.jpg 720w,
                      /wp-content/uploads/2025/09/borealislogo.jpg 1080w,
                      /wp-content/uploads/2025/09/borealislogo.jpg 1600w
                  "
                  sizes="(max-width: 480px) 140px, (max-width: 800px) 220px, 280px"
                  src="/wp-content/uploads/2025/09/borealislogo.jpg"
                  class="img-fluid d-block mx-auto"
                  style="max-width: 200px; width: 100%; height: auto;"
                  loading="lazy"
                  decoding="async"
                />
              </figure>
            </div>
          </div>
          <!-- Center text -->
          <div class="col-md-4 pl-md-4 pr-md-4 my-3 align-self-center">
            <h2>Archived Datasets</h2>
            <p>For premade datasets uploaded monthly, visit the <strong>WELL</strong> data repositories:</p>
            <p style="text-align: left;">
              <a class="btn btn-primary btn-lg text-center d-inline-block mb-2 mr-sm-2" style="background-color: #fdbf57; color: black; border-color: #FDBF57;" href="https://borealisdata.ca/dataverse/WELL" target="_blank" rel="noopener noreferrer">Borealis</a>
              <a class="btn btn-primary btn-lg text-center d-inline-block mb-2" style="background-color: #fdbf57; color: black; border-color: #FDBF57;" href="https://mcmasteru365.sharepoint.com/sites/WELL" target="_blank" rel="noopener noreferrer">Sharepoint</a>
            </p>
          </div>
          <!-- Right image -->
          <div class="col-md-4 pl-md-4 my-3 align-self-center">
            <div class="text-center">
              <figure class="mw-100">
                <?php well_media_img('logo-sharepoint', array(280, 560, 840), array(840, 560), array(
                  'alt'     => 'SharePoint Logo',
                  'sizes'   => '(max-width: 480px) 140px, (max-width: 800px) 220px, 280px',
                  'class'   => 'img-fluid d-block mx-auto',
                  'loading' => 'lazy',
                )); ?>
              </figure>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>
    <?php
  }
endwhile;
?>
</main>

<?php
get_footer();
?>
