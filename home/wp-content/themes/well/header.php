<?php
// This file renders the HTML <head> and site header for the WELL WordPress theme.
// It includes meta tags, favicon links, accessibility skip links, McMaster and site navigation menus.
?>
<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
    <meta charset="<?php bloginfo( 'charset' ); ?>">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="<?php bloginfo( 'name' ); ?>">
    <link rel="profile" href="https://gmpg.org/xfn/11">
    <link rel="pingback" href="<?php bloginfo( 'pingback_url' ); ?>">
    <link rel="apple-touch-icon" sizes="180x180" href="<?php echo get_template_directory_uri(); ?>/favicons/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="<?php echo get_template_directory_uri(); ?>/favicons/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="<?php echo get_template_directory_uri(); ?>/favicons/favicon-16x16.png">
    <link rel="manifest" href="<?php echo get_template_directory_uri(); ?>/favicons/site.webmanifest">
    <link rel="mask-icon" href="<?php echo get_template_directory_uri(); ?>/favicons/safari-pinned-tab.svg" color="#7a003c">
    <meta name="msapplication-TileColor" content="#7a003c">
    <meta name="theme-color" content="#ffffff">
    <?php wp_head(); ?>
</head>
<body <?php body_class(); ?>>
    <header id="mcmaster-header" style="position: relative;">
        <div id="skiptocontent">
            <a href="#mcmaster-nav">Skip to McMaster Navigation</a>
            <a href="#site-navbar">Skip to Site Navigation</a>
            <a href="#site-content">Skip to main content</a>
        </div>
        <div class="header__inner">
            <a href="https://www.mcmaster.ca" id="mcmaster-brand" class="nav-item" style="float:left; display:block; z-index:1000; position:relative; padding-top: 8px;">
                <img src="<?php echo get_template_directory_uri(); ?>/img/logo.svg" style="width: 180px; height: 80px; margin: 0 20px 0 -20px;" alt="McMaster logo" />
                <span class="sr-only">McMaster logo</span>
            </a>
            <div id="mcmaster-header__title">
                <h2 class="mcmaster-header__department"><a href="https://sees.mcmaster.ca/">School of Earth, Environment & Society</a></h2>
                <h1 class="mcmaster-header__header-title"><a href="<?php echo esc_url( home_url( '/' ) ); ?>">Watershed and Ecosystems Living Lab</a></h1>
            </div>
        </div>
        <div id="navLinks" style="display: flex; align-items: center; width:160px; z-index:1200; transition: width 0s; margin-top: 24px; justify-content: flex-end;">
            <a href="<?php echo esc_url( home_url( '/' ) ); ?>" id="well-home-logo" class="nav-item" aria-label="WELL Home">
                <img src="<?php echo get_template_directory_uri(); ?>/img/welllogo.svg" alt="WELL logo" />
            </a>
        </div>
    </header>

    <!-- Search Overlay -->
    <div id="mcmaster-search-overlay" aria-label="Site Search and Quick Links" role="dialog" style="display: none;">
        <div class="search-container">
            <button class="search-close" aria-label="Close search">&times;</button>
            <h2>Search McMaster</h2>
            <form role="search" method="get" action="<?php echo esc_url( home_url( '/' ) ); ?>">
                <input type="search" name="s" class="search-input" placeholder="Search for pages, people, or resources..." value="<?php echo get_search_query(); ?>" />
                <button type="submit" class="search-submit">Search</button>
            </form>
            <div class="search-results"></div>
        </div>
    </div>

    <!-- Navigation Overlay -->
    <div class="nav-overlay"></div>
    
    <!-- Navigation Menu -->
    <ul id="mcmaster-nav" role="menubar" aria-label="McMaster menu" style="display: block; overflow-y: scroll;">
        <li class="nav-header">
            <span>McMaster Menu</span>
            <button class="nav-close" aria-label="Close menu">&times;</button>
        </li>
        <li class="nav-content">
            <ul role="none">
                <?php 
                $nav_menu = well_get_mcmaster_nav_menu();
                foreach ($nav_menu as $item): 
                    $expanded = isset($item['expanded']) && $item['expanded'] ? 'true' : 'false';
                    $submenu_class = $expanded === 'true' ? 'sub-menu active' : 'sub-menu';
                ?>
                <li role="none">
                    <a href="<?php echo esc_url($item['url']); ?>" 
                       data-dparent="<?php echo esc_attr($item['id']); ?>" 
                       aria-expanded="<?php echo $expanded; ?>" 
                       aria-controls="<?php echo esc_attr($item['id']); ?>" 
                       class="collapsed" 
                       tabindex="0" 
                       role="menuitem"><?php echo esc_html($item['title']); ?></a>
                    
                    <?php if (!empty($item['children'])): ?>
                    <ul id="<?php echo esc_attr($item['id']); ?>" 
                        aria-expanded="<?php echo $expanded; ?>" 
                        aria-label="<?php echo esc_attr($item['title']); ?>" 
                        role="menu" 
                        class="<?php echo $submenu_class; ?>">
                        <?php foreach ($item['children'] as $child): ?>
                        <li role="none">
                            <a href="<?php echo esc_url($child['url']); ?>" 
                               role="menuitem"><?php echo esc_html($child['title']); ?></a>
                        </li>
                        <?php endforeach; ?>
                    </ul>
                    <?php endif; ?>
                </li>
                <?php endforeach; ?>
            </ul>
        </li>
    </ul>

    <nav id="site-navbar" class="navbar navbar-expand-lg navbar-dark navbar-site nav-fill navbar-lg level-three">
        <div class="container">
            <button class="navbar-toggler site-toggler collapsed" type="button" data-toggle="collapse" data-target="#siteMenu" aria-controls="siteMenu" aria-expanded="false" aria-label="Toggle navigation">
                Main Menu
            </button>
            <?php
            wp_nav_menu(
                array(
                    'theme_location'  => 'primary',
                    'container_class' => 'collapse navbar-collapse',
                    'container_id'    => 'siteMenu',
                    'menu_class'      => 'navbar-nav',
                    'fallback_cb'     => '',
                    'menu_id'         => 'navbar-nav,mr-auto',
                    'depth'           => 3,
                    'walker'          => new WP_Bootstrap_Navwalker(),
                )
            );
            ?>
        </div>
    </nav>
    <div class="hfeed site" id="page">