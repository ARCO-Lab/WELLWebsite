<?php
// This is the "Dashboard" page template for the WELL WordPress theme.
// It displays an embedded dashboard, links to archived datasets, and related resources.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

get_header();
?>

<main id="site-content">
<banner>
  <div class="banner-carousel" data-flickity='{ "cellAlign": "left", "contain": true, "adaptiveHeight": true, "pageDots": false, "autoPlay": 15000, "wrapAround": true }'>
    <div class="carousel-cell d-flex cool-grey text-black banner-carousel-left flex-column">
      <div class="container-fluid py-4 align-self-center">
        <div class="row">
          <div class="col-12 col-md-10 mx-auto">
            <div class="row mx-auto align-items-center">
              <div class="col-lg-3 text-lg-left py-2">
                <h2 class="banner-title my-0">Handling large data sets?</h2>
              </div>
              <div class="col-lg-6 py-2">
                <p class="banner-text">For smoother experience and quicker downloads, use the full dashboard site.</p>
              </div>
              <div class="col-lg-3 text-lg-right py-2">
                <?php $dashboard_url = getenv('DASHBOARD_URL') ?: 'https://welldash.mcmaster.ca'; ?>
                <a class="btn my-0 focusable btn-secondary" href="<?php echo esc_url($dashboard_url); ?>" target="_blank" rel="noopener noreferrer">Dashboard</a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</banner>
<?php
$dashboard_url = isset($dashboard_url) ? $dashboard_url : (getenv('DASHBOARD_URL') ?: 'https://welldash.mcmaster.ca');
// The dashboard's origin (scheme, host and port), the only one js/dashboard-embed.js exchanges messages with
$dashboard_parts = wp_parse_url($dashboard_url);
$dashboard_origin = isset($dashboard_parts['scheme'], $dashboard_parts['host'])
  ? $dashboard_parts['scheme'] . '://' . $dashboard_parts['host'] . (isset($dashboard_parts['port']) ? ':' . $dashboard_parts['port'] : '')
  : '';
// js/dashboard-embed.js sizes the iframe to the dashboard's content (loaded in the footer, after the iframe)
wp_enqueue_script(
  'well-dashboard-embed',
  get_template_directory_uri() . '/js/dashboard-embed.js',
  array(),
  well_asset_version('/js/dashboard-embed.js'),
  true
);
?>
<style>
  /* Until the dashboard has painted, "Loading the dashboard…" shows through the iframe in a box of the iframe's
     starting height, so the page doesn't jump when it arrives. Once the dashboard reports its height the iframe
     takes that height, and the dashboard scrolls with the page. */
  .well-dashboard-embed { position: relative; background: #f5f5f5; }
  .well-dashboard-embed iframe { position: relative; display: block; width: 100%; height: clamp(560px, 88vh, 1000px); border: 0; }
  .well-dashboard-embed__loading { position: absolute; top: 3rem; left: 0; right: 0; margin: 0; text-align: center; color: #495965; }
  .well-dashboard-embed.is-loaded { background: transparent; }
  .well-dashboard-embed.is-loaded .well-dashboard-embed__loading { display: none; }
</style>
<div class="well-dashboard-embed">
  <p class="well-dashboard-embed__loading" aria-hidden="true">Loading the dashboard…</p>
  <!-- ?embed=1: the dashboard without its own header and footer, sized to its content. Not lazy-loaded: it is the
       page's main content, at the top. "fullscreen" is for the map's full-screen button. -->
  <iframe
    id="well-dashboard-frame"
    src="<?php echo esc_url(rtrim($dashboard_url, '/') . '/?embed=1'); ?>"
    title="WELL data dashboard"
    data-dashboard-origin="<?php echo esc_attr($dashboard_origin); ?>"
    allow="fullscreen"
    referrerpolicy="strict-origin-when-cross-origin"
  ></iframe>
</div>

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
</main>

<?php
get_footer();
?>
