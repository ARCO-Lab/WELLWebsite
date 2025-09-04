<?php
// This is the single post template for the WELL WordPress theme.
// It displays a single news article, its metadata, and related news posts.

get_header();
?>

<?php
if ( have_posts() ) :
    while ( have_posts() ) : the_post();
?>

<nav aria-label="breadcrumb" class="breadcrumb-nav">
    <div class="container">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="<?php echo home_url(); ?>">Home</a></li>
            <li class="breadcrumb-item"><a href="<?php echo home_url('/news/'); ?>">News</a></li>
            <li class="breadcrumb-item active"><?php the_title(); ?></li>
        </ol>
    </div>
</nav>

<main id="site-content">
    <section class="sidebar">
        <div class="container">
            <div class="row">
                <div class="col-xl-9 col-lg-8 pr-xl-5 pr-lg-3">
                    <section>
                        <h1 class="news-title my-3"><?php the_title(); ?></h1>

                        <div class="row">
                            <div class="col-12 col-md-9 news-subtitle-container align-self-center">
                                <p class="news-byline">By <?php the_author(); ?></p>
                                <time class="news-date">Posted on <?php echo get_the_date('F j, Y'); ?></time>
                            </div>
                            <div class="col-12 col-md-3 text-md-right align-self-center">
                                <div class="dropdown social-share">
                                    <button class="btn btn-info dropdown-toggle" type="button" id="dropdownMenuButton" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">Share</button>
                                    <div class="dropdown-menu" aria-labelledby="dropdownMenuButton">
                                        <div class="social-share-title"></div>
                                        <div class="ss-icon-menu">
                                            <a class="ss-icons ss-twitter" href="https://twitter.com/intent/tweet?url=<?php the_permalink(); ?>&text=<?php the_title(); ?>" target="_blank"><span class="sr-only">Twitter</span></a>
                                            <a class="ss-icons ss-facebook" href="https://www.facebook.com/sharer.php?u=<?php the_permalink(); ?>" target="_blank"><span class="sr-only">Facebook</span></a>
                                            <a class="ss-icons ss-linkedin" href="https://www.linkedin.com/sharing/share-offsite/?url=<?php the_permalink(); ?>" target="_blank"><span class="sr-only">LinkedIn</span></a>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div>
                            <hr class="news-divider">
                        </div>

                        <?php the_content(); ?>

                        <span class="category h6"><i class="fa fa-tags"></i>&nbsp;News</span>
                    </section>

                    <?php
                    // Related Posts Query
                    $related_args = array(
                        'post_type' => 'post',
                        'posts_per_page' => 3,
                        'post__not_in' => array( get_the_ID() ),
                        'tax_query' => array(
                            array(
                                'taxonomy' => 'category',
                                'field' => 'slug',
                                'terms' => 'news',
                            ),
                        ),
                    );
                    $related_query = new WP_Query( $related_args );
                    if ( $related_query->have_posts() ) :
                    ?>
                    <section class="section-padding">
                        <h2 class="subtitle mb-0 related-news">Related News</h2>
                        <section class="section-padding">
                            <div class="container">
                                <h2 class="sr-only">News Listing</h2>
                                <div class="row row-eq-height">
                                    <?php while ( $related_query->have_posts() ) : $related_query->the_post(); ?>
                                    <div class="col-lg-4 col-md-6">
                                        <div class="card card-shadow border-top-0">
                                            <div class="card-main border-top h-100">
                                                <div class="card border-0 no-shadow card-hover">
                                                    <div class="card-body pb-0">
                                                        <h3 class="card-title">
                                                            <a href="<?php the_permalink(); ?>" target="_self">
                                                                <?php the_title(); ?>
                                                            </a>
                                                        </h3>
                                                        <div class="card-text mb-0">
                                                            <p class="card-subtitle mt-2 text-maroon">News</p>
                                                        </div>
                                                    </div>
                                                    <div class="card-footer border-top-0 px-4 py-3">
                                                        <p class="small m-0"><strong><?php echo get_the_date('F j, Y'); ?></strong></p>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <?php endwhile; wp_reset_postdata(); ?>
                                </div>
                            </div>
                        </section>
                    </section>
                    <?php endif; ?>
                </div>
                <aside class="col-xl-3 col-lg-4 sidebar-bg sidebar-bg-right py-5 pl-xl-5">
                </aside>
            </div>
        </div>
    </section>
</main>

<?php
    endwhile;
endif;
?>

<?php
get_footer();
?>