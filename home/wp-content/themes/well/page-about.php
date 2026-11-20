<?php
// This is the "About Us" page template for the WELL WordPress theme.
//
// The page's prose (the four "About WELL" / "What is WELL measuring?" ... text-and-photo sections) is
// now editable in wp-admin: it lives in the page's block content and is rendered by the_content()
// below. The "Our Team" cards stay developer-owned code and are placed in the content as the
// [well_team] shortcode (see sections/team.php and inc/shortcodes.php).
//
// The breadcrumb and the "About Us" page title are template chrome, the same on every view, so they
// stay here rather than in the editable content.
//
// Fallback: if the page has no block content yet (it has not been migrated — see
// tools/migrate-pages-to-blocks.php), the original hard-coded sections render instead, so the page is
// never blank. Once the content is populated, the_content() path is used.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.

get_header();
?>

<nav aria-label="breadcrumb" class="breadcrumb-nav">
  <div class="container">
    <ol class="breadcrumb">
      <li class="breadcrumb-item"><a href="https://sees.mcmaster.ca">Home</a></li>
      <li class="breadcrumb-item active">About Us</li>
    </ol>
  </div>
</nav>

<header class="section-intro py-4">
  <div class="container">
    <div class="row align-items-center">
      <div class="col-sm-12">
        <h1 class="mb-4">About Us</h1>
      </div>
    </div>
  </div>
</header>

<main id="site-content" class="sidebar">
<?php
while (have_posts()) :
  the_post();

  // An empty block-editor paragraph still counts as empty.
  if ('' !== trim(wp_strip_all_tags(get_the_content()))) {
    the_content();
  } else {
    // Not migrated yet: render the original hard-coded sections so the page is never blank.
?>
  <section class="content-area white my-4">
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="row">
            <div class="col-md-8 pr-md-4 my-3 align-self-center">
              <h2>About WELL</h2>
              <p>The Watershed and Ecosystems Living Lab (WELL) is an environmental monitoring initiative based at McMaster University. WELL consists of two components: a network of real-time environmental monitoring sensors in West Campus (near parking Lot P) and a comprehensive sampling regime across the Ancaster Creek watershed from the headwaters, through Mac Forest to Cootes Drive. Data collected though WELL provides continuous insights into the hydrology, climate, and ecological health indicators in the watershed to support teaching, research, professional development workshops, and community engagement.</p>
              <p>Led by a team of researchers at McMaster University in partnership with undergraduate and graduate student teams, WELL is a unique resource for environmental science teaching, learning, research, and community engagement.</p>
            </div>
            <div class="col-md-4 pl-md-4 my-3 align-self-center">
              <div class="text-center">
                <figure class="mb-0 profile mx-auto">
                  <div class="fig-img-mask rounded-circle">
                  <?php well_media_img('about-watershed', array(300, 600), array(600, 600), array('alt' => 'Ancaster Watershed', 'class' => 'img-fluid', 'sizes' => '300px')); ?>
                  </div>
                </figure>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="content-area white my-4">
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="row">
            <div class="col-md-6 pr-md-4 my-3 align-self-center">
              <div class="text-center">
                <figure class="mb-0 profile mx-auto">
                  <div class="fig-img-mask rounded-circle">
                  <?php well_media_img('about-weatherstation', array(300, 600, 900), array(900, 900), array('alt' => 'Ancaster Creek', 'class' => 'img-fluid', 'sizes' => '300px')); ?>
                  </div>
                </figure>
              </div>
            </div>
            <div class="col-md-6 pl-md-4 my-3 align-self-center">
              <h2>What is WELL measuring?</h2>
              <p>In West Campus, a fully remote sensor network is collecting real-time data on weather, soil moisture and temperature, water levels, and water quality in Ancaster Creek. A network of nine additional monitoring stations across the Ancaster Creek watershed are sampled bi-weekly for nutrient and water quality parameter, and seasonally for geomorphic processes. Plans to expand sampling to include fish and benthic community monitoring are in place.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="content-area white my-4">
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="row">
            <div class="col-md-8 pr-md-4 my-3 align-self-center">
              <h2>What type of teaching does WELL support?</h2>
              <p>With plans to expand the instrumentation, WELL is poised to become a cornerstone of environmental education at McMaster. It’s convenient on-campus location makes it easy to integrate into courses of all levels and has already been integrated into several courses across the Faculty of Science and the Faculty of Engineering. WELL has also been used for industry-focused workshops on river monitoring.</p>
              <p>WELL also serves as a unique experiential learning opportunity for students. The sensor network in West Campus was installed by a team of undergraduate and graduate students, providing them with hands-on site selection, instrumentation, and fieldwork experience. The sampling regime at the monitoring station across the watershed is also conducted by a team of students. Even this website was designed and built by an undergraduate student research assistant!</p>
            </div>
            <div class="col-md-4 pl-md-4 my-3 align-self-center">
              <div class="text-center">
                <figure class="mb-0 profile mx-auto">
                  <div class="fig-img-mask rounded-circle">
                  <?php well_media_img('about-installation', array(300, 600, 900), array(900, 900), array('alt' => 'Ancaster Watershed', 'class' => 'img-fluid', 'sizes' => '300px', 'loading' => 'lazy')); ?>
                  </div>
                </figure>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="content-area white my-4">
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="row">
            <div class="col-md-6 pr-md-4 my-3 align-self-center">
              <div class="text-center">
                <figure class="mb-0 profile mx-auto">
                  <div class="fig-img-mask rounded-circle">
                  <?php well_media_img('about-research', array(300, 600, 900), array(900, 900), array('alt' => 'Ancaster Creek', 'class' => 'img-fluid', 'sizes' => '300px', 'loading' => 'lazy')); ?>
                  </div>
                </figure>
              </div>
            </div>
            <div class="col-md-6 pl-md-4 my-3 align-self-center">
              <h2>What type of research does WELL support?</h2>
              <p>WELL is not connected to a single research project but is rather a shared data collection effort that can support a multitude of research projects in various fields. Some early examples include measuring stream health indicators to assess the success of naturalization projects in West Campus and serving as a testing ground for new sensor technology and geomorphic monitoring techniques.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <?php get_template_part('sections/team'); ?>
<?php
  }
endwhile;
?>
</main>

<?php
get_footer();
?>
