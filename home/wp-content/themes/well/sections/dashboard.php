<?php
// This section renders the "WELL Dashboard" card for the WELL WordPress theme.
// It provides an overview and preview image of the dashboard, with a link to access it.
?>
<section class="thumbnail-cards white my-5">
  <div class="container">
    <h2 class="text-center">The WELL Dashboard</h2>
    <div class="row row-eq-height justify-content-center">
      <div class="col-lg-12">
        <div class="card card-shadow border-top-0">
          <div class="card-main border-top h-100">
            <div class="card border-0 no-shadow card-hover flex-sm-row">
              <div class="card-img-mask card-img-mask-full card-img-mh min-w-50 order-sm-1">
                <img
                srcset="/wp-content/uploads/2025/08/dashboardPreview.png 414w,
                        /wp-content/uploads/2025/08/dashboardPreview.png 720w,
                        /wp-content/uploads/2025/08/dashboardPreview.png 1080w"
                sizes="(max-width: 480px) 414px, (max-width: 800px) 720px, 1080px"
                src="/wp-content/uploads/2025/08/dashboardPreview.png"
                alt="Dashboard preview"
                role="presentation"
                />            
              </div>
              <div class="d-flex flex-column flex-grow-1 w-100 order-sm-2">
                <div class="card-body pb-0">
                  <?php $dashboard_url = getenv('DASHBOARD_URL') ?: 'https://dashboard.well.mcmaster.ca'; ?>
                  <h3 class="card-title no-line p-0"><a href="<?php echo esc_url($dashboard_url); ?>" ><span class="sr-only">The SEES Dashboard</span></a></h3>
                  <div class="card-text mb-0">
                    <p>Explore the <strong>WELL Dashboard</strong> to view and download current and historical data. All data is freely available to all for teaching, research, and outreach applications. </p>
                    <p><strong>Data Available:</strong></p>
                    <ul>
                      <li><strong>West Campus (near parking Lot P):</strong> Real-time and continuous (10-minutes sampling interval) readings from the weather station, a water quality sensor, and five water level loggers.</li>
                      <li><strong>Ancaster Creek Watershed Monitoring Sites:</strong> Bi-weekly water quality data and seasonal geomorphic data collected at nine sampling sites across the Ancaster Creek Watershed.</li>
                    </ul>
                    <p><strong>WELL is growing!</strong> WELL is an ever-evolving space and we have hope to expand the instrumentation and data collection in the future. If there is something we can add to WELL to support a course or outreach initiative, such as adding additional sensors or sampling sites, purchasing lab equipment, or integrating your data into the WELL network, please connect with the team and we can make it happen!</p>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0" aria-hidden="true">
                  <span class="d-flex align-items-center nav-link nav-link-sm border-bottom-0 h-100">
                    The WELL Dashboard
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>