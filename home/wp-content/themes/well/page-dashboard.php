<?php
// This is the "Dashboard" page template for the WELL WordPress theme.
// It displays an embedded dashboard, links to archived datasets, and related resources.

get_header();
?>

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
                <?php $dashboard_url = getenv('DASHBOARD_URL') ?: 'http://localhost:8081'; ?>
                <a class="btn my-0 focusable btn-secondary" href="<?php echo esc_url($dashboard_url); ?>" target="_blank">Dashboard</a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</banner>
<?php $dashboard_url = isset($dashboard_url) ? $dashboard_url : (getenv('DASHBOARD_URL') ?: 'http://localhost:8081'); ?>
<iframe src="<?php echo esc_url($dashboard_url); ?>/" style="width:100%;height:100vh;border:none;"></iframe>

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
                  sizes="(max-width: 480px) 150px, (max-width: 800px) 270px, 300px"
                  src="/wp-content/uploads/2025/09/borealislogo.jpg"
                  class="img-fluid d-block mx-auto"
                  style="max-width: 200px; width: 100%; height: auto;"
                />            
              </figure>
            </div>
          </div>
          <!-- Center text -->
          <div class="col-md-4 pl-md-4 pr-md-4 my-3 align-self-center">
            <h2>Archived Datasets</h2>
            <p>For premade datasets uploaded monthly, visit the <strong>WELL</strong> data repositories:</p>
            <p style="text-align: left;">
              <a class="btn btn-primary btn-lg text-center" style="background-color: #fdbf57; color: black; border-color: #FDBF57;" href="https://borealisdata.ca/dataverse/WELL" target="_blank" rel="noopener noreferrer">Borealis</a>
              <a class="btn btn-primary btn-lg text-center" style="background-color: #fdbf57; color: black; border-color: #FDBF57;" href="https://mcmasteru365.sharepoint.com/sites/WELL" target="_blank" rel="noopener noreferrer">Sharepoint</a>
            </p>
          </div>
          <!-- Right image -->
          <div class="col-md-4 pl-md-4 my-3 align-self-center">
            <div class="text-center">
              <figure class="mw-100">
                <img 
                  alt="SharePoint Logo"
                  srcset="
                      /wp-content/uploads/2025/09/sharepointlogo.png 414w,
                      /wp-content/uploads/2025/09/sharepointlogo.png 720w,
                      /wp-content/uploads/2025/09/sharepointlogo.png 1080w,
                      /wp-content/uploads/2025/09/sharepointlogo.png 1600w
                  "
                  sizes="(max-width: 480px) 150px, (max-width: 800px) 270px, 300px"
                  src="/wp-content/uploads/2025/09/sharepointlogo.png"
                  class="img-fluid d-block mx-auto"
                />            
              </figure>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<?php
get_footer();
?>
