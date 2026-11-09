<?php
/**
 * Plugin Name: Dastine SMS login
 * Description: Sign in with a one-time code by SMS (Jibit). Required before checkout; also powers the "my orders" page.
 */
if (!defined('ABSPATH')) { exit; }

/** 09xxxxxxxxx or '' */
function dastine_login_phone($p) {
    $d = function_exists('dastine_sms_phone') ? dastine_sms_phone($p) : '';
    return $d ? '0' . substr($d, 2) : '';
}

function dastine_login_user($phone) {
    $u = get_user_by('login', $phone);
    if ($u) { return $u; }
    $q = get_users(array('meta_key' => 'billing_phone', 'meta_value' => $phone, 'number' => 1, 'role__not_in' => array('administrator')));
    return $q ? $q[0] : null;
}

function dastine_login_ip() {
    return preg_replace('/[^0-9a-f:.]/i', '', (string) ($_SERVER['REMOTE_ADDR'] ?? ''));
}

add_action('wp_ajax_nopriv_dastine_otp_send', 'dastine_otp_send');
add_action('wp_ajax_dastine_otp_send', 'dastine_otp_send');
function dastine_otp_send() {
    check_ajax_referer('dastine_otp', 'nonce');
    $phone = dastine_login_phone(wp_unslash($_POST['phone'] ?? ''));
    if (!$phone) { wp_send_json_error(array('msg' => 'شماره‌ی موبایل را درست بنویس؛ مثلاً ۰۹۱۲۱۲۳۴۵۶۷')); }
    $k = 'dotp_' . md5($phone);
    $prev = get_transient($k);
    if ($prev && time() - (int) $prev['t'] < 60) { wp_send_json_error(array('msg' => 'کد فرستاده شد؛ یک دقیقه صبر کن و دوباره بخواه.', 'wait' => 60 - (time() - (int) $prev['t']))); }
    $ik = 'dotp_ip_' . md5(dastine_login_ip());
    $n = (int) get_transient($ik);
    if ($n >= 8) { wp_send_json_error(array('msg' => 'درخواست زیاد شد؛ کمی بعد دوباره امتحان کن.')); }
    set_transient($ik, $n + 1, HOUR_IN_SECONDS);
    $code = (string) wp_rand(1000, 9999);
    $cfg = dastine_sms_cfg();
    $res = dastine_sms_send($phone, (string) $cfg['tpl_otp'], array('otp_code' => $code));
    if (is_wp_error($res)) {
        update_option('dastine_sms_last_error', current_time('mysql') . ' · ورود: ' . $res->get_error_message(), false);
        wp_send_json_error(array('msg' => 'پیامک نرفت؛ چند لحظه بعد دوباره امتحان کن.'));
    }
    set_transient($k, array('h' => wp_hash($phone . '|' . $code), 't' => time(), 'tries' => 0), 5 * MINUTE_IN_SECONDS);
    wp_send_json_success(array('wait' => 60));
}

add_action('wp_ajax_nopriv_dastine_otp_verify', 'dastine_otp_verify');
add_action('wp_ajax_dastine_otp_verify', 'dastine_otp_verify');
function dastine_otp_verify() {
    check_ajax_referer('dastine_otp', 'nonce');
    $phone = dastine_login_phone(wp_unslash($_POST['phone'] ?? ''));
    $code = preg_replace('/\D+/', '', dastine_login_digits(wp_unslash($_POST['code'] ?? '')));
    $k = 'dotp_' . md5($phone);
    $s = $phone ? get_transient($k) : false;
    if (!$s) { wp_send_json_error(array('msg' => 'کد منقضی شده؛ دوباره کد بخواه.')); }
    if ((int) $s['tries'] >= 5) { delete_transient($k); wp_send_json_error(array('msg' => 'چند بار اشتباه شد؛ دوباره کد بخواه.')); }
    if (!hash_equals($s['h'], wp_hash($phone . '|' . $code))) {
        $s['tries'] = (int) $s['tries'] + 1;
        set_transient($k, $s, 5 * MINUTE_IN_SECONDS);
        wp_send_json_error(array('msg' => 'کد درست نیست.'));
    }
    delete_transient($k);
    $user = dastine_login_user($phone);
    if (!$user) {
        $id = wp_insert_user(array('user_login' => $phone, 'user_pass' => wp_generate_password(24), 'role' => 'customer', 'display_name' => $phone));
        if (is_wp_error($id)) { wp_send_json_error(array('msg' => 'ساختِ حساب نشد؛ دوباره امتحان کن.')); }
        $user = get_user_by('id', $id);
    }
    if (user_can($user, 'edit_others_posts')) { wp_send_json_error(array('msg' => 'این شماره برای ورودِ پیامکی نیست.')); }
    update_user_meta($user->ID, 'billing_phone', $phone);
    update_user_meta($user->ID, 'dastine_phone_ok', $phone);
    // earlier guest orders with this phone now belong to this account
    foreach (wc_get_orders(array('customer_id' => 0, 'billing_phone' => $phone, 'limit' => 50)) as $o) {
        if (dastine_login_phone($o->get_billing_phone()) === $phone) { $o->set_customer_id($user->ID); $o->save(); }
    }
    wp_set_current_user($user->ID);
    wp_set_auth_cookie($user->ID, true);
    wp_send_json_success();
}

function dastine_login_digits($s) {
    return strtr((string) $s, array('۰' => '0', '۱' => '1', '۲' => '2', '۳' => '3', '۴' => '4', '۵' => '5', '۶' => '6', '۷' => '7', '۸' => '8', '۹' => '9',
        '٠' => '0', '١' => '1', '٢' => '2', '٣' => '3', '٤' => '4', '٥' => '5', '٦' => '6', '٧' => '7', '٨' => '8', '٩' => '9'));
}

/** The sign-in box (phone → code). */
function dastine_login_box($title, $sub) {
    static $js = false;
    $out = '<div class="dastine-login"><h2>' . esc_html($title) . '</h2><p class="dastine-login__sub">' . esc_html($sub) . '</p>'
        . '<div class="dastine-login__step" data-step="phone"><label><span>شماره‌ی موبایل</span><input type="tel" inputmode="numeric" autocomplete="tel" maxlength="14" placeholder="۰۹۱۲۱۲۳۴۵۶۷" class="dastine-login__phone"></label>'
        . '<button type="button" class="dastine-btn dastine-btn--anar dastine-btn--block dastine-login__send">کد را بفرست</button></div>'
        . '<div class="dastine-login__step" data-step="code" hidden><label><span class="dastine-login__to"></span><input type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="کدِ ۴ رقمی" class="dastine-login__code"></label>'
        . '<button type="button" class="dastine-btn dastine-btn--anar dastine-btn--block dastine-login__ok">ورود</button>'
        . '<p class="dastine-login__links"><button type="button" class="dastine-login__again" disabled>ارسالِ دوباره</button> · <button type="button" class="dastine-login__edit">شماره را عوض کن</button></p></div>'
        . '<p class="dastine-login__msg" role="status"></p></div>';
    if (!$js) {
        $js = true;
        $out .= '<script>window.dastineOtp=' . wp_json_encode(array('url' => admin_url('admin-ajax.php'), 'nonce' => wp_create_nonce('dastine_otp'))) . ';</script>';
    }
    return $out;
}

add_action('wp_footer', function () {
    if (is_admin() || is_user_logged_in()) { return; }
    ?>
<script id="dastine-login">
(function(){
  var fa=function(s){return String(s).replace(/\d/g,function(d){return '۰۱۲۳۴۵۶۷۸۹'[d];});};
  var post=function(action,data){var f=new FormData();f.append('action',action);f.append('nonce',dastineOtp.nonce);for(var k in data)f.append(k,data[k]);
    return fetch(dastineOtp.url,{method:'POST',body:f,credentials:'same-origin'}).then(function(r){return r.json();}).catch(function(){return {success:false,data:{msg:'اینترنت قطع شد؛ دوباره امتحان کن.'}};});};
  document.querySelectorAll('.dastine-login').forEach(function(box){
    var q=function(s){return box.querySelector(s);},msg=q('.dastine-login__msg'),phone=q('.dastine-login__phone'),code=q('.dastine-login__code'),again=q('.dastine-login__again'),timer;
    var show=function(step){box.querySelectorAll('.dastine-login__step').forEach(function(s){s.hidden=s.getAttribute('data-step')!==step;});};
    var say=function(t,bad){msg.textContent=t||'';msg.classList.toggle('is-bad',!!bad);};
    var count=function(n){clearInterval(timer);again.disabled=true;again.textContent='ارسالِ دوباره ('+fa(n)+')';
      timer=setInterval(function(){n--;if(n<=0){clearInterval(timer);again.disabled=false;again.textContent='ارسالِ دوباره';}else again.textContent='ارسالِ دوباره ('+fa(n)+')';},1000);};
    var send=function(btn){btn.disabled=true;say('در حال فرستادن…');
      post('dastine_otp_send',{phone:phone.value}).then(function(r){btn.disabled=false;
        if(r.success){show('code');q('.dastine-login__to').textContent='کدی که به '+fa(phone.value.replace(/[^\d۰-۹]/g,''))+' پیامک شد';say('');count(r.data.wait||60);code.focus();}
        else{say(r.data&&r.data.msg,true);if(r.data&&r.data.wait){show('code');count(r.data.wait);}}});};
    q('.dastine-login__send').addEventListener('click',function(){send(this);});
    again.addEventListener('click',function(){send(this);});
    q('.dastine-login__edit').addEventListener('click',function(){show('phone');say('');phone.focus();});
    var ok=q('.dastine-login__ok');
    ok.addEventListener('click',function(){ok.disabled=true;say('در حال ورود…');
      post('dastine_otp_verify',{phone:phone.value,code:code.value}).then(function(r){
        if(r.success){say('وارد شدی.');location.reload();}else{ok.disabled=false;say(r.data&&r.data.msg,true);}});});
    phone.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();q('.dastine-login__send').click();}});
    code.addEventListener('input',function(){var v=code.value.replace(/[^\d۰-۹]/g,'');if(v.length===4)ok.click();});
    code.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();ok.click();}});
  });
})();
</script>
    <?php
}, 99);

/* ---------- checkout: sign in first, phone comes from the sign-in ---------- */
add_action('woocommerce_before_checkout_form', function () {
    if (is_user_logged_in()) { return; }
    echo dastine_login_box('اول با شماره‌ی موبایلت وارد شو', 'یک کدِ ۴ رقمی برایت پیامک می‌کنیم. رمز و ایمیل لازم نیست؛ دفعه‌ی بعد هم نشانی‌ات یادمان می‌ماند.'); // phpcs:ignore
    echo '<style>.woocommerce-checkout form.checkout,.woocommerce-checkout .woocommerce-form-coupon-toggle,.woocommerce-checkout .checkout_coupon{display:none!important}</style>';
}, 1);

function dastine_login_verified_phone() {
    $uid = get_current_user_id();
    return $uid ? (string) get_user_meta($uid, 'dastine_phone_ok', true) : '';
}

add_filter('woocommerce_checkout_fields', function ($f) {
    $p = dastine_login_verified_phone();
    if ($p && isset($f['billing']['billing_phone'])) {
        $f['billing']['billing_phone']['custom_attributes'] = array('readonly' => 'readonly');
        $f['billing']['billing_phone']['description'] = 'همان شماره‌ای که با آن وارد شدی؛ پیامک‌های سفارش به این شماره می‌آید.';
    }
    return $f;
}, 60);

add_filter('woocommerce_checkout_get_value', function ($v, $key) {
    if ($key === 'billing_phone') {
        $p = dastine_login_verified_phone();
        if ($p) { return $p; }
    }
    return $v;
}, 10, 2);

add_filter('woocommerce_checkout_posted_data', function ($d) {
    $p = dastine_login_verified_phone();
    if ($p) { $d['billing_phone'] = $p; }
    return $d;
}, 30);

add_action('woocommerce_checkout_process', function () {
    if (!is_user_logged_in()) { wc_add_notice('اول با کدِ پیامکی وارد شو، بعد سفارش را ثبت کن.', 'error'); }
});

/* ---------- my orders ---------- */
add_action('init', function () {
    if (get_option('dastine_orders_page')) { return; }
    $page = get_page_by_path('orders');
    $id = $page ? $page->ID : wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish', 'post_name' => 'orders', 'post_title' => 'سفارش‌های من',
        'post_content' => "<!-- wp:shortcode -->\n[dastine_orders]\n<!-- /wp:shortcode -->"));
    if ($id && !is_wp_error($id)) { update_option('dastine_orders_page', (int) $id); }
});

add_shortcode('dastine_orders', function () {
    if (!is_user_logged_in()) {
        return dastine_login_box('ورود با شماره‌ی موبایل', 'با همان شماره‌ای که سفارش دادی وارد شو تا سفارش‌ها و وضعیتشان را ببینی.');
    }
    $orders = wc_get_orders(array('customer_id' => get_current_user_id(), 'limit' => 30, 'orderby' => 'date', 'order' => 'DESC'));
    $fa = function ($s) { return function_exists('dastine_fa') ? dastine_fa($s) : $s; };
    $out = '<div class="dastine-orders">';
    if (!$orders) {
        $out .= '<p class="dastine-orders__empty">هنوز سفارشی نداری.</p><a class="dastine-btn dastine-btn--anar" href="' . esc_url(home_url('/')) . '">دیدنِ گالری</a>';
    }
    foreach ($orders as $o) {
        $st = $o->get_status();
        $paid = (bool) $o->get_meta('_dastine_paid_at');
        $names = array();
        foreach ($o->get_items() as $it) { $names[] = $it->get_name(); }
        $label = array('pending' => 'منتظرِ پرداخت', 'on-hold' => $paid ? 'واریزت رسید؛ در حالِ بررسی' : 'منتظرِ پرداخت',
            'processing' => 'پرداخت تأیید شد؛ در حالِ ساخت', 'completed' => 'با تیپاکس فرستاده شد', 'cancelled' => 'لغو شد',
            'refunded' => 'برگشت داده شد', 'failed' => 'ناموفق')[$st] ?? wc_get_order_status_name($st);
        $btn = (in_array($st, array('pending', 'on-hold'), true) && !$paid && $o->get_payment_method() === 'bacs')
            ? '<a class="dastine-btn dastine-btn--anar" href="' . esc_url($o->get_checkout_order_received_url()) . '">دیدنِ مبلغ و شماره‌ی کارت</a>' : '';
        $out .= '<div class="dastine-orders__item"><div class="dastine-orders__top"><b>سفارشِ ' . esc_html($fa($o->get_order_number())) . '</b><span class="dastine-orders__st is-' . esc_attr($st) . '">' . esc_html($label) . '</span></div>'
            . '<p>' . esc_html(implode('، ', $names)) . '</p>'
            . '<p class="dastine-orders__meta">' . esc_html($fa(wc_format_datetime($o->get_date_created(), 'Y/m/d'))) . ' · ' . wp_kses_post(wc_price($o->get_total())) . '</p>' . $btn . '</div>';
    }
    $out .= '<p class="dastine-orders__out"><a href="' . esc_url(wp_logout_url(home_url('/'))) . '">خروج از حساب</a></p></div>';
    return $out;
});

add_action('wp_head', function () {
    ?>
<style id="dastine-login-css">
.dastine-login{max-width:440px;margin:8px auto 40px;padding:26px 22px;border:1px solid var(--d-line,#E8DED2);border-radius:18px;background:#fff}
.dastine-login h2{font-size:22px;margin:0 0 6px}
.dastine-login__sub{color:var(--d-muted,#7a6e64);font-size:14px;line-height:1.9;margin:0 0 16px}
.dastine-login label{display:grid;gap:6px;font-size:14px;font-weight:700;margin-bottom:12px}
.dastine-login input{height:52px;border:1px solid #D9CDBD;border-radius:12px;padding:0 14px;font-family:inherit;font-size:18px;text-align:center;letter-spacing:1px}
.dastine-login .dastine-btn--block{width:100%;justify-content:center}
.dastine-login__links{text-align:center;font-size:13px;color:var(--d-muted,#7a6e64);margin:12px 0 0}
.dastine-login__links button{background:none;border:0;color:var(--d-anar,#A82E3C);font-family:inherit;font-size:13px;cursor:pointer;padding:4px}
.dastine-login__links button:disabled{color:var(--d-muted,#7a6e64);cursor:default}
.dastine-login__msg{min-height:1.6em;margin:10px 0 0;font-size:14px;text-align:center;color:var(--d-muted,#7a6e64)}
.dastine-login__msg.is-bad{color:var(--d-anar,#A82E3C);font-weight:700}
.dastine-orders{max-width:620px;margin:0 auto 48px;display:grid;gap:14px}
.dastine-orders__item{border:1px solid var(--d-line,#E8DED2);border-radius:16px;padding:16px 18px;background:#fff}
.dastine-orders__item p{margin:6px 0}
.dastine-orders__top{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.dastine-orders__st{font-size:13px;padding:4px 12px;border-radius:999px;background:var(--d-katan,#F3EBE1)}
.dastine-orders__st.is-processing,.dastine-orders__st.is-completed{background:#E7F2EA;color:#24613a}
.dastine-orders__meta{color:var(--d-muted,#7a6e64);font-size:14px}
.dastine-orders__item .dastine-btn{margin-top:8px}
.dastine-orders__out{text-align:center;font-size:14px}
</style>
    <?php
});
