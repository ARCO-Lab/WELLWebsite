<?php
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
                <a class="btn my-0 focusable btn-secondary" href="http://localhost:3000" target="_blank">Dashboard</a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</banner>
<iframe src="http://localhost:3000/" style="width:100%;height:100vh;border:none;"></iframe>


<?php
get_footer();
?>
