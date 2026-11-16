<?php
/**
 * Title: Team Member Card
 * Slug: well/team-member
 * Categories: well
 * Description: A single team member card — photo, name, role and a short bio. Place three across inside a Columns block for a team row.
 */

$image_url = esc_url( get_template_directory_uri() . '/img/media/about-research-600.webp' );
?>
<!-- wp:group {"className":"card card-shadow well-team-member","layout":{"type":"constrained"}} -->
<div class="wp-block-group card card-shadow well-team-member">
<!-- wp:image {"sizeSlug":"large","className":"well-team-member__photo"} -->
<figure class="wp-block-image size-large well-team-member__photo"><img src="<?php echo $image_url; ?>" alt="Photo of team member"/></figure>
<!-- /wp:image -->

<!-- wp:heading {"level":3,"className":"well-team-member__name"} -->
<h3 class="wp-block-heading well-team-member__name">Full Name</h3>
<!-- /wp:heading -->

<!-- wp:paragraph {"className":"well-team-member__role"} -->
<p class="well-team-member__role">Role or title</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph {"className":"well-team-member__bio"} -->
<p class="well-team-member__bio">One or two sentences about this person's work with WELL.</p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->
