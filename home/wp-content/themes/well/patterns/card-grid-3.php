<?php
/**
 * Title: Card Grid (3-up)
 * Slug: well/card-grid-3
 * Categories: well
 * Description: A row of three matching cards with a photo, title, description and link, using the site's card styling.
 */

$base  = get_template_directory_uri() . '/img/media/';
$cards = array(
    array(
        'image' => $base . 'about-installation-600.webp',
        'title' => 'Card Title One',
        'text'  => 'Short description of this item.',
    ),
    array(
        'image' => $base . 'about-research-600.webp',
        'title' => 'Card Title Two',
        'text'  => 'Short description of this item.',
    ),
    array(
        'image' => $base . 'about-watershed-600.webp',
        'title' => 'Card Title Three',
        'text'  => 'Short description of this item.',
    ),
);
?>
<!-- wp:columns -->
<div class="wp-block-columns">
<?php foreach ( $cards as $card ) : ?>
<!-- wp:column -->
<div class="wp-block-column">
<!-- wp:group {"className":"card card-shadow border-top-0","layout":{"type":"constrained"}} -->
<div class="wp-block-group card card-shadow border-top-0">
<!-- wp:image {"sizeSlug":"large","className":"card-img-mask card-img-mask-top"} -->
<figure class="wp-block-image size-large card-img-mask card-img-mask-top"><img src="<?php echo esc_url( $card['image'] ); ?>" alt=""/></figure>
<!-- /wp:image -->

<!-- wp:group {"className":"card-body","style":{"spacing":{"padding":{"top":"24px","right":"24px","bottom":"24px","left":"24px"}}},"layout":{"type":"constrained"}} -->
<div class="wp-block-group card-body" style="padding-top:24px;padding-right:24px;padding-bottom:24px;padding-left:24px">
<!-- wp:heading {"level":3,"className":"card-title"} -->
<h3 class="wp-block-heading card-title"><?php echo esc_html( $card['title'] ); ?></h3>
<!-- /wp:heading -->

<!-- wp:paragraph {"className":"card-text"} -->
<p class="card-text"><?php echo esc_html( $card['text'] ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p><a href="#">Learn more</a></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->
</div>
<!-- /wp:group -->
</div>
<!-- /wp:column -->
<?php endforeach; ?>
</div>
<!-- /wp:columns -->
