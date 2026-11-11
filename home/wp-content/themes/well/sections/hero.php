<?php
// This section renders the homepage hero carousel for the WELL WordPress theme.
// It displays rotating banners with images and calls to action for WELL, Dashboard, and News.
// The slide images are pre-sized WebP copies (see well_media_img() in functions.php).
?>
<banner>
  <section class="carousel">
    <div class="hero-carousel" data-flickity='{ "cellAlign": "left", "contain": true, "adaptiveHeight": true, "pageDots": true, "autoPlay": 15000, "wrapAround": true }'>
      <!-- Carousel Text | Right Banner -->
      <div class="carousel-cell drop">
        <?php well_media_img('hero-teaching', array(414, 800), array(800, 343), array(
             'class'         => 'carousel-bg carousel-bg-left carousel-bg-bottom',
             'sizes'         => '(max-width: 991.98px) 100vw, 90vw',
             'alt'           => 'Teaching Photo',
             'role'          => 'presentation',
             // First slide: the largest image above the fold, so fetch it first.
             'fetchpriority' => 'high',
        )); ?>
        <div class="cell-container circle-mask circle-mask-right"></div>
        <div class="container-fluid pt-4 pb-5 pt-lg-0 pb-lg-0">
          <div class="row">
            <div class="col-10 mx-auto">
              <div class="row carousel-limiter ml-auto">
                <div class="col-lg-10 ml-auto d-lg-flex flex-lg-column align-items-lg-end justify-content-lg-center carousel-text text-lg-right">
                  <h2 class="banner-title banner-title-lg">WELL</h2>
                  <p class="banner-text">The WELL Lab provides hands-on learning opportunities through advanced weather stations, water quality sensors, and sampling sites that span from McMaster’s campus to the broader Ancaster watershed.</p>
                  <a class="btn btn-primary btn-lg" href="<?php echo esc_url( home_url('/about') ); ?>"><span>Learn about WELL</span></a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- Carousel Text | Right Banner -->
      <div class="carousel-cell drop">
        <?php well_media_img('hero-weather', array(414, 720, 1080, 1600), array(1600, 685), array(
             'class'         => 'carousel-bg carousel-bg-left',
             'sizes'         => '(max-width: 991.98px) 100vw, 90vw',
             'alt'           => 'Weather Preview',
             'role'          => 'presentation',
             'loading'       => 'lazy',
        )); ?>
        <div class="cell-container circle-mask circle-mask-right"></div>
        <div class="container-fluid pt-4 pb-5 pt-lg-0 pb-lg-0">
          <div class="row">
            <div class="col-10 mx-auto">
              <div class="row carousel-limiter ml-auto">
                <div class="col-lg-10 ml-auto d-lg-flex flex-lg-column align-items-lg-end justify-content-lg-center carousel-text text-lg-right">
                  <h2 class="banner-title banner-title-lg">Dashboard</h2>
                  <p class="banner-text">The WELL Dashboard displays real-time and historical environmental data from across McMaster and the Ancaster watershed.</p>
                  <?php $dashboard_url = getenv('DASHBOARD_URL') ?: 'https://welldash.mcmaster.ca'; ?>
                  <a class="btn btn-primary btn-lg" href="<?php echo esc_url( $dashboard_url ); ?>"><span>Explore the Dashboard</span></a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- Carousel Text | Left Banner -->
      <div class="carousel-cell drop">
        <?php well_media_img('hero-installation', array(414, 720, 1080, 1600, 2000), array(2000, 857), array(
             'class'         => 'carousel-bg carousel-bg-right',
             'sizes'         => '(max-width: 991.98px) 100vw, 90vw',
             'alt'           => 'Installation Photo 2',
             'role'          => 'presentation',
             'loading'       => 'lazy',
        )); ?>
        <div class="cell-container circle-mask circle-mask-left"></div>
        <div class="container-fluid pt-4 pb-5 pt-lg-0 pb-lg-0">
          <div class="row">
            <div class="col-10 mx-auto">
              <div class="row carousel-limiter mr-auto">
                <div class="col-lg-10 mr-auto d-lg-flex flex-lg-column align-items-lg-start justify-content-lg-center carousel-text text-lg-left">
                  <h2 class="banner-title banner-title-lg">News</h2>
                  <p class="banner-text">WELL is making a difference in teaching and research at McMaster</p>
                  <a class="btn btn-primary btn-lg" href="<?php echo esc_url( home_url('/news') ); ?>"><span>Read More</span></a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</banner>