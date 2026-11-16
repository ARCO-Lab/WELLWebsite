<?php
/**
 * Title: Hero Banner
 * Slug: well/hero-banner
 * Categories: well
 * Description: Full-width banner with a background photo, a page title and one supporting line, matching the site's page-header banners.
 */

$image_url = esc_url( get_template_directory_uri() . '/img/media/hero-installation-1600.webp' );
?>
<!-- wp:cover {"url":"<?php echo $image_url; ?>","dimRatio":50,"overlayColor":"black","minHeight":420,"align":"full"} -->
<div class="wp-block-cover alignfull" style="min-height:420px"><span aria-hidden="true" class="wp-block-cover__background has-black-background-color has-background-dim-50 has-background-dim"></span><img class="wp-block-cover__image-background" alt="" src="<?php echo $image_url; ?>" data-object-fit="cover"/><div class="wp-block-cover__inner-container">
<!-- wp:heading {"textAlign":"center","level":1,"className":"banner-title banner-title-lg banner-title-line banner-text-rev"} -->
<h1 class="wp-block-heading has-text-align-center banner-title banner-title-lg banner-title-line banner-text-rev">Page Title Here</h1>
<!-- /wp:heading -->

<!-- wp:paragraph {"align":"center","className":"banner-text banner-text-rev"} -->
<p class="has-text-align-center banner-text banner-text-rev">A short supporting line about this page.</p>
<!-- /wp:paragraph -->
</div></div>
<!-- /wp:cover -->
