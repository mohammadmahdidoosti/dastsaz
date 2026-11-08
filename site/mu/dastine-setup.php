<?php
/*
 * Plugin Name: Dastine one-time setup
 * Description: Creates the halls (product categories), the basic pages, and moves WordPress sample content to the trash. Runs once.
 */
if (!defined('ABSPATH')) { exit; }

add_action('admin_init', function () {
    if (get_option('dastine_setup_done') === '1' || !current_user_can('manage_options') || !taxonomy_exists('product_cat')) {
        return;
    }
    foreach (array('necklace' => 'گردنبند', 'ring' => 'انگشتر', 'earring' => 'گوشواره', 'bracelet' => 'دستبند') as $slug => $name) {
        if (!term_exists($slug, 'product_cat')) {
            wp_insert_term($name, 'product_cat', array('slug' => $slug));
        }
    }
    if (taxonomy_exists('product_tag') && !term_exists('gift', 'product_tag')) {
        wp_insert_term('کادو', 'product_tag', array('slug' => 'gift'));
    }
    $pages = array(
        'about' => array('داستانِ ما',
            "<!-- wp:paragraph {\"fontSize\":\"large\"} -->\n<p class=\"has-large-font-size\">دستینه از یک فکرِ ساده شروع شد: زیوری که می‌پوشی باید قصه داشته باشد.</p>\n<!-- /wp:paragraph -->\n\n<!-- wp:paragraph -->\n<p>هر قطعه‌ی دستینه را یک سازنده با دست و با حوصله می‌سازد. برای همین هر قطعه شناسنامه دارد: اسمِ سازنده، شماره‌ی قطعه و تاریخِ ساخت. چیزی که به دستت می‌رسد یک کالای بی‌نام از قفسه‌ی یک انبار نیست؛ کارِ دستِ یک نفر است.</p>\n<!-- /wp:paragraph -->\n\n<!-- wp:paragraph -->\n<p>می‌توانی روی قطعه‌ات اسم، تاریخ یا مصرعی را که دوست داری حکاکی کنی، تا فقط مالِ تو باشد، یا مالِ کسی که برایش هدیه می‌گیری.</p>\n<!-- /wp:paragraph -->\n\n<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">از دستانِ سازنده، به دستانِ تو</h2>\n<!-- /wp:heading -->\n\n<!-- wp:paragraph -->\n<p>[این‌جا چند خط از داستانِ خودت و سازنده‌ها: از کجا شروع کردید، چرا دست‌ساز، و این‌که هر قطعه چطور ساخته می‌شود.]</p>\n<!-- /wp:paragraph -->"),
        'favorites' => array('دلخواه‌ها', "<!-- wp:shortcode -->\n[dastine_favorites]\n<!-- /wp:shortcode -->"),
        'shipping' => array('ارسال و مرجوعی',
            "<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">زمانِ ساخت و ارسال</h2>\n<!-- /wp:heading -->\n\n<!-- wp:paragraph -->\n<p>بیشترِ قطعه‌ها بعد از سفارشِ تو ساخته می‌شوند. زمانِ ساختِ هر قطعه در صفحه‌ی خودش نوشته شده. بعد از ساخت، سفارش با [پست پیشتاز] در [X تا Y روزِ کاری] به دستت می‌رسد.</p>\n<!-- /wp:paragraph -->\n\n<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">هزینه‌ی ارسال</h2>\n<!-- /wp:heading -->\n\n<!-- wp:paragraph -->\n<p>[هزینه‌ی ارسال / شرطِ ارسالِ رایگان]</p>\n<!-- /wp:paragraph -->\n\n<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">مرجوعی</h2>\n<!-- /wp:heading -->\n\n<!-- wp:paragraph -->\n<p>[شرایطِ مرجوعی. قطعه‌های حکاکی‌شده چون فقط برای تو ساخته شده‌اند معمولاً مرجوع نمی‌شوند، مگر ایرادِ ساخت داشته باشند.]</p>\n<!-- /wp:paragraph -->"),
        'contact' => array('تماس با ما',
            "<!-- wp:paragraph -->\n<p>سؤالی درباره‌ی یک قطعه، حکاکی یا سفارشت داری؟ از این راه‌ها با ما در تماس باش:</p>\n<!-- /wp:paragraph -->\n\n<!-- wp:list -->\n<ul class=\"wp-block-list\"><!-- wp:list-item -->\n<li>اینستاگرام: [آدرس پیج]</li>\n<!-- /wp:list-item -->\n\n<!-- wp:list-item -->\n<li>تلگرام / واتس‌اپ: [شماره]</li>\n<!-- /wp:list-item -->\n\n<!-- wp:list-item -->\n<li>ایمیل: info@dastine.art</li>\n<!-- /wp:list-item --></ul>\n<!-- /wp:list -->"),
    );
    foreach ($pages as $slug => $p) {
        if (!get_page_by_path($slug)) {
            wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish', 'post_name' => $slug, 'post_title' => $p[0], 'post_content' => $p[1]));
        }
    }
    $hello = get_page_by_path('hello-world', OBJECT, 'post');
    if ($hello) { wp_trash_post($hello->ID); }
    foreach (get_posts(array('post_type' => 'post', 'post_status' => 'publish', 'numberposts' => 5)) as $post) {
        if (strpos($post->post_content, 'به وردپرس خوش آمدید') !== false) { wp_trash_post($post->ID); }
    }
    foreach (get_posts(array('post_type' => 'page', 'post_status' => 'publish', 'numberposts' => 20)) as $page) {
        if ($page->post_title === 'برگه نمونه' || $page->post_name === 'sample-page') { wp_trash_post($page->ID); }
    }
    update_option('dastine_setup_done', '1');
});
