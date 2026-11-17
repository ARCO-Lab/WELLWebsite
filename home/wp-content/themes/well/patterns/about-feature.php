<?php
/**
 * Title: Text + Circular Photo (About section)
 * Slug: well/about-feature
 * Categories: well
 * Description: A banded content section with a heading and paragraphs beside a circular dotted-ring photo, matching the About page's text-and-photo sections.
 */

$image = '/wp-content/themes/well/img/media/about-watershed-600.webp';
?>
<!-- wp:group {"className":"content-area white my-4","layout":{"type":"default"}} -->
<div class="wp-block-group content-area white my-4">
<!-- wp:group {"className":"container","layout":{"type":"default"}} -->
<div class="wp-block-group container">
<!-- wp:columns {"verticalAlignment":"center"} -->
<div class="wp-block-columns are-vertically-aligned-center">
<!-- wp:column {"verticalAlignment":"center","width":"66.66%"} -->
<div class="wp-block-column is-vertically-aligned-center" style="flex-basis:66.66%">
<!-- wp:heading -->
<h2 class="wp-block-heading">Section heading</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Use this space to explain one idea in a short paragraph or two. Replace this text with your own.</p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:column -->

<!-- wp:column {"verticalAlignment":"center","width":"33.33%"} -->
<div class="wp-block-column is-vertically-aligned-center" style="flex-basis:33.33%">
<!-- wp:html -->
<div class="text-center"><figure class="mb-0 profile mx-auto"><div class="fig-img-mask rounded-circle"><img src="<?php echo esc_url( $image ); ?>" width="600" height="600" decoding="async" alt="" class="img-fluid" sizes="300px"></div></figure></div>
<!-- /wp:html -->
</div>
<!-- /wp:column -->
</div>
<!-- /wp:columns -->
</div>
<!-- /wp:group -->
</div>
<!-- /wp:group -->
