<?php
// The "Our Team" section of the About page: a grid of team-member cards, each with a Bootstrap
// modal (data-toggle="modal") holding that person's contact details and a "More Information" link.
//
// This stays developer-owned PHP, not editable blocks, because every card is wired to its own modal
// by a matching id (#modal_elli, #modal_waddington ...). A generic editable block would break that
// wiring. Editors place or move the whole section with the [well_team] shortcode (see
// inc/shortcodes.php); the cards themselves are maintained here in code.
defined( 'ABSPATH' ) || exit; // Only WordPress may load this file; a direct request gets an empty page.
?>
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
                  <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:papangee@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                    <i class="fa fa-envelope mr-2"></i>papangee@mcmaster.ca
                  </a>
                </div>
              </div>
              <div class="modal-footer">
                <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty" target="_blank" rel="noopener noreferrer">More Information</a>
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
                  <?php well_media_img('team-ellipapangelakis', array(), array(150, 150), array('class' => 'rounded-circle wp-post-image', 'alt' => 'Elli Papangelakis', 'loading' => 'lazy')); ?>
                </div>
                <div>
                  <h3 class="card-title no-line p-0 pb-2">Dr. Elli Papangelakis</h3>
                </div>
                <div class="card-text mb-0">
                  <p class="mb-0"><strong>Director</strong></p>
                </div>
                <div class="list-group list-group-flush small mt-2">
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
                <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty/" target="_blank" rel="noopener noreferrer">More Information</a>
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
                  <?php well_media_img('team-mikewaddington', array(), array(150, 150), array('class' => 'rounded-circle wp-post-image', 'alt' => '', 'loading' => 'lazy')); ?>
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
                <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty/" target="_blank" rel="noopener noreferrer">More Information</a>
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
                  <?php well_media_img('team-seancarey', array(), array(150, 150), array('class' => 'rounded-circle wp-post-image', 'alt' => '', 'loading' => 'lazy')); ?>
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
                <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty/" target="_blank" rel="noopener noreferrer">More Information</a>
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
                  <?php well_media_img('team-altafarain', array(), array(150, 150), array('class' => 'rounded-circle wp-post-image', 'alt' => '', 'loading' => 'lazy')); ?>
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
                <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty/" target="_blank" rel="noopener noreferrer">More Information</a>
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
                  <?php well_media_img('team-alemugonsamo', array(), array(150, 150), array('class' => 'rounded-circle wp-post-image', 'alt' => '', 'loading' => 'lazy')); ?>
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
                <a class="btn-link-label btn btn-primary mr-auto" href="https://sees.mcmaster.ca/people/faculty/" target="_blank" rel="noopener noreferrer">More Information</a>
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
                  <?php well_media_img('team-paulincoulibaly', array(), array(150, 150), array('class' => 'rounded-circle wp-post-image', 'alt' => '', 'loading' => 'lazy')); ?>
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
                <a class="btn-link-label btn btn-primary mr-auto" href="https://biology.mcmaster.ca/people/faculty/" target="_blank" rel="noopener noreferrer">More Information</a>
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
                  <?php well_media_img('team-chowfraser', array(), array(150, 150), array('class' => 'rounded-circle wp-post-image', 'alt' => '', 'loading' => 'lazy')); ?>
                </div>
                <div>
                  <h3 class="card-title no-line p-0 pb-2">Dr. Chow-Fraser</h3>
                </div>
                <div class="card-text mb-0">
                  <p class="mb-0"><strong>Collaborator</strong></p>
                </div>
                <div class="list-group list-group-flush small mt-2">
                  <a href="tel:+19055259140,27338" class="list-group-item list-group-item-action pt-0 pb-1 px-0 border-0 m-0" aria-label="Primary phone number for Dr. Chow-Fraser">
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
                  <a class="dropdown-item px-3 py-2 col-sm-6 col-12" href="mailto:giamoum@mcmaster.ca" style="overflow: hidden; white-space: initial;">
                    <i class="fa fa-envelope mr-2"></i>giamoum@mcmaster.ca
                  </a>
                </div>
              </div>
              <div class="modal-footer">
                <a class="btn-link-label btn btn-primary mr-auto" href="https://www.eng.mcmaster.ca/cas/faculty/matthew-giamou/" target="_blank" rel="noopener noreferrer">More Information</a>
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
                  <?php well_media_img('team-matthewgiamou', array(), array(150, 150), array('class' => 'rounded-circle wp-post-image', 'alt' => '', 'loading' => 'lazy')); ?>
                </div>
                <div>
                  <h3 class="card-title no-line p-0 pb-2">Dr. Matthew Giamou</h3>
                </div>
                <div class="card-text mb-0">
                  <p class="mb-0"><strong>Collaborator</strong></p>
                </div>
                <div class="list-group list-group-flush small mt-2">
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
                <a class="btn-link-label btn btn-primary mr-auto" href="https://biology.mcmaster.ca/people/faculty/" target="_blank" rel="noopener noreferrer">More Information</a>
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
                  <?php well_media_img('team-karenkidd', array(), array(150, 150), array('class' => 'rounded-circle wp-post-image', 'alt' => '', 'loading' => 'lazy')); ?>
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
                <a class="btn-link-label btn btn-primary mr-auto" href="https://linkedin.com/in/lukhsaan/" target="_blank" rel="noopener noreferrer">More Information</a>
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
                  <?php well_media_img('team-lukhsaankumar', array(), array(150, 150), array('class' => 'rounded-circle wp-post-image', 'alt' => '', 'loading' => 'lazy')); ?>
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
