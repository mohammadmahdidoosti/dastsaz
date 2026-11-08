<?php
/*
 * Plugin Name: Dastine shop
 * Description: Product page (engraving, making time, gallery look), simple checkout for Iran, card-to-card payment page with receipt upload, Persian digits.
 * Version: 1.0.0
 */
if (!defined('ABSPATH')) { exit; }

/* ---------- Persian digits ---------- */
function dastine_fa($s) {
    return strtr((string) $s, array('0' => '۰', '1' => '۱', '2' => '۲', '3' => '۳', '4' => '۴', '5' => '۵', '6' => '۶', '7' => '۷', '8' => '۸', '9' => '۹', ',' => '٬'));
}
function dastine_fa_html($html) {
    // Only the visible text: leave tags and HTML codes (like &#x62A;) untouched.
    $parts = preg_split('/(<[^>]*>|&#?[a-zA-Z0-9]+;)/', (string) $html, -1, PREG_SPLIT_DELIM_CAPTURE);
    foreach ($parts as $i => $p) {
        if ($i % 2 === 0) { $parts[$i] = dastine_fa($p); }
    }
    return implode('', $parts);
}
add_filter('wc_price', 'dastine_fa_html', 99);

/* ---------- one-time shop setup (runs once, by an admin) ---------- */
add_action('admin_init', function () {
    if (get_option('dastine_shop_setup') === '2' || !current_user_can('manage_woocommerce') || !class_exists('WC_Shipping_Zones')) {
        return;
    }
    // Sell and ship only inside Iran; simple checkout fields.
    update_option('woocommerce_allowed_countries', 'specific');
    update_option('woocommerce_specific_allowed_countries', array('IR'));
    update_option('woocommerce_ship_to_countries', '');
    update_option('woocommerce_checkout_company_field', 'hidden');
    update_option('woocommerce_checkout_address_2_field', 'hidden');
    update_option('woocommerce_checkout_phone_field', 'required');
    update_option('woocommerce_enable_guest_checkout', 'yes');
    update_option('woocommerce_enable_checkout_login_reminder', 'no');
    update_option('woocommerce_enable_signup_and_login_from_checkout', 'no');
    update_option('woocommerce_enable_reviews', 'no');
    // Card-to-card (the bank transfer gateway). The card itself is entered by the owner in WooCommerce › Payments.
    $bacs = (array) get_option('woocommerce_bacs_settings', array());
    $bacs = array_merge($bacs, array(
        'enabled' => 'yes',
        'title' => 'کارت‌به‌کارت',
        'description' => 'بعد از ثبتِ سفارش، شماره‌ی کارت و مبلغ را می‌بینی؛ واریز کن و رسیدش را همان‌جا بفرست.',
        'instructions' => 'رسیدِ واریز را در صفحه‌ی پرداخت بفرست تا ساختِ قطعه‌ات شروع شود.',
    ));
    update_option('woocommerce_bacs_settings', $bacs);
    // Shipping: one zone for Iran with post. The price is set by the owner later.
    $has = false;
    foreach (WC_Shipping_Zones::get_zones() as $z) {
        if (($z['zone_name'] ?? '') === 'ایران') { $has = true; }
    }
    if (!$has) {
        $zone = new WC_Shipping_Zone();
        $zone->set_zone_name('ایران');
        $zone->add_location('IR', 'country');
        $zone->save();
        $iid = $zone->add_shipping_method('flat_rate');
        $opt = 'woocommerce_flat_rate_' . $iid . '_settings';
        update_option($opt, array('title' => 'تیپاکس (پس‌کرایه)', 'tax_status' => 'none', 'cost' => '0'));
    }
    // The payment page.
    if (!get_page_by_path('pay')) {
        wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish', 'post_name' => 'pay', 'post_title' => 'پرداخت',
            'post_content' => "<!-- wp:shortcode -->\n[dastine_pay]\n<!-- /wp:shortcode -->"));
    }
    update_option('dastine_shop_setup', '2');
});

/* ---------- product page ---------- */
add_filter('woocommerce_product_tabs', function ($tabs) {
    unset($tabs['reviews'], $tabs['additional_information']);
    if (isset($tabs['description'])) { $tabs['description']['title'] = 'قصه و جزئیات'; }
    return $tabs;
}, 98);
add_action('init', function () {
    remove_action('woocommerce_single_product_summary', 'woocommerce_template_single_meta', 40);
    remove_action('woocommerce_single_product_summary', 'woocommerce_template_single_rating', 10);
});
add_action('woocommerce_single_product_summary', function () {
    $days = trim((string) get_post_meta(get_the_ID(), 'dastine_days', true));
    $make = $days !== '' ? 'ساخته می‌شود در حدودِ ' . esc_html(dastine_fa($days)) . ' روزِ کاری' : 'بعد از سفارشِ تو با دست ساخته می‌شود';
    echo '<ul class="dastine-promise">'
        . '<li><b>دست‌ساز</b><span>' . $make . '</span></li>'
        . '<li><b>شناسنامه‌دار</b><span>با کارتِ شناسنامه: اسمِ سازنده، شماره و تاریخِ ساخت</span></li>'
        . '<li><b>ارسال</b><span>با تیپاکس به سراسرِ ایران؛ هزینه‌ی ارسال پس‌کرایه</span></li>'
        . '</ul>';
}, 25);

/* Engraving: free, optional, carried to the cart and the order. */
add_action('woocommerce_before_add_to_cart_button', function () {
    echo '<div class="dastine-engrave"><label for="dastine_engrave">حکاکیِ دلخواه <small>(رایگان، اختیاری)</small></label>'
        . '<input type="text" id="dastine_engrave" name="dastine_engrave" maxlength="40" placeholder="یک اسم، یک تاریخ یا یک مصرع" autocomplete="off"></div>';
});
add_filter('woocommerce_add_cart_item_data', function ($data) {
    $v = isset($_POST['dastine_engrave']) ? trim(sanitize_text_field(wp_unslash($_POST['dastine_engrave']))) : '';
    if ($v !== '') {
        $data['dastine_engrave'] = mb_substr($v, 0, 40);
        $data['dastine_key'] = md5($v . microtime());
    }
    return $data;
});
add_filter('woocommerce_get_item_data', function ($items, $cart_item) {
    if (!empty($cart_item['dastine_engrave'])) {
        $items[] = array('key' => 'حکاکی', 'value' => esc_html($cart_item['dastine_engrave']));
    }
    return $items;
}, 10, 2);
add_action('woocommerce_checkout_create_order_line_item', function ($item, $key, $values) {
    if (!empty($values['dastine_engrave'])) {
        $item->add_meta_data('حکاکی', $values['dastine_engrave']);
    }
}, 10, 3);

/* Shop and halls: the engine decides the order (unless the visitor sorts). */
add_action('woocommerce_product_query', function ($q) {
    if (is_admin() || !function_exists('dastine_ranked_ids') || !empty($_GET['orderby']) || is_search()) { return; }
    $ids = dastine_ranked_ids(300);
    if ($ids) {
        $q->set('post__in', $ids);
        $q->set('orderby', 'post__in');
    }
});
add_filter('loop_shop_per_page', function () { return 24; }, 20);

/* ---------- card-to-card payment page ---------- */
add_filter('woocommerce_get_checkout_order_received_url', function ($url, $order) {
    if ($order && $order->get_payment_method() === 'bacs') {
        $page = get_page_by_path('pay');
        if ($page) {
            return add_query_arg(array('order' => $order->get_id(), 'key' => $order->get_order_key()), get_permalink($page));
        }
    }
    return $url;
}, 10, 2);

function dastine_pay_order() {
    $id = isset($_REQUEST['order']) ? absint($_REQUEST['order']) : 0;
    $key = isset($_REQUEST['key']) ? sanitize_text_field(wp_unslash($_REQUEST['key'])) : '';
    $order = $id ? wc_get_order($id) : null;
    if (!$order || !$key || !hash_equals($order->get_order_key(), $key)) { return null; }
    return $order;
}

add_action('template_redirect', function () {
    if (empty($_POST['dastine_pay']) || !is_page('pay')) { return; }
    $order = dastine_pay_order();
    if (!$order || !isset($_POST['_dpn']) || !wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['_dpn'])), 'dastine_pay_' . $order->get_id())) {
        wp_die('این لینک معتبر نیست.', '', array('response' => 403));
    }
    if (!empty($_POST['website'])) { wp_safe_redirect(home_url('/')); exit; }   // robots fill hidden fields
    $code = isset($_POST['paycode']) ? trim(sanitize_text_field(wp_unslash($_POST['paycode']))) : '';
    $att = 0;
    $err = '';
    if (!empty($_FILES['receipt']['name'])) {
        $f = $_FILES['receipt'];
        $type = wp_check_filetype($f['name']);
        if (!in_array($type['ext'], array('jpg', 'jpeg', 'png', 'webp'), true) || $f['size'] > 4 * MB_IN_BYTES || !empty($f['error'])) {
            $err = 'file';
        } else {
            require_once ABSPATH . 'wp-admin/includes/file.php';
            require_once ABSPATH . 'wp-admin/includes/image.php';
            require_once ABSPATH . 'wp-admin/includes/media.php';
            $att = media_handle_upload('receipt', 0, array('post_title' => 'رسید سفارش ' . $order->get_order_number()));
            if (is_wp_error($att)) { $att = 0; $err = 'file'; }
        }
    }
    if (!$att && $code === '') { $err = $err ?: 'empty'; }
    if ($err) {
        wp_safe_redirect(add_query_arg(array('order' => $order->get_id(), 'key' => $order->get_order_key(), 'err' => $err), get_permalink()));
        exit;
    }
    if ($att) { $order->update_meta_data('_dastine_receipt', $att); }
    if ($code !== '') { $order->update_meta_data('_dastine_paycode', mb_substr($code, 0, 60)); }
    $order->update_meta_data('_dastine_paid_at', current_time('mysql'));
    if ($order->get_status() === 'pending') { $order->update_status('on-hold'); }
    $note = 'مشتری پرداختِ کارت‌به‌کارت را ثبت کرد.' . ($code !== '' ? ' شماره پیگیری: ' . $code : '') . ($att ? ' رسید: ' . wp_get_attachment_url($att) : '');
    $order->add_order_note($note);
    $order->save();
    wp_mail(get_option('admin_email'), 'رسید پرداخت · سفارش ' . $order->get_order_number(),
        $note . "\n\nمبلغ: " . wp_strip_all_tags(wc_price($order->get_total())) . "\nمشتری: " . $order->get_formatted_billing_full_name()
        . ' · ' . $order->get_billing_phone() . "\n\nبرای تأیید: " . admin_url('post.php?post=' . $order->get_id() . '&action=edit'));
    wp_safe_redirect(add_query_arg(array('order' => $order->get_id(), 'key' => $order->get_order_key(), 'done' => 1), get_permalink()));
    exit;
});

add_shortcode('dastine_pay', function () {
    $order = dastine_pay_order();
    if (!$order) {
        return '<div class="dastine-pay"><p class="dastine-pay__muted">لینکِ پرداخت کامل نیست. اگر سفارش داده‌ای، از لینکِ داخلِ ایمیل یا پیامکِ سفارش وارد شو.</p></div>';
    }
    $items = $order->get_items();
    $first = $items ? reset($items) : null;
    $thumb = '';
    $names = array();
    foreach ($items as $it) { $names[] = $it->get_name(); }
    if ($first && $first->get_product()) {
        $thumb = get_the_post_thumbnail_url($first->get_product_id(), 'thumbnail');
    }
    $head = '<div class="dastine-pay__order">' . ($thumb ? '<img src="' . esc_url($thumb) . '" alt="">' : '')
        . '<div><span class="dastine-pay__muted">سفارشِ ' . esc_html(dastine_fa($order->get_order_number())) . '</span><b>' . esc_html(implode('، ', $names)) . '</b></div></div>';
    $paid = $order->get_meta('_dastine_paid_at');
    if (!empty($_GET['done']) || $paid) {
        return '<div class="dastine-pay">' . $head . '<div class="dastine-pay__ok"><h2>پرداختت ثبت شد</h2>'
            . '<p>رسیدت به دستِ ما رسید. بعد از تأیید، ساختِ قطعه‌ات شروع می‌شود و خبرت می‌کنیم.</p>'
            . '<p class="dastine-pay__muted">شماره‌ی سفارش را نگه دار: ' . esc_html(dastine_fa($order->get_order_number())) . '</p>'
            . '<a class="dastine-btn dastine-btn--anar" href="' . esc_url(home_url('/')) . '">بازگشت به گالری</a></div></div>';
    }
    $acc = (array) get_option('woocommerce_bacs_accounts', array());
    $a = $acc ? (array) reset($acc) : array();
    $card = preg_replace('/\D+/', '', (string) ($a['account_number'] ?? ''));
    $card_fmt = $card ? implode('-', str_split($card, 4)) : '';
    $total = (int) round((float) $order->get_total());
    $rows = '<div class="dastine-pay__row"><span>مبلغ</span><b>' . wp_kses_post(wc_price($order->get_total())) . '</b><button type="button" class="dastine-copy" data-copy="' . esc_attr($total) . '">کپی</button></div>';
    if (!empty($a['bank_name'])) { $rows .= '<div class="dastine-pay__row"><span>بانک</span><b>' . esc_html($a['bank_name']) . '</b></div>'; }
    if (!empty($a['account_name'])) { $rows .= '<div class="dastine-pay__row"><span>به نامِ</span><b>' . esc_html($a['account_name']) . '</b></div>'; }
    $rows .= $card
        ? '<div class="dastine-pay__row dastine-pay__row--card"><span>شماره‌ی کارت</span><b dir="ltr">' . esc_html(dastine_fa($card_fmt)) . '</b><button type="button" class="dastine-copy" data-copy="' . esc_attr($card) . '">کپی</button></div>'
        : '<div class="dastine-pay__row"><span>شماره‌ی کارت</span><b>به‌زودی</b></div>';
    $err = isset($_GET['err']) ? sanitize_key($_GET['err']) : '';
    $msg = $err === 'file' ? '<p class="dastine-pay__err">تصویرِ رسید باید JPG، PNG یا WEBP و کمتر از ۴ مگابایت باشد.</p>'
        : ($err === 'empty' ? '<p class="dastine-pay__err">تصویرِ رسید یا شماره‌ی پیگیری را بفرست.</p>' : '');
    $form = '<form class="dastine-pay__form" method="post" enctype="multipart/form-data">'
        . wp_nonce_field('dastine_pay_' . $order->get_id(), '_dpn', true, false)
        . '<input type="hidden" name="dastine_pay" value="1"><input type="hidden" name="order" value="' . esc_attr($order->get_id()) . '"><input type="hidden" name="key" value="' . esc_attr($order->get_order_key()) . '">'
        . '<input type="text" name="website" tabindex="-1" autocomplete="off" class="dastine-hp" aria-hidden="true">'
        . '<label class="dastine-drop"><input type="file" name="receipt" accept="image/jpeg,image/png,image/webp"><span class="dastine-drop__t">تصویرِ رسید را این‌جا بگذار یا بزن تا انتخاب کنی</span><span class="dastine-pay__muted">JPG، PNG یا WEBP، حداکثر ۴ مگابایت</span></label>'
        . '<div class="dastine-or"><span>یا</span></div>'
        . '<label class="dastine-field"><span>شماره‌ی پیگیری یا چهار رقمِ آخرِ کارتِ خودت</span><input type="text" name="paycode" inputmode="numeric" maxlength="60" placeholder="مثلاً ۱۲۳۴۵۶"></label>'
        . $msg
        . '<button type="submit" class="dastine-btn dastine-btn--anar dastine-btn--block">ثبتِ پرداخت</button></form>';
    return '<div class="dastine-pay">' . $head
        . '<h1>یک قدم تا ساختِ قطعه‌ات</h1><p class="dastine-pay__muted">مبلغ را به این کارت واریز کن، بعد رسید یا شماره‌ی پیگیری را بفرست.</p>'
        . '<div class="dastine-pay__card">' . $rows . '</div>' . $form . '</div>';
});

/* small helpers on the front: copy buttons, receipt file name, sticky buy bar on phones */
add_action('wp_footer', function () {
    if (is_admin()) { return; }
    ?>
<script id="dastine-shop">
(function(){
  document.addEventListener('click',function(e){var b=e.target.closest('.dastine-copy');if(!b)return;
    var v=b.getAttribute('data-copy');var done=function(){var t=b.textContent;b.textContent='کپی شد';setTimeout(function(){b.textContent=t;},1500);};
    if(navigator.clipboard){navigator.clipboard.writeText(v).then(done,done);}else{var i=document.createElement('input');i.value=v;document.body.appendChild(i);i.select();try{document.execCommand('copy');}catch(x){}i.remove();done();}});
  document.addEventListener('change',function(e){var f=e.target;if(f.matches&&f.matches('.dastine-drop input[type=file]')&&f.files&&f.files[0]){f.closest('.dastine-drop').classList.add('has-file');f.parentNode.querySelector('.dastine-drop__t').textContent=f.files[0].name;}});
  var form=document.querySelector('.single-product form.cart'),btn=form&&form.querySelector('.single_add_to_cart_button');
  if(btn&&'IntersectionObserver' in window&&window.matchMedia('(max-width: 781px)').matches){
    var price=document.querySelector('.single-product .summary .price');
    var bar=document.createElement('div');bar.className='dastine-buybar';
    bar.innerHTML='<span class="dastine-buybar__p"></span><button type="button" class="dastine-btn dastine-btn--anar">افزودن به سبد</button>';
    if(price)bar.querySelector('.dastine-buybar__p').innerHTML=price.innerHTML;
    bar.querySelector('button').addEventListener('click',function(){btn.click();});
    document.body.appendChild(bar);
    new IntersectionObserver(function(es){bar.classList.toggle('is-on',!es[0].isIntersecting);}).observe(form);
  }
})();
</script>
    <?php
}, 98);
