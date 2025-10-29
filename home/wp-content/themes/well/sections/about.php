<?php
// This section renders the "About Us" content for the WELL theme in WordPress.
// It displays the WELL logo and a brief description with a call-to-action button.
?>
<section class="content-area cool-grey my-4">
  <div class="container">
    <div class="row">
      <div class="col-12">
        <div class="row">
          <div class="col-md-4 pr-md-4 my-3 align-self-center">
            <div class="text-center">
              <figure class="mw-100">
                <img 
                alt="WELL Logo"
                srcset="
                    /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-32x32.png 32w,
                    /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-150x150.png 150w,
                    /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-180x180.png 180w,
                    /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-192x192.png 192w,
                    /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-270x270.png 270w,
                    /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG-300x300.png 300w,
                    /wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG.png 600w
                "
                sizes="(max-width: 480px) 150px, (max-width: 800px) 270px, 300px"
                src="/wp-content/uploads/2025/08/cropped-WELL_LogoOnly_TransparentBG.png"
                class="img-fluid d-block mx-auto"
                />            
              </figure>
            </div>
          </div>
          <div class="col-md-8 pl-md-4 my-3 align-self-center">
            <h2>About Us</h2>
            <p>The <strong> Watershed and Ecosystems Living Lab (WELL) </strong> at McMaster University is an interdisciplinary initiative that brings together students, researchers, and the community to monitor and learn from real-time environmental data. <strong>WELL</strong> provides hands-on learning opportunities and valuable data through its network of real-time environmental sensors and comprehensive watershed-wide sampling regime within the Ancaster Creek watershed in Hamilton. </p>
            <p style="text-align: left;">
              <a class="btn btn-primary btn-lg text-center" style="background-color: #fdbf57; color: black; border-color: #FDBF57;" href="<?php echo esc_url( home_url('/about') ); ?>">Learn More</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>