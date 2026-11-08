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
            . '<dl><div><dt>سازنده</dt><dd>' . esc_html($maker !== '' ? $maker : '[نامِ سازنده]') . '</dd></div>'
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
.dastine-support{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:26px 0}
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
@media (max-width:900px){
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description{grid-template-columns:minmax(0,1fr)}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>*{grid-column:1!important;grid-row:auto!important}
.dastine-v2 .dastine-product .woocommerce-Tabs-panel--description>ul{margin-top:0}
.dastine-v2 .dastine-v2hall__halls{flex-wrap:nowrap;overflow-x:auto}
}
</style>
    <?php
}
