<?php
// This is the "About Us" page template for the WELL WordPress theme.
// It displays information about WELL, its team, and its activities.

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
                  <img alt="Ancaster Watershed" src="/wp-content/uploads/2025/08/ancasterwatershed.jpg" class="img-fluid">
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
                  <img alt="Ancaster Creek" src="/wp-content/uploads/2025/08/ancastercreek.jpg" class="img-fluid">
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
                  <img alt="Ancaster Watershed" src="/wp-content/uploads/2025/09/InstallationPhoto1.jpeg" class="img-fluid">
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
                  <img alt="Ancaster Creek" src="/wp-content/uploads/2025/09/wellresearch.png" class="img-fluid">
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
</main>
<main>
  <section class="dynamic-content people white my-5">
    <div class="container">
      <h2 class="text-left">Our Team</h2>
      <div class="row row-eq-height justify-content-start">
        <div class="col-lg-3 col-md-6">
          <div class="modal fade" id="modal_elli" tabindex="-1" aria-labelledby="modal_elli-label" aria-hidden="true">
            <div class="modal-dialog">
              <div class="modal-content">
                <div class="modal-header">
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Elli Papangelakis</h3>
                    <div class="card-text mb-0">
                      <p id="modal_elli-label">Director</p>
                    </div>
                  </div>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <div class="modal-body p-0">
                  <div class="row row-cols-2 m-0">
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="tel:+19055259140,12345" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-phone mr-2"></i>(905) 525-9140 x12345
                    </a>
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:papangee@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-envelope mr-2"></i>papangee@mcmaster.ca
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty" target="_blank">More Information</a>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                </div>
              </div>
            </div>
          </div>
          <div class="card card-shadow border-top-0">
            <div class="card-main border-top h-100">
              <div class="card border-0 no-shadow">
                <div class="card-body pb-0 text-center">
                  <div class="icon-circle">
                    <img width="150" height="150" src="/wp-content/uploads/2025/08/ellipapangelakis.jpg" class="rounded-circle wp-post-image" alt="Elli Papangelakis" decoding="async">
                  </div>
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Elli Papangelakis</h3>
                  </div>
                  <div class="card-text mb-0">
                    <p class="mb-0"><strong>Director</strong></p>
                  </div>
                  <div class="list-group list-group-flush small mt-2">
                    <a href="tel:+19055259140,12345" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0" aria-label="Primary phone number for Dr. John Smith">
                      <i class="fa fa-phone mr-2 text-muted"></i><strong>(905) 525-9140 x12345</strong>
                    </a>
                    <a href="mailto:papangee@mcmaster.ca" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0">
                      <i class="fa fa-envelope mr-2 text-muted"></i><strong>papangee@mcmaster.ca</strong>
                    </a>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0 text-center">
                  <div class="dropup mx-3 mt-3 mb-4">
                    <a class="btn btn-info" href="#modal_elli" data-toggle="modal" aria-haspopup="true" aria-expanded="false">
                      More Information
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="col-lg-3 col-md-6">
          <div class="modal fade" id="modal_waddington" tabindex="-1" aria-labelledby="modal_waddington-label" aria-hidden="true">
            <div class="modal-dialog">
              <div class="modal-content">
                <div class="modal-header">
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. James Michael Waddington</h3>
                    <div class="card-text mb-0">
                      <p id="modal_waddington-label">Scientific Advisory Committee Member</p>
                    </div>
                  </div>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <div class="modal-body p-0">
                  <div class="row row-cols-2 m-0">
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:jmw@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-envelope mr-2"></i>jmw@mcmaster.ca
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty/" target="_blank">More Information</a>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                </div>
              </div>
            </div>
          </div>
          <div class="card card-shadow border-top-0">
            <div class="card-main border-top h-100">
              <div class="card border-0 no-shadow">
                <div class="card-body pb-0 text-center">
                  <div class="icon-circle">
                    <img width="150" height="150" src="/wp-content/uploads/2025/08/mikewaddington.png" class="rounded-circle wp-post-image" alt="" decoding="async">
                  </div>
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. James Michael Waddington</h3>
                  </div>
                  <div class="card-text mb-0">
                    <p class="mb-0"><strong>Scientific Advisory Committee Member</strong></p>
                  </div>
                  <div class="list-group list-group-flush small mt-2">
                    <a href="mailto:jmw@mcmaster.ca" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0">
                      <i class="fa fa-envelope mr-2 text-muted"></i><strong>jmw@mcmaster.ca</strong>
                    </a>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0 text-center">
                  <div class="dropup mx-3 mt-3 mb-4">
                    <a class="btn btn-info" href="#modal_waddington" data-toggle="modal" aria-haspopup="true" aria-expanded="false">
                      More Information
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-lg-3 col-md-6">
          <div class="modal fade" id="modal_carey" tabindex="-1" aria-labelledby="modal_carey-label" aria-hidden="true">
            <div class="modal-dialog">
              <div class="modal-content">
                <div class="modal-header">
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Sean Carey</h3>
                    <div class="card-text mb-0">
                      <p id="modal_carey-label">Scientific Advisory Commitee Member</p>
                    </div>
                  </div>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <div class="modal-body p-0">
                  <div class="row row-cols-2 m-0">
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:careysk@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-envelope mr-2"></i>careysk@mcmaster.ca
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty/" target="_blank">More Information</a>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                </div>
              </div>
            </div>
          </div>
          <div class="card card-shadow border-top-0">
            <div class="card-main border-top h-100">
              <div class="card border-0 no-shadow">
                <div class="card-body pb-0 text-center">
                  <div class="icon-circle">
                    <img width="150" height="150" src="/wp-content/uploads/2025/08/seancarey.jpg" class="rounded-circle wp-post-image" alt="" decoding="async">
                  </div>
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Sean Carey</h3>
                  </div>
                  <div class="card-text mb-0">
                    <p class="mb-0"><strong>Scientific Advisory Committee Member</strong></p>
                  </div>
                  <div class="list-group list-group-flush small mt-2">
                    <a href="mailto:careysk@mcmaster.ca" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0">
                      <i class="fa fa-envelope mr-2 text-muted"></i><strong>careysk@mcmaster.ca</strong>
                    </a>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0 text-center">
                  <div class="dropup mx-3 mt-3 mb-4">
                    <a class="btn btn-info" href="#modal_carey" data-toggle="modal" aria-haspopup="true" aria-expanded="false">
                      More Information
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-lg-3 col-md-6">
          <div class="modal fade" id="modal_arain" tabindex="-1" aria-labelledby="modal_arain-label" aria-hidden="true">
            <div class="modal-dialog">
              <div class="modal-content">
                <div class="modal-header">
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Altaf Arain</h3>
                    <div class="card-text mb-0">
                      <p id="modal_arain-label">Scientific Advisory Committee Member</p>
                    </div>
                  </div>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <div class="modal-body p-0">
                  <div class="row row-cols-2 m-0">
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:arianm@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-envelope mr-2"></i>arianm@mcmaster.ca
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty/" target="_blank">More Information</a>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                </div>
              </div>
            </div>
          </div>
          <div class="card card-shadow border-top-0">
            <div class="card-main border-top h-100">
              <div class="card border-0 no-shadow">
                <div class="card-body pb-0 text-center">
                  <div class="icon-circle">
                    <img width="150" height="150" src="/wp-content/uploads/2025/08/altafarain.png" class="rounded-circle wp-post-image" alt="" decoding="async">
                  </div>
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Altaf Arain</h3>
                  </div>
                  <div class="card-text mb-0">
                    <p class="mb-0"><strong>Scientific Advisory Committee Member</strong></p>
                  </div>
                  <div class="list-group list-group-flush small mt-2">
                    <a href="mailto:arianm@mcmaster.ca" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0">
                      <i class="fa fa-envelope mr-2 text-muted"></i><strong>arianm@mcmaster.ca</strong>
                    </a>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0 text-center">
                  <div class="dropup mx-3 mt-3 mb-4">
                    <a class="btn btn-info" href="#modal_arain" data-toggle="modal" aria-haspopup="true" aria-expanded="false">
                      More Information
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-lg-3 col-md-6">
          <div class="modal fade" id="modal_gonsamo" tabindex="-1" aria-labelledby="modal_gonsamo-label" aria-hidden="true">
            <div class="modal-dialog">
              <div class="modal-content">
                <div class="modal-header">
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Alemu Gonsamo</h3>
                    <div class="card-text mb-0">
                      <p id="modal_gonsamo-label">Scientific Advisory Committee Member</p>
                    </div>
                  </div>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <div class="modal-body p-0">
                  <div class="row row-cols-2 m-0">
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:gonsamoa@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-envelope mr-2"></i>gonsamoa@mcmaster.ca
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty/" target="_blank">More Information</a>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                </div>
              </div>
            </div>
          </div>
          <div class="card card-shadow border-top-0">
            <div class="card-main border-top h-100">
              <div class="card border-0 no-shadow">
                <div class="card-body pb-0 text-center">
                  <div class="icon-circle">
                    <img width="150" height="150" src="/wp-content/uploads/2025/08/alemugonsamo.jpg" class="rounded-circle wp-post-image" alt="" decoding="async">
                  </div>
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Alemu Gonsamo</h3>
                  </div>
                  <div class="card-text mb-0">
                    <p class="mb-0"><strong>Scientific Advisory Committee Member</strong></p>
                  </div>
                  <div class="list-group list-group-flush small mt-2">
                    <a href="mailto:gonsamoa@mcmaster.ca" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0">
                      <i class="fa fa-envelope mr-2 text-muted"></i><strong>gonsamoa@mcmaster.ca</strong>
                    </a>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0 text-center">
                  <div class="dropup mx-3 mt-3 mb-4">
                    <a class="btn btn-info" href="#modal_gonsamo" data-toggle="modal" aria-haspopup="true" aria-expanded="false">
                      More Information
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-lg-3 col-md-6">
          <div class="modal fade" id="modal_coulibaly" tabindex="-1" aria-labelledby="modal_coulibaly-label" aria-hidden="true">
            <div class="modal-dialog">
              <div class="modal-content">
                <div class="modal-header">
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Paulin Coulibaly</h3>
                    <div class="card-text mb-0">
                      <p id="modal_coulibaly-label">Scientific Advisory Committee Member</p>
                    </div>
                  </div>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <div class="modal-body p-0">
                  <div class="row row-cols-2 m-0">
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:couliba@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-envelope mr-2"></i>couliba@mcmaster.ca
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty/" target="_blank">More Information</a>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                </div>
              </div>
            </div>
          </div>
          <div class="card card-shadow border-top-0">
            <div class="card-main border-top h-100">
              <div class="card border-0 no-shadow">
                <div class="card-body pb-0 text-center">
                  <div class="icon-circle">
                    <img width="150" height="150" src="/wp-content/uploads/2025/08/paulincoulibaly.jpg" class="rounded-circle wp-post-image" alt="" decoding="async">
                  </div>
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Paulin Coulibaly</h3>
                  </div>
                  <div class="card-text mb-0">
                    <p class="mb-0"><strong>Scientific Advisory Committee Member</strong></p>
                  </div>
                  <div class="list-group list-group-flush small mt-2">
                    <a href="mailto:couliba@mcmaster.ca" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0">
                      <i class="fa fa-envelope mr-2 text-muted"></i><strong>couliba@mcmaster.ca</strong>
                    </a>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0 text-center">
                  <div class="dropup mx-3 mt-3 mb-4">
                    <a class="btn btn-info" href="#modal_coulibaly" data-toggle="modal" aria-haspopup="true" aria-expanded="false">
                      More Information
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-lg-3 col-md-6">
          <div class="modal fade" id="modal_chowfraser" tabindex="-1" aria-labelledby="modal_chowfraser-label" aria-hidden="true">
            <div class="modal-dialog">
              <div class="modal-content">
                <div class="modal-header">
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Chow-Fraser</h3>
                    <div class="card-text mb-0">
                      <p id="modal_chowfraser-label">Collaborator</p>
                    </div>
                  </div>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <div class="modal-body p-0">
                  <div class="row row-cols-2 m-0">
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="tel:+19055259140,27338" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-phone mr-2"></i>(905) 525-9140 x27338
                    </a>
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:chowfras@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-envelope mr-2"></i>chowfras@mcmaster.ca
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <a class="btn-link-label btn btn-primary mr-auto" href="https://biology.mcmaster.ca/people/faculty/" target="_blank">More Information</a>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                </div>
              </div>
            </div>
          </div>
          <div class="card card-shadow border-top-0">
            <div class="card-main border-top h-100">
              <div class="card border-0 no-shadow">
                <div class="card-body pb-0 text-center">
                  <div class="icon-circle">
                    <img width="150" height="150" src="/wp-content/uploads/2025/08/chowfraser.jpg" class="rounded-circle wp-post-image" alt="" decoding="async">
                  </div>
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Chow-Fraser</h3>
                  </div>
                  <div class="card-text mb-0">
                    <p class="mb-0"><strong>Collaborator</strong></p>
                  </div>
                  <div class="list-group list-group-flush small mt-2">
                    <a href="tel:+19055259140,27338" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0" aria-label="Primary phone number for Dr. Jane Doe">
                      <i class="fa fa-phone mr-2 text-muted"></i><strong>(905) 525-9140 x27338</strong>
                    </a>
                    <a href="mailto:chowfras@mcmaster.ca" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0">
                      <i class="fa fa-envelope mr-2 text-muted"></i><strong>chowfras@mcmaster.ca</strong>
                    </a>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0 text-center">
                  <div class="dropup mx-3 mt-3 mb-4">
                    <a class="btn btn-info" href="#modal_chowfraser" data-toggle="modal" aria-haspopup="true" aria-expanded="false">
                      More Information
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-lg-3 col-md-6">
          <div class="modal fade" id="modal_matthew" tabindex="-1" aria-labelledby="modal_matthew-label" aria-hidden="true">
            <div class="modal-dialog">
              <div class="modal-content">
                <div class="modal-header">
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Matthew Giamou</h3>
                    <div class="card-text mb-0">
                      <p id="modal_matthew-label">Collaborator</p>
                    </div>
                  </div>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <div class="modal-body p-0">
                  <div class="row row-cols-2 m-0">
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="tel:+19055259140,67890" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-phone mr-2"></i>(905) 525-9140 x67890
                    </a>
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:giamoum@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-envelope mr-2"></i>giamoum@mcmaster.ca
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <a class="btn-link-label btn btn-primary mr-auto" href="https://www.eng.mcmaster.ca/cas/faculty/matthew-giamou/" target="_blank">More Information</a>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                </div>
              </div>
            </div>
          </div>
          <div class="card card-shadow border-top-0">
            <div class="card-main border-top h-100">
              <div class="card border-0 no-shadow">
                <div class="card-body pb-0 text-center">
                  <div class="icon-circle">
                    <img width="150" height="150" src="/wp-content/uploads/2025/08/matthewgiamou.jpg" class="rounded-circle wp-post-image" alt="" decoding="async">
                  </div>
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Matthew Giamou</h3>
                  </div>
                  <div class="card-text mb-0">
                    <p class="mb-0"><strong>Collaborator</strong></p>
                  </div>
                  <div class="list-group list-group-flush small mt-2">
                    <a href="tel:+19055259140,67890" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0" aria-label="Primary phone number for Dr. Jane Doe">
                      <i class="fa fa-phone mr-2 text-muted"></i><strong>(905) 525-9140 x67890</strong>
                    </a>
                    <a href="mailto:giamoum@mcmaster.ca" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0">
                      <i class="fa fa-envelope mr-2 text-muted"></i><strong>giamoum@mcmaster.ca</strong>
                    </a>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0 text-center">
                  <div class="dropup mx-3 mt-3 mb-4">
                    <a class="btn btn-info" href="#modal_matthew" data-toggle="modal" aria-haspopup="true" aria-expanded="false">
                      More Information
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-lg-3 col-md-6">
          <div class="modal fade" id="modal_kidd" tabindex="-1" aria-labelledby="modal_kidd-label" aria-hidden="true">
            <div class="modal-dialog">
              <div class="modal-content">
                <div class="modal-header">
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Kidd</h3>
                    <div class="card-text mb-0">
                      <p id="modal_kidd-label">Collaborator</p>
                    </div>
                  </div>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <div class="modal-body p-0">
                  <div class="row row-cols-2 m-0">
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="tel:+19055259140,23550" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-phone mr-2"></i>(905) 525-9140 23550
                    </a>
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:karenkidd@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-envelope mr-2"></i>karenkidd@mcmaster.ca
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <a class="btn-link-label btn btn-primary mr-auto" href="https://biology.mcmaster.ca/people/faculty/" target="_blank">More Information</a>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                </div>
              </div>
            </div>
          </div>
          <div class="card card-shadow border-top-0">
            <div class="card-main border-top h-100">
              <div class="card border-0 no-shadow">
                <div class="card-body pb-0 text-center">
                  <div class="icon-circle">
                    <img width="150" height="150" src="/wp-content/uploads/2025/08/karenkidd.jpg" class="rounded-circle wp-post-image" alt="" decoding="async">
                  </div>
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Dr. Kidd</h3>
                  </div>
                  <div class="card-text mb-0">
                    <p class="mb-0"><strong>Collaborator</strong></p>
                  </div>
                  <div class="list-group list-group-flush small mt-2">
                    <a href="tel:+19055259140,23550" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0" aria-label="Primary phone number for Dr. Kidd">
                      <i class="fa fa-phone mr-2 text-muted"></i><strong>(905) 525-9140 23550</strong>
                    </a>
                    <a href="mailto:karenkidd@mcmaster.ca" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0">
                      <i class="fa fa-envelope mr-2 text-muted"></i><strong>karenkidd@mcmaster.ca</strong>
                    </a>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0 text-center">
                  <div class="dropup mx-3 mt-3 mb-4">
                    <a class="btn btn-info" href="#modal_kidd" data-toggle="modal" aria-haspopup="true" aria-expanded="false">
                      More Information
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-lg-3 col-md-6">
          <div class="modal fade" id="modal_lukhsaan" tabindex="-1" aria-labelledby="modal_lukhsaan-label" aria-hidden="true">
            <div class="modal-dialog">
              <div class="modal-content">
                <div class="modal-header">
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Lukhsaan Elankumaran</h3>
                    <div class="card-text mb-0">
                      <p id="modal_lukhsaan-label">Website Developer</p>
                    </div>
                  </div>
                  <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <div class="modal-body p-0">
                  <div class="row row-cols-2 m-0">
                    <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:elankuml@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                      <i class="fa fa-envelope mr-2"></i>elankuml@mcmaster.ca
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <a class="btn-link-label btn btn-primary mr-auto" href="https://linkedin.com/in/lukhsaan/" target="_blank">More Information</a>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                </div>
              </div>
            </div>
          </div>
          <div class="card card-shadow border-top-0">
            <div class="card-main border-top h-100">
              <div class="card border-0 no-shadow">
                <div class="card-body pb-0 text-center">
                  <div class="icon-circle">
                    <img width="150" height="150" src="/wp-content/uploads/2025/08/lukhsaankumar.jpeg" class="rounded-circle wp-post-image" alt="" decoding="async">
                  </div>
                  <div>
                    <h3 class="card-title no-line p-0 pb-2">Lukhsaan Elankumaran</h3>
                  </div>
                  <div class="card-text mb-0">
                    <p class="mb-0"><strong>Website Developer</strong></p>
                  </div>
                  <div class="list-group list-group-flush small mt-2">
                    <a href="mailto:elankuml@mcmaster.ca" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0">
                      <i class="fa fa-envelope mr-2 text-muted"></i><strong>elankuml@mcmaster.ca</strong>
                    </a>
                  </div>
                </div>
                <div class="card-footer border-top-0 p-0 text-center">
                  <div class="dropup mx-3 mt-3 mb-4">
                    <a class="btn btn-info" href="#modal_lukhsaan" data-toggle="modal" aria-haspopup="true" aria-expanded="false">
                      More Information
                    </a>
                  </div>
                </div>
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