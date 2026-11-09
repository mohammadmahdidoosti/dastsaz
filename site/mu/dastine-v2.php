<?php
/**
 * Dastine v2: homepage blocks, footer, product page and halls (went live 2026-11-08).
 * Also fixes stray <br> gaps in product cards and keeps the product summary from sliding over the story.
 */

add_action('template_redirect', 'dastine_v2_hooks', 1);

/* ---------- fixes for everyone ---------- */
add_action('wp_head', function () {
    echo '<style id="dastine-fixes">'
        . '.dastine-loop li.product br,.dastine-archive li.product br,.dastine-related li.product br{display:none}'
        . '.dastine-loop li.product a,.dastine-archive li.product a{line-height:1.6}'
        . '.dastine-product .summary{position:static}'
        . '</style>';
}, 50);

/* ---------- floating support (WhatsApp, Telegram, phone) ---------- */
add_action('wp_footer', function () {
    if (is_admin()) { return; }
    echo '<details class="dastine-fab"><summary aria-label="پشتیبانی">'
        . '<svg class="dastine-fab__open" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/></svg>'
        . '<svg class="dastine-fab__close" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg></summary>'
        . '<div class="dastine-fab__list">'
        . '<a href="https://wa.me/989100291903" rel="noopener"><i style="background:#25D366"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20l1.3-4A8 8 0 1 1 8 19z"/><path d="M9 9c0 3 3 6 6 6l1-1.5-2-1-1 .8c-1-.5-2-1.5-2.4-2.4l.8-1-1-2z"/></svg></i><span>واتس‌اپ</span></a>'
        . '<a href="https://t.me/+989100291903" rel="noopener"><i style="background:#2AABEE"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 4 3 11l6 2 2 6 3-4 5 4z"/><path d="m9 13 8-6"/></svg></i><span>تلگرام</span></a>'
        . '<a href="https://www.instagram.com/dastine.official/" rel="noopener"><i style="background:#C13584"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="5"/><circle cx="12" cy="12" r="3.6"/><circle cx="16.8" cy="7.2" r="0.6"/></svg></i><span>اینستاگرام</span></a>'
        . '<a href="tel:09100291903"><i style="background:#3B2A24"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1z"/></svg></i><span>تماس تلفنی</span></a>'
        . '</div></details>';
}, 30);

/* ---------- trust seal (e-Namad): the owner pastes the code on Settings › نماد اعتماد ---------- */
add_action('admin_menu', function () {
    add_options_page('نماد اعتماد', 'نماد اعتماد', 'unfiltered_html', 'dastine-seal', function () {
        if (!current_user_can('unfiltered_html')) { return; }
        $note = '';
        if (!empty($_POST['dastine_seal_nonce']) && wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['dastine_seal_nonce'])), 'dastine_seal')) {
            update_option('dastine_seal', trim((string) wp_unslash($_POST['dastine_seal'] ?? '')));
            $note = 'ذخیره شد. پایینِ همه‌ی صفحه‌ها، ستونِ «نمادِ اعتماد» را ببینید.';
        }
        echo '<div class="wrap" dir="rtl"><h1>نماد اعتماد (اینماد)</h1>';
        if ($note) { echo '<div class="notice notice-success"><p>' . esc_html($note) . '</p></div>'; }
        echo '<p>کدی را که سایتِ اینماد داده (یک لینک و یک عکس) کامل این‌جا بچسبانید و ذخیره کنید. خالی بماند، جای خالی نشان داده می‌شود.</p>'
            . '<form method="post">';
        wp_nonce_field('dastine_seal', 'dastine_seal_nonce');
        echo '<textarea name="dastine_seal" rows="8" class="large-text code" dir="ltr">' . esc_textarea((string) get_option('dastine_seal', '')) . '</textarea>'
            . '<p><button class="button button-primary">ذخیره</button></p></form></div>';
    });
});
add_filter('render_block', function ($html, $block) {
    if (($block['blockName'] ?? '') !== 'core/html' || strpos($html, 'v2-seal') === false) { return $html; }
    $code = trim((string) get_option('dastine_seal', ''));
    if ($code === '') { return $html; }
    return preg_replace('#<div class="v2-seal">.*?</div>#su', '<div class="v2-seal v2-seal--on">' . $code . '</div>', $html, 1);
}, 10, 2);

/* ---------- checkout: name, province, city, address, mobile. No email, no postcode. ---------- */
function dastine_latin_digits($s) {
    return strtr((string) $s, array('۰' => '0', '۱' => '1', '۲' => '2', '۳' => '3', '۴' => '4', '۵' => '5', '۶' => '6', '۷' => '7', '۸' => '8', '۹' => '9',
        '٠' => '0', '١' => '1', '٢' => '2', '٣' => '3', '٤' => '4', '٥' => '5', '٦' => '6', '٧' => '7', '٨' => '8', '٩' => '9'));
}
add_filter('woocommerce_get_country_locale', function ($l) {
    $l['IR']['postcode'] = array('required' => true, 'hidden' => false, 'label' => 'کد پستی', 'priority' => 95);
    $l['IR']['phone'] = array('label' => 'موبایل', 'required' => true, 'priority' => 25);
    $l['IR']['address_1'] = array('label' => 'نشانیِ کامل', 'placeholder' => 'محله، خیابان، کوچه، پلاک، واحد', 'priority' => 90);
    $l['IR']['state'] = array('priority' => 60);
    $l['IR']['city'] = array('priority' => 70);
    return $l;
}, 50);
add_filter('woocommerce_checkout_fields', function ($f) {
    unset($f['billing']['billing_email'], $f['billing']['billing_company'], $f['billing']['billing_address_2'],
        $f['shipping']['shipping_company'], $f['shipping']['shipping_address_2']);
    if (isset($f['billing']['billing_phone'])) {
        $f['billing']['billing_phone'] = array_merge($f['billing']['billing_phone'], array(
            'label' => 'موبایل', 'required' => true, 'priority' => 25, 'placeholder' => '۰۹۱۲۱۲۳۴۵۶۷',
            'description' => 'پیامکِ ثبت و ارسالِ سفارش به همین شماره می‌آید.', 'class' => array('form-row-wide')));
    }
    if (isset($f['billing']['billing_address_1'])) {
        $f['billing']['billing_address_1']['placeholder'] = 'محله، خیابان، کوچه، پلاک، واحد';
        $f['billing']['billing_address_1']['label'] = 'نشانیِ کامل';
    }
    if (isset($f['billing']['billing_postcode'])) {
        $f['billing']['billing_postcode']['placeholder'] = '۱۰ رقم، بدون خط تیره';
    }
    if (isset($f['order']['order_comments'])) {
        $f['order']['order_comments']['placeholder'] = 'اگر نکته‌ای درباره‌ی سفارش یا حکاکی داری، این‌جا بنویس (اختیاری)';
    }
    return $f;
}, 50);
add_filter('woocommerce_checkout_posted_data', function ($d) {
    if (isset($d['billing_phone'])) {
        $p = preg_replace('/\D+/', '', dastine_latin_digits($d['billing_phone']));
        if (strpos($p, '98') === 0 && strlen($p) === 12) { $p = '0' . substr($p, 2); }
        if (strlen($p) === 10 && $p[0] === '9') { $p = '0' . $p; }
        $d['billing_phone'] = $p;
    }
    if (isset($d['billing_postcode'])) {
        $d['billing_postcode'] = preg_replace('/\D+/', '', dastine_latin_digits($d['billing_postcode']));
    }
    return $d;
});
add_action('woocommerce_after_checkout_validation', function ($data, $errors) {
    if (!preg_match('/^09\d{9}$/', (string) ($data['billing_phone'] ?? ''))) {
        $errors->add('validation', 'شماره‌ی موبایل را درست وارد کن؛ مثلاً ۰۹۱۲۱۲۳۴۵۶۷');
    }
    if (!preg_match('/^\d{10}$/', (string) ($data['billing_postcode'] ?? ''))) {
        $errors->add('validation', 'کد پستی باید ۱۰ رقم باشد.');
    }
}, 10, 2);
add_filter('woocommerce_cart_needs_shipping_address', '__return_false');
add_filter('woocommerce_validate_postcode', function ($ok, $postcode, $country) { return $country === 'IR' ? true : $ok; }, 20, 3);
add_filter('gettext', function ($t, $text, $domain) {
    if ($domain === 'woocommerce' && ($text === 'Billing details' || $text === 'Billing &amp; Shipping')) { return 'اطلاعاتِ ارسال'; }
    return $t;
}, 20, 3);

/* ---------- v2 ---------- */
function dastine_v2_halls() {
    return array(
        'necklace' => array('گردنبند', 'کوچک، شاد، و هر کدام یک قصه؛ برای گردنی که دوست دارد دیده شود.'),
        'ring'     => array('انگشتر', 'انگشترهایی که هر بار نگاهشان کنی، لبخند می‌زنی.'),
        'earring'  => array('گوشواره', 'سبک و رنگی؛ بعضی جفت‌ها عمداً مثلِ هم نیستند.'),
        'bracelet' => array('دستبند', 'نخی و ظریف، برای هر روز و هر مچی.'),
        'gift'     => array('کادو برای…', 'وقتی می‌خواهی چیزی بدهی که با دست ساخته شده؛ با حکاکیِ یک اسم.'),
    );
}

function dastine_v2_hooks() {
    add_filter('body_class', function ($c) { $c[] = 'dastine-v2'; return $c; });

    /* cards: a small bag that opens the piece (engraving lives there) */
    add_action('woocommerce_after_shop_loop_item', function () {
        global $product;
        if (!$product) { return; }
        printf('<a class="dastine-bag" href="%s" aria-label="%s"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8h12l-1 12H7z"/><path d="M9 8V7a3 3 0 0 1 6 0v1"/></svg></a>',
            esc_url(get_permalink($product->get_id())), esc_attr('خریدِ ' . $product->get_name()));
    }, 9);

    /* product page: card preview + a question link right after the buy button */
    add_action('woocommerce_single_product_summary', function () {
        global $product;
        if (!$product) { return; }
        $maker = trim((string) get_post_meta($product->get_id(), 'dastine_maker', true));
        $mat = preg_match('/جنس\s*[:：]\s*([^<\n\r]{1,40})/u', $product->get_description(), $m) ? trim(wp_strip_all_tags($m[1])) : '';
        $mark = esc_url(get_stylesheet_directory_uri() . '/assets/images/dastine-mark.svg');
        echo '<div class="dastine-v2card"><p class="dastine-v2card__cap">همراهِ این اثر می‌رسد:</p>'
            . '<div class="dastine-v2card__card">'
            . '<div class="dastine-v2card__top"><span class="dastine-v2card__brand"><img src="' . $mark . '" alt="">دستینه</span><span class="dastine-v2card__no">اثرِ شماره‌ی<b>بعد از ساخت</b></span></div>'
            . '<p class="dastine-v2card__name">' . esc_html($product->get_name()) . '</p>'
            . '<dl><div><dt>سازنده</dt><dd>' . esc_html($maker !== '' ? $maker : 'به خطِ خودِ سازنده') . '</dd></div>'
            . ($mat !== '' ? '<div><dt>جنس</dt><dd>' . esc_html($mat) . '</dd></div>' : '')
            . '<div><dt>حکاکی</dt><dd>همان که بنویسی</dd></div></dl>'
            . '<div class="dastine-v2card__sign"><i></i>امضای سازنده</div>'
            . '</div></div>'
            . '<p class="dastine-v2ask">سؤالی داری؟ <a href="/contact/">قبل از خرید از ما بپرس</a></p>';
    }, 35);

    /* the story's details list becomes a small table: «جنس: خمیر پلیمری» → label | value */
    add_filter('the_content', function ($html) {
        if (!is_product() || !in_the_loop()) { return $html; }
        return preg_replace_callback('#<li>([^<:：]{1,40})[:：]\s*(.+?)</li>#u', function ($m) {
            return '<li><span>' . trim($m[1]) . '</span><span>' . trim($m[2]) . '</span></li>';
        }, $html);
    }, 20);

    /* halls: no WooCommerce counters, a sentence, the other halls, and three quiet chips */
    remove_action('woocommerce_before_shop_loop', 'woocommerce_result_count', 20);
    remove_action('woocommerce_before_shop_loop', 'woocommerce_catalog_ordering', 30);
    add_action('woocommerce_before_shop_loop', 'dastine_v2_hall_head', 5);
    add_action('woocommerce_no_products_found', 'dastine_v2_hall_head', 5);

    add_action('wp_head', 'dastine_v2_css', 60);
}

function dastine_v2_hall_head() {
    static $done = false;
    if ($done) { return; }
    $done = true;
    $halls = dastine_v2_halls();
    $obj = get_queried_object();
    $slug = ($obj && isset($obj->slug)) ? $obj->slug : '';
    $intro = isset($halls[$slug]) ? $halls[$slug][1] : 'همه‌ی آثارِ دستینه؛ هر کدام را یک نفر با دست می‌سازد.';
    $base = strtok((string) $_SERVER['REQUEST_URI'], '?');
    $chips = array(
        array('محبوب‌ها', $base, empty($_GET['orderby']) && empty($_GET['max_price'])),
        array('تازه‌ها', $base . '?orderby=date', isset($_GET['orderby']) && $_GET['orderby'] === 'date'),
        array('زیرِ ۲۰۰ هزار', $base . '?max_price=200000', !empty($_GET['max_price'])),
    );
    echo '<div class="dastine-v2hall"><p class="dastine-v2hall__intro">' . esc_html($intro) . '</p>';
    echo '<nav class="dastine-v2hall__halls" aria-label="مجموعه‌های دیگر">';
    foreach ($halls as $s => $h) {
        $url = $s === 'gift' ? '/product-tag/gift/' : '/product-category/' . $s . '/';
        printf('<a href="%s"%s>%s</a>', esc_url($url), $s === $slug ? ' aria-current="page"' : '', esc_html($h[0]));
    }
    echo '</nav><nav class="dastine-v2hall__chips" aria-label="چیدمان">';
    foreach ($chips as $c) {
        printf('<a href="%s"%s>%s</a>', esc_url($c[1]), $c[2] ? ' aria-current="true"' : '', esc_html($c[0]));
    }
    echo '</nav></div>';
}

function dastine_v2_css() {
    ?>
<style id="dastine-v2">
.dastine-v2 .v2-wrap{max-width:1240px;margin:0 auto;padding:0 24px;box-sizing:border-box}
.dastine-v2 .v2-trust{background:#FFFFFF;border-top:1px solid var(--d-line);border-bottom:1px solid var(--d-line)}
.dastine-v2 .v2-trust ul{list-style:none;margin:0 auto;padding:18px 24px;max-width:1240px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;box-sizing:border-box}
.dastine-v2 .v2-trust li{display:flex;align-items:center;gap:12px;font-size:14px;color:var(--d-ink)}
.dastine-v2 .v2-trust li b{display:block;font-size:15px}
.dastine-v2 .v2-trust li span{color:var(--d-muted);font-size:13px}
.dastine-v2 .v2-ico{width:42px;height:42px;flex-shrink:0;border-radius:50%;background:var(--d-katan);display:flex;align-items:center;justify-content:center}
.dastine-v2 .v2-ico svg{width:22px;height:22px;fill:none;stroke:var(--d-anar);stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.dastine-v2 .dastine-halls .dastine-cert{display:none}
.dastine-v2 .dastine-wall .dastine-loop li.product:nth-child(n+13){display:none}
.dastine-v2 .dastine-wall.is-open .dastine-loop li.product:nth-child(n+13){display:block}
.dastine-v2 .v2-more{display:flex;justify-content:center;margin-top:36px}
.dastine-v2 .v2-more button{height:50px;padding:0 34px;border-radius:999px;border:1px solid var(--d-ink);background:transparent;color:var(--d-ink);font:inherit;font-weight:700;font-size:15px;cursor:pointer}
.dastine-v2 .v2-more button:hover{border-color:var(--d-anar);color:var(--d-anar)}
.dastine-v2 .dastine-wall.is-open .v2-more{display:none}
.dastine-v2 .v2-workshop{background:var(--d-katan);padding:88px 0}
.dastine-v2 .v2-workshop .v2-wrap{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:64px;align-items:center}
.dastine-v2 .v2-eyebrow{font-size:14px;font-weight:700;color:var(--d-anar);margin:0 0 10px}
.dastine-v2 .v2-workshop h2{font-size:34px;line-height:1.45;margin:0 0 16px;color:var(--d-ink)}
.dastine-v2 .v2-workshop .v2-lead{font-size:17px;line-height:1.95;color:var(--d-ink);margin:0 0 30px}
.dastine-v2 .v2-steps{list-style:none;margin:0 0 32px;padding:0;display:flex;flex-direction:column;gap:18px}
.dastine-v2 .v2-steps li{display:flex;gap:16px;align-items:flex-start}
.dastine-v2 .v2-steps .n{width:36px;height:36px;flex-shrink:0;border-radius:50%;border:1px solid var(--d-sofal);color:var(--d-anar);font-weight:800;display:flex;align-items:center;justify-content:center}
.dastine-v2 .v2-steps b{display:block;font-size:16px;margin-bottom:2px}
.dastine-v2 .v2-steps span{font-size:14px;color:var(--d-muted);line-height:1.8}
.dastine-v2 .v2-btn{display:inline-flex;align-items:center;height:50px;padding:0 30px;border-radius:999px;background:var(--d-anar);color:#FFFFFF!important;font-weight:700;text-decoration:none!important}
.dastine-v2 .v2-btn:hover{background:var(--d-ink)}
.dastine-v2 .v2-visual{position:relative;padding-bottom:70px}
.dastine-v2 .v2-photo{aspect-ratio:4/5;max-width:440px;border-radius:6px;background:#E9DFD2;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding-top:22%;box-sizing:border-box;gap:14px;color:var(--d-muted);font-size:14px;text-align:center;border:1px dashed #CDBBA6}
.dastine-v2 .v2-photo img{width:72px;height:72px;opacity:.6}
.dastine-v2 .v2-card{position:absolute;left:0;bottom:0;width:300px;background:#FBF7F1;border:1px solid var(--d-sofal);border-radius:6px;padding:22px 24px;box-shadow:0 18px 40px rgba(59,42,36,.14);transform:rotate(-3deg);color:var(--d-ink)}
.dastine-v2 .v2-card__top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}
.dastine-v2 .v2-card__brand{display:flex;align-items:center;gap:8px;font-weight:800;color:var(--d-anar)}
.dastine-v2 .v2-card__brand img{width:28px;height:28px}
.dastine-v2 .v2-card__no{text-align:left;font-size:11px;color:var(--d-muted)}
.dastine-v2 .v2-card__no b{display:block;font-size:20px;color:var(--d-ink);letter-spacing:1px}
.dastine-v2 .v2-card__name{font-size:19px;font-weight:800;margin:0 0 12px}
.dastine-v2 .v2-card dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 16px;margin:0;padding-top:10px;border-top:1px solid #DCCBB8}
.dastine-v2 .v2-card dt{font-size:11px;color:var(--d-muted)}
.dastine-v2 .v2-card dd{margin:0;font-size:13px;font-weight:600}
.dastine-v2 .v2-card__sign{margin-top:14px;display:flex;justify-content:space-between;align-items:flex-end;font-size:11px;color:var(--d-muted)}
.dastine-v2 .v2-card__sign i{display:block;width:110px;border-bottom:1px dashed var(--d-muted);height:18px;margin-bottom:4px}
.v2-foot{background:#FFFFFF;border-top:1px solid var(--d-line);padding:56px 0 0}
.dastine-v2 .v2-foot__grid{display:grid;grid-template-columns:1.4fr 1fr 1fr .8fr;gap:40px}
ul.products li.product a:focus:not(:focus-visible),.dastine-hero2 a:focus:not(:focus-visible){outline:none;box-shadow:none}
.v2-foot h3{font-size:15px;margin:0 0 14px;color:var(--d-ink)}
.v2-foot p,.v2-foot li{font-size:14px;color:var(--d-muted);line-height:1.9;margin:0}
.v2-foot ul{list-style:none;margin:0;padding:0}
.v2-foot .v2-wrap a{color:var(--d-ink);text-decoration:none}
.v2-foot .v2-wrap a:hover{color:var(--d-anar)}
.dastine-v2 .v2-foot__brand{font-size:24px;font-weight:800;color:var(--d-anar)!important;margin-bottom:4px!important}
.dastine-v2 .v2-insta{display:inline-flex;align-items:center;gap:8px;margin-top:14px;font-weight:600}
.dastine-v2 .v2-insta svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.7}
.dastine-v2 .v2-soon{font-size:11px;background:var(--d-katan);color:var(--d-muted);padding:1px 8px;border-radius:999px;margin-right:6px}
.dastine-v2 .v2-seal{width:110px;height:120px;border:1px dashed #CDBBA6;border-radius:8px;display:flex;align-items:center;justify-content:center;text-align:center;font-size:12px;color:var(--d-muted);padding:8px;box-sizing:border-box}
.dastine-v2 .v2-copy{margin-top:44px;border-top:1px solid var(--d-line);padding:18px 0 22px;font-size:13px;color:var(--d-muted);text-align:center}
@media (max-width:900px){
.dastine-v2 .v2-trust ul{grid-template-columns:repeat(2,minmax(0,1fr))}
.dastine-v2 .v2-workshop{padding:56px 0}
.dastine-v2 .v2-workshop .v2-wrap{grid-template-columns:minmax(0,1fr);gap:40px}
.dastine-v2 .v2-workshop h2{font-size:26px}
.dastine-v2 .v2-visual{order:2}
.dastine-v2 .v2-photo{max-width:none;aspect-ratio:4/3}
.dastine-v2 .v2-card{width:260px}
.dastine-v2 .v2-foot__grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:32px}
.dastine-v2 .v2-copy{padding-bottom:84px}
}
.dastine-v2 ul.products li.product{position:relative}
.dastine-v2 .dastine-bag{position:absolute;left:0;bottom:0;width:38px;height:38px;border-radius:50%;border:1px solid #D9CDBD;display:flex;align-items:center;justify-content:center;background:#fff;transition:border-color .2s,background .2s}
.dastine-v2 .dastine-bag svg{width:18px;height:18px;fill:none;stroke:var(--d-ink);stroke-width:1.7;stroke-linejoin:round}
.dastine-v2 .dastine-bag:hover{border-color:var(--d-anar);background:var(--d-katan)}
.dastine-v2 .dastine-bag:hover svg{stroke:var(--d-anar)}
.dastine-v2 ul.products li.product .price{padding-left:46px}

.dastine-v2 .dastine-product .summary{display:flex;flex-direction:column}
.dastine-v2 .dastine-product .summary>*{order:0}
.dastine-v2 .dastine-product .summary .dastine-promise{order:2;margin-top:22px}
.dastine-v2 .dastine-product .summary .dastine-v2card{order:3}
.dastine-v2 .dastine-product .summary .dastine-v2ask{order:4}
.dastine-v2 .dastine-product .summary form.cart{margin-bottom:0}
.dastine-v2 .dastine-v2card{margin-top:4px}
.dastine-v2 .dastine-v2card__cap{font-size:13px;color:var(--d-muted);margin:0 0 10px}
.dastine-v2 .dastine-v2card__card{max-width:340px;background:#FBF7F1;border:1px solid var(--d-sofal);border-radius:6px;padding:18px 20px;transform:rotate(-1.5deg);box-shadow:0 10px 26px rgba(59,42,36,.10);color:var(--d-ink)}
.dastine-v2 .dastine-v2card__top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}
.dastine-v2 .dastine-v2card__brand{display:flex;align-items:center;gap:8px;font-weight:800;color:var(--d-anar)}
.dastine-v2 .dastine-v2card__brand img{width:24px;height:24px}
.dastine-v2 .dastine-v2card__no{font-size:11px;color:var(--d-muted);text-align:left}
.dastine-v2 .dastine-v2card__no b{display:block;font-size:12px;color:var(--d-ink)}
.dastine-v2 .dastine-v2card__name{font-size:16px;font-weight:800;margin:0 0 10px}
.dastine-v2 .dastine-v2card dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 14px;margin:0;padding-top:8px;border-top:1px solid #DCCBB8}
.dastine-v2 .dastine-v2card dt{font-size:11px;color:var(--d-muted)}
.dastine-v2 .dastine-v2card dd{margin:0;font-size:13px;font-weight:600}
.dastine-v2 .dastine-v2card__sign{margin-top:12px;font-size:11px;color:var(--d-muted)}
.dastine-v2 .dastine-v2card__sign i{display:block;width:110px;height:16px;border-bottom:1px dashed var(--d-muted);margin-bottom:3px}
.dastine-v2 .dastine-v2ask{font-size:14px;color:var(--d-muted);margin:18px 0 0}
.dastine-v2 .dastine-v2ask a{color:var(--d-anar);font-weight:700}
.dastine-support{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:26px 0}
.dastine-support__btn{display:flex;flex-direction:column;gap:4px;padding:18px 20px;border:1px solid var(--d-line);border-radius:12px;text-decoration:none!important;color:var(--d-ink)!important;transition:border-color .2s,background .2s}
.dastine-support__btn b{font-size:17px;color:var(--d-anar)}
.dastine-support__btn span{font-size:14px;color:var(--d-muted)}
.dastine-support__btn:hover{border-color:var(--d-anar);background:var(--d-katan)}
@media (max-width:700px){.dastine-support{grid-template-columns:minmax(0,1fr)}}

.dastine-v2 .dastine-product .woocommerce-tabs{margin-top:56px;padding-top:40px;border-top:1px solid var(--d-line)}
.dastine-v2 .dastine-product .woocommerce-tabs ul.tabs{display:none}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description{max-width:none;display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:24px 64px;align-items:start}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>*{grid-column:1}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>p:first-of-type{font-size:20px;line-height:2.1;color:var(--d-ink);margin-top:0}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>h2:not(:first-child),.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>h3,.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>ul{grid-column:2}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>h2:not(:first-child),.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>h3{grid-row:1;font-size:15px;margin:0;color:var(--d-muted)}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>ul{grid-row:1 / span 6;margin:34px 0 0;padding:0;list-style:none;border-top:1px solid var(--d-line)}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>ul li{display:flex;justify-content:space-between;gap:16px;padding:9px 0;border-bottom:1px solid var(--d-line);font-size:15px;line-height:1.7}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>ul li span:first-child{color:var(--d-muted)}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>ul li span:last-child{font-weight:600;text-align:left}

.dastine-v2 .dastine-v2hall{margin:-6px 0 26px}
.dastine-v2 .dastine-v2hall__intro{font-size:17px;color:var(--d-muted);margin:0 0 20px;max-width:640px}
.dastine-v2 .dastine-v2hall__halls{display:flex;flex-wrap:wrap;gap:8px 22px;padding-bottom:14px;margin-bottom:16px;border-bottom:1px solid var(--d-line)}
.dastine-v2 .dastine-v2hall__halls a{color:var(--d-muted);text-decoration:none;font-weight:600;font-size:15px;padding:4px 0}
.dastine-v2 .dastine-v2hall__halls a[aria-current]{color:var(--d-anar);box-shadow:inset 0 -2px 0 var(--d-anar)}
.dastine-v2 .dastine-v2hall__chips{display:flex;flex-wrap:wrap;gap:8px}
.dastine-v2 .dastine-v2hall__chips a{display:inline-flex;align-items:center;height:36px;padding:0 16px;border:1px solid #D9CDBD;border-radius:999px;color:var(--d-ink);text-decoration:none;font-size:14px}
.dastine-v2 .dastine-v2hall__chips a[aria-current]{background:var(--d-ink);border-color:var(--d-ink);color:#fff}
.dastine-v2 .v2-seal--on{border:0;width:auto;height:auto;padding:0}
.v2-seal--on img{max-width:110px;height:auto}
.woocommerce-checkout form.checkout{max-width:1000px;margin:0 auto}
.woocommerce-checkout form.checkout .col2-set{width:100%;float:none}
.woocommerce-checkout form.checkout .col2-set .col-1,.woocommerce-checkout form.checkout .col2-set .col-2{width:100%;float:none}
.woocommerce-checkout form.checkout h3{font-size:20px;font-weight:800;margin:0 0 14px}
.woocommerce-checkout form.checkout .form-row{margin:0 0 14px;padding:0}
.woocommerce-checkout form.checkout label{font-weight:600;font-size:14px;margin-bottom:6px;display:block}
.woocommerce-checkout form.checkout input.input-text,.woocommerce-checkout form.checkout textarea,.woocommerce-checkout form.checkout select,.woocommerce-checkout .select2-container .select2-selection--single{border:1px solid #D9CDBD!important;border-radius:10px!important;padding:12px 14px!important;font-family:inherit;font-size:15px;min-height:48px;box-sizing:border-box;width:100%}
.woocommerce-checkout .select2-container .select2-selection--single .select2-selection__rendered{line-height:22px;padding:0}
.woocommerce-checkout .select2-container .select2-selection--single .select2-selection__arrow{top:11px}
.woocommerce-checkout form.checkout .description{font-size:13px;color:var(--d-muted)}
.woocommerce-checkout #order_review_heading{margin-top:28px}
.woocommerce-checkout #order_review table.shop_table{border:1px solid var(--d-line);border-radius:12px;border-collapse:separate}
.woocommerce-checkout #payment{background:var(--d-katan)!important;border-radius:12px}
.woocommerce-checkout #place_order{background:var(--d-anar)!important;color:#fff!important;border-radius:999px!important;width:100%;height:56px;font-size:17px!important;font-weight:700!important;font-family:inherit}
.woocommerce-checkout #place_order:hover{background:var(--d-ink)!important}
.dastine-buybar{bottom:calc(64px + env(safe-area-inset-bottom))!important;visibility:hidden;transform:translateY(calc(100% + 120px))!important}
.dastine-buybar.is-on{visibility:visible;transform:none!important}
@media (max-width:900px){.single-product .dastine-fab{bottom:150px}}
.woocommerce-cart .woocommerce{max-width:1000px;margin:0 auto}
.woocommerce-cart table.shop_table{border:1px solid var(--d-line);border-radius:12px;border-collapse:separate;overflow:hidden}
.woocommerce-cart table.cart img{width:72px;border-radius:8px}
.woocommerce-cart table.cart td.actions .coupon .input-text{border:1px solid #D9CDBD;border-radius:10px;padding:10px 12px;min-width:160px;font-family:inherit}
.woocommerce-cart .button,.woocommerce-cart button.button{border-radius:999px!important;font-family:inherit!important}
.woocommerce-cart .wc-proceed-to-checkout a.checkout-button{background:var(--d-anar)!important;color:#fff!important;border-radius:999px!important;font-size:17px!important;padding:16px!important}
.woocommerce-cart .cart_totals h2{font-size:20px}
.woocommerce-shipping-destination,.woocommerce-shipping-calculator{display:none!important}
.v2-photo--img{border:0!important;padding:0!important;overflow:hidden;background:none!important}
.v2-photo--img img{width:100%!important;height:100%!important;object-fit:cover;opacity:1!important;display:block}
.v2-custom{padding:0 0 72px}
.v2-custom__card{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:36px 40px;border-radius:14px;background:var(--d-ink);color:#F4EDE3!important;text-decoration:none!important;transition:transform .2s}
.v2-custom__card:hover{transform:translateY(-2px)}
.v2-custom__card .v2-eyebrow{color:#E8B9A6!important}
.v2-custom__card h2{font-size:28px;margin:0 0 8px;color:#fff}
.v2-custom__card p{margin:0;font-size:16px;line-height:1.9;color:#E9DFD2}
.v2-custom__go{flex-shrink:0;display:inline-flex;align-items:center;height:50px;padding:0 28px;border-radius:999px;background:#fff;color:var(--d-anar);font-weight:700}
@media (max-width:700px){.v2-custom__card{flex-direction:column;align-items:flex-start;padding:28px 24px}}
.dastine-fab{position:fixed;left:20px;bottom:20px;z-index:70;display:flex;flex-direction:column-reverse;align-items:flex-start;gap:10px}
.dastine-fab summary{list-style:none;width:58px;height:58px;border-radius:50%;background:var(--d-anar);display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 8px 22px rgba(59,42,36,.25)}
.dastine-fab summary::-webkit-details-marker{display:none}
.dastine-fab summary svg{width:26px;height:26px;fill:none;stroke:#fff;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.dastine-fab[open] .dastine-fab__open,.dastine-fab:not([open]) .dastine-fab__close{display:none}
.dastine-fab__list{display:flex;flex-direction:column;gap:10px;margin-bottom:10px}
.dastine-fab__list a{display:flex;align-items:center;gap:10px;text-decoration:none!important;color:var(--d-ink)!important;font-weight:600;font-size:14px}
.dastine-fab__list a span{background:#fff;padding:8px 14px;border-radius:8px;box-shadow:0 4px 14px rgba(59,42,36,.12)}
.dastine-fab__list a i{width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 14px rgba(59,42,36,.15)}
.dastine-fab__list a i svg{width:22px;height:22px;fill:none;stroke:#fff;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
@media (max-width:900px){.dastine-fab{bottom:80px;left:14px}}
@media (max-width:900px){
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description{grid-template-columns:minmax(0,1fr)}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>*{grid-column:1!important;grid-row:auto!important}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>ul{margin-top:0}
.dastine-v2 .dastine-v2hall__halls{flex-wrap:nowrap;overflow-x:auto}
}
</style>
    <?php
}
