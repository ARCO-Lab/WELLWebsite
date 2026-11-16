<?php
/**
 * Title: Two Column (Text + Image)
 * Slug: well/two-column-text-image
 * Categories: well
 * Description: Text on one side and a photo on the other — good for an intro, a feature or a profile section.
 */

$image_url = esc_url( get_template_directory_uri() . '/img/media/about-weatherstation-600.webp' );
?>
<!-- wp:columns {"verticalAlignment":"center"} -->
<div class="wp-block-columns are-vertically-aligned-center">
<!-- wp:column {"verticalAlignment":"center","width":"55%"} -->
<div class="wp-block-column is-vertically-aligned-center" style="flex-basis:55%">
<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading">Section heading</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Use this space to explain one idea: what this section is about, why it matters, and what the reader should do next. Keep it to a short paragraph or two.</p>
<!-- /wp:paragraph -->

<!-- wp:buttons -->
<div class="wp-block-buttons">
<!-- wp:button -->
<div class="wp-block-button"><a class="wp-block-button__link wp-element-button" href="#">Learn more</a></div>
<!-- /wp:button -->
</div>
<!-- /wp:buttons -->
</div>
<!-- /wp:column -->

<!-- wp:column {"verticalAlignment":"center","width":"45%"} -->
<div class="wp-block-column is-vertically-aligned-center" style="flex-basis:45%">
<!-- wp:image {"sizeSlug":"large"} -->
<figure class="wp-block-image size-large"><img src="<?php echo $image_url; ?>" alt=""/></figure>
<!-- /wp:image -->
</div>
<!-- /wp:column -->
</div>
<!-- /wp:columns -->
