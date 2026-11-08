<?php
/**
 * Dastine SMS through Jibit (approved pattern templates).
 *
 * Customer: order placed, payment confirmed (processing), shipped (completed).
 * Owner: a payment receipt arrived.
 * Keys are entered by the owner on WooCommerce › پیامک دستینه; they are never shown again.
 * Each message goes once per order, in the background (Action Scheduler).
 */

const DASTINE_SMS_OPT = 'dastine_sms';
const DASTINE_SMS_BASE = 'https://napi.jibit.ir/pulse/api/v1/';

function dastine_sms_cfg() {
    $d = array(
        'on' => '0', 'api_key' => '', 'secret_key' => '', 'sender' => '9890000476', 'admin_phone' => '09100291903',
        'tpl_placed' => 'fa144040-d9df-46a8-b2ba-3ce13717657a', 'tpl_paid' => 'd55c6bae-0768-4273-b356-ac229b14d278',
        'tpl_shipped' => '99465b55-ce62-4003-add9-613880e37fd3', 'tpl_receipt' => 'cadc49b6-d416-4b9d-be70-7c589f14e562',
        'tpl_otp' => 'cdc88422-a005-48b0-b9d9-870c0974a100',
    );
    $o = get_option(DASTINE_SMS_OPT, array());
    return array_merge($d, is_array($o) ? $o : array());
}

/** 09…, 9…, +98…, 0098…, Persian digits → 989xxxxxxxxx (or '' if not a mobile). */
function dastine_sms_phone($p) {
    $p = strtr((string) $p, array('۰' => '0', '۱' => '1', '۲' => '2', '۳' => '3', '۴' => '4', '۵' => '5', '۶' => '6', '۷' => '7', '۸' => '8', '۹' => '9',
        '٠' => '0', '١' => '1', '٢' => '2', '٣' => '3', '٤' => '4', '٥' => '5', '٦' => '6', '٧' => '7', '٨' => '8', '٩' => '9'));
    $d = preg_replace('/\D+/', '', $p);
    if (strpos($d, '0098') === 0) { $d = substr($d, 2); }
    elseif (strpos($d, '09') === 0) { $d = '98' . substr($d, 1); }
    elseif (strpos($d, '9') === 0 && strlen($d) === 10) { $d = '98' . $d; }
    return preg_match('/^989\d{9}$/', $d) ? $d : '';
}

function dastine_sms_token($cfg, $fresh = false) {
    $t = get_transient('dastine_sms_token');
    if ($t && !$fresh) { return $t; }
    $r = wp_remote_post(DASTINE_SMS_BASE . 'auth/authenticate', array('timeout' => 20,
        'headers' => array('Content-Type' => 'application/json', 'Accept' => 'application/json'),
        'body' => wp_json_encode(array('api_key' => $cfg['api_key'], 'secret_key' => $cfg['secret_key']))));
    if (is_wp_error($r)) { return $r; }
    $j = json_decode((string) wp_remote_retrieve_body($r), true);
    if (empty($j['access_token'])) {
        return new WP_Error('dastine_sms', 'کلیدهای جیبیت پذیرفته نشد (HTTP ' . wp_remote_retrieve_response_code($r) . ')');
    }
    set_transient('dastine_sms_token', $j['access_token'], 50 * MINUTE_IN_SECONDS);
    return $j['access_token'];
}

/** One pattern SMS. Returns true or WP_Error. */
function dastine_sms_send($to, $template, $params) {
    $cfg = dastine_sms_cfg();
    $to = dastine_sms_phone($to);
    if ($to === '' || $template === '' || $cfg['api_key'] === '' || $cfg['secret_key'] === '') {
        return new WP_Error('dastine_sms', 'شماره، قالب یا کلیدها تنظیم نیست');
    }
    $body = array('receptor' => $to, 'template' => $template, 'params' => (object) array_map('strval', $params),
        'client_message_id' => 'dst-' . wp_generate_uuid4());
    if ($cfg['sender'] !== '') { $body['sender'] = $cfg['sender']; }
    for ($try = 0; $try < 2; $try++) {
        $tok = dastine_sms_token($cfg, $try > 0);
        if (is_wp_error($tok)) { return $tok; }
        $r = wp_remote_post(DASTINE_SMS_BASE . 'message/sms/pattern/send', array('timeout' => 20,
            'headers' => array('Content-Type' => 'application/json; charset=utf-8', 'Accept' => 'application/json', 'Authorization' => 'Bearer ' . $tok),
            'body' => wp_json_encode($body)));
        if (is_wp_error($r)) { return $r; }
        $code = (int) wp_remote_retrieve_response_code($r);
        if ($code === 401 && $try === 0) { continue; }
        $j = json_decode((string) wp_remote_retrieve_body($r), true);
        $st = is_array($j) ? strtoupper((string) ($j['status'] ?? '')) : '';
        if ($code >= 200 && $code < 300 && !in_array($st, array('FAILED', 'REJECTED', 'ERROR'), true)) { return true; }
        $msg = is_array($j) ? (string) ($j['message'] ?? ($j['errors'][0]['message'] ?? '')) : '';
        return new WP_Error('dastine_sms', 'جیبیت: HTTP ' . $code . ($msg !== '' ? ' — ' . $msg : ''));
    }
    return new WP_Error('dastine_sms', 'کلیدهای جیبیت پذیرفته نشد');
}

/* ---------- orders ---------- */
function dastine_sms_queue($order, $kind) {
    $cfg = dastine_sms_cfg();
    if ($cfg['on'] !== '1' || !$order) { return; }
    if ($order->get_meta('_dastine_sms_' . $kind)) { return; }
    $order->update_meta_data('_dastine_sms_' . $kind, 'queued');
    $order->save_meta_data();
    if (function_exists('as_enqueue_async_action')) {
        as_enqueue_async_action('dastine_sms_job', array($order->get_id(), $kind), 'dastine');
    } else {
        dastine_sms_job($order->get_id(), $kind);
    }
}

function dastine_sms_job($order_id, $kind) {
    $order = wc_get_order($order_id);
    if (!$order) { return; }
    $cfg = dastine_sms_cfg();
    $to = $kind === 'receipt' ? $cfg['admin_phone'] : $order->get_billing_phone();
    $res = dastine_sms_send($to, (string) ($cfg['tpl_' . $kind] ?? ''), array('order_id' => $order->get_order_number()));
    $labels = array('placed' => 'ثبت سفارش', 'paid' => 'تأیید پرداخت', 'shipped' => 'ارسال', 'receipt' => 'رسید (به مدیر)');
    $label = $labels[$kind] ?? $kind;
    if (is_wp_error($res)) {
        $order->update_meta_data('_dastine_sms_' . $kind, 'failed');
        $order->add_order_note('پیامک «' . $label . '» نرفت: ' . $res->get_error_message());
        update_option('dastine_sms_last_error', current_time('mysql') . ' · ' . $res->get_error_message(), false);
    } else {
        $order->update_meta_data('_dastine_sms_' . $kind, 'sent');
        $order->add_order_note('پیامک «' . $label . '» فرستاده شد.');
    }
    $order->save();
}
add_action('dastine_sms_job', 'dastine_sms_job', 10, 2);

add_action('woocommerce_checkout_order_processed', function ($id) { dastine_sms_queue(wc_get_order($id), 'placed'); }, 20);
add_action('woocommerce_store_api_checkout_order_processed', function ($order) { dastine_sms_queue($order, 'placed'); }, 20);
add_action('woocommerce_order_status_processing', function ($id) { dastine_sms_queue(wc_get_order($id), 'paid'); });
add_action('woocommerce_order_status_completed', function ($id) { dastine_sms_queue(wc_get_order($id), 'shipped'); });
/* the payment page stores _dastine_paid_at when a receipt or tracking code arrives */
add_action('woocommerce_after_order_object_save', function ($order) {
    if ($order->get_meta('_dastine_paid_at') && !$order->get_meta('_dastine_sms_receipt')) {
        dastine_sms_queue($order, 'receipt');
    }
});

/* ---------- settings page ---------- */
add_action('admin_menu', function () {
    add_submenu_page('woocommerce', 'پیامک دستینه', 'پیامک دستینه', 'manage_woocommerce', 'dastine-sms', 'dastine_sms_page');
}, 60);

function dastine_sms_page() {
    if (!current_user_can('manage_woocommerce')) { return; }
    $cfg = dastine_sms_cfg();
    $note = '';
    if (!empty($_POST['dastine_sms_nonce']) && wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['dastine_sms_nonce'])), 'dastine_sms')) {
        $p = wp_unslash($_POST);
        foreach (array('sender', 'admin_phone', 'tpl_placed', 'tpl_paid', 'tpl_shipped', 'tpl_receipt', 'tpl_otp') as $k) {
            $cfg[$k] = sanitize_text_field($p[$k] ?? '');
        }
        foreach (array('api_key', 'secret_key') as $k) {
            $v = trim(sanitize_text_field($p[$k] ?? ''));
            if ($v !== '') { $cfg[$k] = $v; delete_transient('dastine_sms_token'); }
        }
        $cfg['on'] = !empty($p['on']) ? '1' : '0';
        update_option(DASTINE_SMS_OPT, $cfg, false);
        $note = 'ذخیره شد.';
        if (!empty($p['test'])) {
            $r = dastine_sms_send($cfg['admin_phone'], $cfg['tpl_placed'], array('order_id' => '1001'));
            $note = is_wp_error($r) ? 'پیامک آزمایشی نرفت: ' . $r->get_error_message() : 'پیامک آزمایشی «ثبت سفارش ۱۰۰۱» به شماره‌ی مدیر فرستاده شد.';
        }
    }
    $f = function ($k, $label, $help = '') use ($cfg) {
        printf('<tr><th><label for="%1$s">%2$s</label></th><td><input class="regular-text" dir="ltr" id="%1$s" name="%1$s" value="%3$s">%4$s</td></tr>',
            esc_attr($k), esc_html($label), esc_attr($cfg[$k]), $help ? '<p class="description">' . esc_html($help) . '</p>' : '');
    };
    echo '<div class="wrap" dir="rtl"><h1>پیامک دستینه (جیبیت)</h1>';
    if ($note) { echo '<div class="notice notice-info"><p>' . esc_html($note) . '</p></div>'; }
    $err = get_option('dastine_sms_last_error');
    if ($err) { echo '<p style="color:#a8323e">آخرین خطا: ' . esc_html($err) . '</p>'; }
    echo '<form method="post">';
    wp_nonce_field('dastine_sms', 'dastine_sms_nonce');
    echo '<table class="form-table">';
    printf('<tr><th>روشن</th><td><label><input type="checkbox" name="on" value="1"%s> پیامک‌های سفارش فرستاده شوند</label></td></tr>', checked($cfg['on'], '1', false));
    foreach (array('api_key' => 'API Key', 'secret_key' => 'Secret Key') as $k => $label) {
        printf('<tr><th><label for="%1$s">%2$s</label></th><td><input type="password" class="regular-text" dir="ltr" id="%1$s" name="%1$s" value="" autocomplete="new-password" placeholder="%3$s"><p class="description">برای عوض کردن، مقدارِ تازه را بنویسید؛ خالی بماند، قبلی می‌ماند.</p></td></tr>',
            esc_attr($k), esc_html($label), $cfg[$k] !== '' ? '•••••••• (ذخیره شده)' : 'وارد نشده');
    }
    $f('sender', 'شماره‌ی فرستنده');
    $f('admin_phone', 'موبایلِ مدیر', 'رسیدِ تازه به این شماره خبر داده می‌شود.');
    $f('tpl_placed', 'قالبِ ثبت سفارش');
    $f('tpl_paid', 'قالبِ تأیید پرداخت', 'وقتی سفارش را «در حال انجام» کنید.');
    $f('tpl_shipped', 'قالبِ ارسال', 'وقتی سفارش را «تکمیل‌شده» کنید.');
    $f('tpl_receipt', 'قالبِ رسیدِ تازه (به مدیر)');
    $f('tpl_otp', 'قالبِ کدِ ورود', 'برای بعد؛ هنوز استفاده نمی‌شود.');
    echo '</table><p><button class="button button-primary">ذخیره</button> <button class="button" name="test" value="1">ذخیره و پیامکِ آزمایشی به مدیر</button></p></form></div>';
}
