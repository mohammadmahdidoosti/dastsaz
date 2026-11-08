<?php
// Dastine child theme.
if (!defined('ABSPATH')) { exit; }

add_action('wp_enqueue_scripts', function () {
    $file = get_stylesheet_directory() . '/style.css';
    wp_enqueue_style('dastine', get_stylesheet_uri(), array(), file_exists($file) ? (string) filemtime($file) : '1.1.0');
}, 20);

// Favicon fallback when no Site Icon is set.
add_action('wp_head', function () {
    if (!has_site_icon()) {
        echo '<link rel="icon" type="image/svg+xml" href="' . esc_url(get_stylesheet_directory_uri() . '/assets/images/dastine-mark.svg') . '">' . "\n";
    }
});
