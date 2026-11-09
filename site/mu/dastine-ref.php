<?php
/**
 * Plugin Name: Dastine partners
 * Description: Influencer partners — a discount code and a link for each, sales counted per partner and per niche, and niche collection pages.
 */
if (!defined('ABSPATH')) { exit; }

const DASTINE_REF_COOKIE = 'dastine_ref';

function dastine_niches() {
    return array(
        'cats'  => array('label' => 'گربه و حیوانِ خانگی', 'page' => 'cat-lovers'),
        'cafe'  => array('label' => 'آشپزی و کافه', 'page' => 'cafe'),
        'books' => array('label' => 'کتاب‌خوان‌ها', 'page' => 'bookish'),
        'yalda' => array('label' => 'یلدا', 'page' => 'yalda'),
        'other' => array('label' => 'سایر', 'page' => ''),
    );
}

function dastine_partners() {
    $p = get_option('dastine_partners', array());
    return is_array($p) ? $p : array();
}

function dastine_partner_link($slug) {
    $p = dastine_partners()[$slug] ?? null;
    if (!$p) { return ''; }
    $page = dastine_niches()[$p['niche']]['page'] ?? '';
    return add_query_arg('ref', $slug, home_url($page ? '/' . $page . '/' : '/'));
}

function dastine_partner_by_coupon($code) {
    $code = wc_format_coupon_code($code);
    foreach (dastine_partners() as $slug => $p) {
        if (wc_format_coupon_code($p['code']) === $code) { return $slug; }
    }
    return '';
}

/* ---------- visits: ?ref=slug remembers the partner for 30 days ---------- */
add_action('template_redirect', function () {
    if (empty($_GET['ref'])) { return; }
    $slug = sanitize_key(wp_unslash($_GET['ref']));
    if (!isset(dastine_partners()[$slug])) { return; }
    $had = isset($_COOKIE[DASTINE_REF_COOKIE]) && $_COOKIE[DASTINE_REF_COOKIE] === $slug;
    setcookie(DASTINE_REF_COOKIE, $slug, array('expires' => time() + 30 * DAY_IN_SECONDS, 'path' => COOKIEPATH ?: '/', 'secure' => is_ssl(), 'httponly' => true, 'samesite' => 'Lax'));
    $_COOKIE[DASTINE_REF_COOKIE] = $slug;
    if (!$had && !current_user_can('manage_woocommerce')) {
        $v = get_option('dastine_ref_visits', array());
        $v = is_array($v) ? $v : array();
        $v[$slug] = (int) ($v[$slug] ?? 0) + 1;
        update_option('dastine_ref_visits', $v, false);
    }
}, 5);

function dastine_ref_current() {
    $slug = isset($_COOKIE[DASTINE_REF_COOKIE]) ? sanitize_key(wp_unslash($_COOKIE[DASTINE_REF_COOKIE])) : '';
    return isset(dastine_partners()[$slug]) ? $slug : '';
}

/* the partner's code is applied by itself when someone who came by the link adds a piece to the cart */
add_action('woocommerce_add_to_cart', function () {
    $slug = dastine_ref_current();
    if (!$slug || !WC()->cart) { return; }
    $code = wc_format_coupon_code(dastine_partners()[$slug]['code']);
    if ($code && !WC()->cart->has_discount($code) && !WC()->cart->get_applied_coupons()) { WC()->cart->apply_coupon($code); }
}, 20);

/* ---------- which partner an order belongs to: their code first, otherwise their link ---------- */
add_action('woocommerce_checkout_create_order', function ($order) {
    $slug = '';
    foreach ($order->get_coupon_codes() as $c) {
        $slug = dastine_partner_by_coupon($c);
        if ($slug) { break; }
    }
    if (!$slug) { $slug = dastine_ref_current(); }
    if ($slug) { $order->update_meta_data('_dastine_ref', $slug); }
}, 10);

function dastine_ref_order_amount($o) {
    $fee = 0;
    foreach ($o->get_fees() as $f) { $fee += (float) $f->get_total(); }
    return max(0, (float) $o->get_total() - $fee - (float) $o->get_shipping_total());
}

function dastine_ref_report() {
    $rows = array();
    foreach (dastine_partners() as $slug => $p) {
        $rows[$slug] = array('orders' => 0, 'paid' => 0, 'sales' => 0.0);
    }
    $orders = wc_get_orders(array('limit' => 1000, 'date_created' => '>' . (time() - 365 * DAY_IN_SECONDS), 'status' => array_keys(wc_get_order_statuses())));
    foreach ($orders as $o) {
        $slug = (string) $o->get_meta('_dastine_ref');
        if (!$slug || !isset($rows[$slug])) { continue; }
        if (in_array($o->get_status(), array('cancelled', 'failed', 'refunded', 'trash'), true)) { continue; }
        $rows[$slug]['orders']++;
        if (in_array($o->get_status(), array('processing', 'completed'), true)) {
            $rows[$slug]['paid']++;
            $rows[$slug]['sales'] += dastine_ref_order_amount($o);
        }
    }
    return $rows;
}

/* ---------- admin page: WooCommerce › همکاران ---------- */
add_action('admin_menu', function () {
    add_submenu_page('woocommerce', 'همکاران (اینفلوئنسرها)', 'همکاران', 'manage_woocommerce', 'dastine-partners', 'dastine_partners_page');
}, 60);

function dastine_partners_page() {
    if (!current_user_can('manage_woocommerce')) { return; }
    $note = '';
    $list = dastine_partners();
    if (!empty($_POST['dastine_partner_nonce']) && wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['dastine_partner_nonce'])), 'dastine_partner')) {
        $p = wp_unslash($_POST);
        if (!empty($p['delete'])) {
            $slug = sanitize_key($p['delete']);
            if (isset($list[$slug])) {
                $cid = wc_get_coupon_id_by_code($list[$slug]['code']);
                if ($cid) { wp_trash_post($cid); }
                unset($list[$slug]);
                update_option('dastine_partners', $list, false);
                $note = 'حذف شد.';
            }
        } else {
            $ig = ltrim(sanitize_text_field($p['ig'] ?? ''), '@ ');
            $slug = sanitize_key(str_replace('.', '-', $p['slug'] ?? '') ?: str_replace('.', '-', $ig));
            $code = wc_format_coupon_code(sanitize_text_field($p['code'] ?? '') ?: $slug);
            $disc = max(0, min(50, (int) ($p['disc'] ?? 10)));
            $comm = max(0, min(50, (int) ($p['comm'] ?? 10)));
            $niche = array_key_exists($p['niche'] ?? '', dastine_niches()) ? $p['niche'] : 'other';
            if (!$slug || !preg_match('/^[a-z0-9_-]{2,30}$/', $slug)) {
                $note = 'نامِ کوتاهِ لینک فقط حروفِ انگلیسی، عدد و خط تیره باشد.';
            } elseif (!isset($list[$slug]) && wc_get_coupon_id_by_code($code)) {
                $note = 'این کدِ تخفیف قبلاً وجود دارد؛ یک کدِ دیگر بنویس.';
            } else {
                $cid = wc_get_coupon_id_by_code($list[$slug]['code'] ?? $code);
                $c = new WC_Coupon($cid ?: 0);
                $c->set_code($code);
                $c->set_discount_type('percent');
                $c->set_amount($disc);
                $c->set_individual_use(true);
                $c->set_usage_limit_per_user(1);
                $c->set_description('همکار: ' . sanitize_text_field($p['name'] ?? $slug));
                $c->save();
                $list[$slug] = array('name' => sanitize_text_field($p['name'] ?? ''), 'ig' => $ig, 'niche' => $niche, 'code' => $code,
                    'disc' => $disc, 'comm' => $comm, 'since' => $list[$slug]['since'] ?? current_time('Y-m-d'));
                update_option('dastine_partners', $list, false);
                $note = 'ذخیره شد. لینک و کد در جدولِ پایین است.';
            }
        }
    }
    $visits = get_option('dastine_ref_visits', array());
    $rep = dastine_ref_report();
    $niches = dastine_niches();
    $fa = function ($s) { return function_exists('dastine_fa') ? dastine_fa($s) : $s; };
    $num = function ($n) use ($fa) { return $fa(number_format((float) $n)); };
    echo '<div class="wrap" dir="rtl"><h1>همکاران (اینفلوئنسرها)</h1>';
    if ($note) { echo '<div class="notice notice-info"><p>' . esc_html($note) . '</p></div>'; }
    echo '<p>برای هر اینفلوئنسر یک کدِ تخفیف و یک لینک ساخته می‌شود. هر کس با لینک بیاید، کد خودش روی سبدش می‌نشیند؛ هر کس هم کد را دستی بزند، سفارشش به همان همکار می‌رسد. فروش فقط وقتی حساب می‌شود که پرداخت تأیید شده باشد (در حال انجام یا تکمیل‌شده).</p>';

    // per-niche totals
    $by = array();
    foreach ($list as $slug => $p) {
        $n = $p['niche'];
        $by[$n] = $by[$n] ?? array('people' => 0, 'visits' => 0, 'orders' => 0, 'paid' => 0, 'sales' => 0);
        $by[$n]['people']++;
        $by[$n]['visits'] += (int) ($visits[$slug] ?? 0);
        foreach (array('orders', 'paid', 'sales') as $k) { $by[$n][$k] += $rep[$slug][$k]; }
    }
    if ($by) {
        echo '<h2>هر حوزه</h2><table class="widefat striped" style="max-width:900px"><thead><tr><th>حوزه</th><th>همکار</th><th>بازدید از لینک</th><th>سفارش</th><th>پرداخت‌شده</th><th>فروش (تومان)</th><th>فروش به ازای هر ۱۰۰ بازدید</th></tr></thead><tbody>';
        foreach ($by as $n => $r) {
            echo '<tr><td>' . esc_html($niches[$n]['label'] ?? $n) . '</td><td>' . esc_html($fa($r['people'])) . '</td><td>' . esc_html($fa($r['visits'])) . '</td><td>' . esc_html($fa($r['orders'])) . '</td><td>' . esc_html($fa($r['paid'])) . '</td><td>' . esc_html($num($r['sales'])) . '</td><td>' . esc_html($r['visits'] ? $fa(round(100 * $r['paid'] / $r['visits'], 1)) : '—') . '</td></tr>';
        }
        echo '</tbody></table>';
    }

    echo '<h2>هر همکار</h2><table class="widefat striped"><thead><tr><th>نام</th><th>اینستاگرام</th><th>حوزه</th><th>کدِ تخفیف</th><th>لینک</th><th>بازدید</th><th>سفارش</th><th>پرداخت‌شده</th><th>فروش (تومان)</th><th>سهمِ همکار (تومان)</th><th></th></tr></thead><tbody>';
    if (!$list) { echo '<tr><td colspan="11">هنوز همکاری ثبت نشده.</td></tr>'; }
    foreach ($list as $slug => $p) {
        $r = $rep[$slug];
        $link = dastine_partner_link($slug);
        echo '<tr><td>' . esc_html($p['name']) . '</td><td>' . ($p['ig'] ? '<a href="https://www.instagram.com/' . esc_attr($p['ig']) . '/" target="_blank" rel="noopener">@' . esc_html($p['ig']) . '</a>' : '') . '</td>'
            . '<td>' . esc_html($niches[$p['niche']]['label'] ?? '') . '</td><td><code>' . esc_html(strtoupper($p['code'])) . '</code> (' . esc_html($fa($p['disc'])) . '٪)</td>'
            . '<td><input type="text" readonly value="' . esc_attr($link) . '" onclick="this.select()" style="width:260px;direction:ltr"></td>'
            . '<td>' . esc_html($fa((int) ($visits[$slug] ?? 0))) . '</td><td>' . esc_html($fa($r['orders'])) . '</td><td>' . esc_html($fa($r['paid'])) . '</td><td>' . esc_html($num($r['sales'])) . '</td>'
            . '<td>' . esc_html($num(round($r['sales'] * $p['comm'] / 100))) . ' (' . esc_html($fa($p['comm'])) . '٪)</td>'
            . '<td><form method="post" onsubmit="return confirm(\'حذف شود؟ کدِ تخفیفش هم غیرفعال می‌شود.\')">' . wp_nonce_field('dastine_partner', 'dastine_partner_nonce', true, false) . '<input type="hidden" name="delete" value="' . esc_attr($slug) . '"><button class="button-link-delete" type="submit">حذف</button></form></td></tr>';
    }
    echo '</tbody></table>';

    $opts = '';
    foreach ($niches as $k => $n) { $opts .= '<option value="' . esc_attr($k) . '">' . esc_html($n['label']) . '</option>'; }
    echo '<h2>همکارِ تازه (یا ویرایش با همان نامِ لینک)</h2><form method="post"><table class="form-table" role="presentation">'
        . wp_nonce_field('dastine_partner', 'dastine_partner_nonce', true, false)
        . '<tr><th>نام</th><td><input name="name" class="regular-text" required></td></tr>'
        . '<tr><th>آیدیِ اینستاگرام</th><td><input name="ig" class="regular-text" dir="ltr" placeholder="sara.cats"></td></tr>'
        . '<tr><th>حوزه</th><td><select name="niche">' . $opts . '</select> <span class="description">لینک به صفحه‌ی همین حوزه می‌رود.</span></td></tr>'
        . '<tr><th>نامِ کوتاهِ لینک</th><td><input name="slug" dir="ltr" placeholder="sara"> <span class="description">خالی بماند، از آیدی ساخته می‌شود. فقط انگلیسی.</span></td></tr>'
        . '<tr><th>کدِ تخفیف</th><td><input name="code" dir="ltr" placeholder="SARA"> <span class="description">خالی بماند، همان نامِ کوتاه می‌شود.</span></td></tr>'
        . '<tr><th>درصدِ تخفیف برای مشتری</th><td><input name="disc" type="number" min="0" max="50" value="10" style="width:80px"></td></tr>'
        . '<tr><th>درصدِ سهمِ همکار</th><td><input name="comm" type="number" min="0" max="50" value="10" style="width:80px"></td></tr>'
        . '</table><p><button class="button button-primary">ذخیره</button></p></form></div>';
}

/* ---------- niche collection pages ---------- */
function dastine_niche_ids($tags) {
    $ids = array();
    foreach (array_filter(array_map('trim', explode(',', (string) $tags))) as $name) {
        $t = get_term_by('name', $name, 'product_tag');
        if ($t) { $ids[] = (int) $t->term_id; }
    }
    if (!$ids) { return array(); }
    $found = get_posts(array('post_type' => 'product', 'post_status' => 'publish', 'numberposts' => 60, 'fields' => 'ids',
        'tax_query' => array(array('taxonomy' => 'product_tag', 'field' => 'term_id', 'terms' => $ids))));
    $rank = function_exists('dastine_ranked_ids') ? dastine_ranked_ids(200) : array();
    $pos = array_flip($rank);
    usort($found, function ($a, $b) use ($pos) { return ($pos[$a] ?? 999) <=> ($pos[$b] ?? 999); });
    return $found;
}

add_shortcode('dastine_niche', function ($atts) {
    $a = shortcode_atts(array('tags' => '', 'intro' => ''), $atts);
    $out = '<div class="dastine-niche">';
    if ($a['intro'] !== '') { $out .= '<p class="dastine-niche__intro">' . esc_html($a['intro']) . '</p>'; }
    $slug = dastine_ref_current();
    if ($slug) {
        $p = dastine_partners()[$slug];
        $out .= '<p class="dastine-niche__gift">از طرفِ ' . esc_html($p['name']) . ' آمده‌ای؛ ' . esc_html(function_exists('dastine_fa') ? dastine_fa($p['disc']) : $p['disc']) . '٪ تخفیف با کدِ <b dir="ltr">' . esc_html(strtoupper($p['code'])) . '</b> خودش روی سبدت می‌نشیند.</p>';
    }
    $ids = dastine_niche_ids($a['tags']);
    $out .= $ids && function_exists('dastine_render_loop') ? dastine_render_loop($ids, 'niche', 4) : '<p class="dastine-empty">به‌زودی قطعه‌های این مجموعه این‌جا می‌آیند.</p>';
    return $out . '</div>';
});

add_action('init', function () {
    if (get_option('dastine_niche_pages') === '1') { return; }
    $pages = array(
        array('cat-lovers', 'برای گربه‌دوست‌ها', 'گربه,حیوان,جانور,ماهی قرمز,ماهی,حلزون', 'publish',
            'گربه‌ای که روی گیره‌ی مو چرت می‌زند، ماهیِ قرمزی که هیچ‌وقت آبش عوض نمی‌شود و حلزونی که عجله ندارد؛ قطعه‌هایی برای کسی که دلش با حیوان‌ها گرم است.'),
        array('cafe', 'برای اهلِ آشپزی و کافه', 'میوه,خوراکی,پسته,انار,گیلاس,هندوانه,توت‌فرنگی,به', 'publish',
            'پسته‌ای که می‌خندد، اناری که دانه‌دانه ساخته شده و گیلاس‌هایی که جفت آمده‌اند؛ خوردنی نیستند، ولی کنارِ فنجان و بشقاب دلبری می‌کنند.'),
        array('bookish', 'برای کتاب‌خوان‌ها', 'مینیمال,رمانتیک,ستاره,آسمان,احساسی', 'publish',
            'قطعه‌های آرام و کم‌حرف، برای کسی که لای صفحه‌ها زندگی می‌کند؛ هم‌نشینِ چای، چراغ‌مطالعه و نشان‌کتاب.'),
        array('yalda', 'کادوی یلدا', 'یلدا,انار,هندوانه', 'draft',
            'بلندترین شب را با یک انار یا یک قاچ هندوانه‌ی همیشگی کادو بده؛ دست‌ساز، با کارتِ شناسنامه.'),
    );
    foreach ($pages as $p) {
        if (get_page_by_path($p[0], OBJECT, 'page')) { continue; }
        wp_insert_post(array('post_type' => 'page', 'post_status' => $p[3], 'post_name' => $p[0], 'post_title' => $p[1],
            'post_content' => "<!-- wp:shortcode -->\n[dastine_niche tags=\"" . $p[2] . "\" intro=\"" . $p[4] . "\"]\n<!-- /wp:shortcode -->"));
    }
    update_option('dastine_niche_pages', '1');
});

add_action('wp_head', function () {
    echo '<style id="dastine-niche-css">.dastine-niche__intro{font-size:18px;line-height:2.1;max-width:720px;color:var(--d-ink,#2b211c);margin:0 0 22px}'
        . '.dastine-niche__gift{background:var(--d-katan,#F3EBE1);border-radius:14px;padding:12px 16px;margin:0 0 24px;font-size:15px}</style>';
});
