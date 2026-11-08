<?php
/*
 * Plugin Name: Dastine engine
 * Description: Quiet behaviour measurement and recommendations for dastine.art (gallery wall ordering, related pieces, favourites, weekly report).
 * Version: 1.0.0
 */
if (!defined('ABSPATH')) { exit; }

define('DASTINE_ENGINE_DB', 2);

/* ---------- storage ---------- */
function dastine_events_table() {
    global $wpdb;
    return $wpdb->prefix . 'dastine_events';
}

add_action('init', function () {
    if ((int) get_option('dastine_engine_db') === DASTINE_ENGINE_DB) {
        return;
    }
    global $wpdb;
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $t = dastine_events_table();
    $c = $wpdb->get_charset_collate();
    dbDelta("CREATE TABLE $t (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        ts DATETIME NOT NULL,
        vid VARCHAR(24) NOT NULL,
        pid BIGINT UNSIGNED NOT NULL DEFAULT 0,
        ev VARCHAR(12) NOT NULL,
        val INT NOT NULL DEFAULT 0,
        ctx VARCHAR(16) NOT NULL DEFAULT '',
        PRIMARY KEY  (id),
        KEY pid_ev (pid, ev),
        KEY vid (vid),
        KEY ts (ts)
    ) $c;");
    update_option('dastine_engine_db', DASTINE_ENGINE_DB);
});

function dastine_allowed_events() {
    // imp = seen in a list, clk = opened from a list, view = product page, dwell = ms on product page,
    // gal = browsed product photos, heart / unheart = favourite, cart = add to cart, share = shared
    return array('imp', 'clk', 'view', 'dwell', 'gal', 'heart', 'unheart', 'cart', 'share');
}

/* ---------- REST ---------- */
add_action('rest_api_init', function () {
    register_rest_route('dastine/v1', '/e', array(
        'methods'             => 'POST',
        'permission_callback' => '__return_true',
        'callback'            => 'dastine_rest_events',
    ));
    register_rest_route('dastine/v1', '/fav', array(
        'methods'             => 'GET',
        'permission_callback' => '__return_true',
        'callback'            => 'dastine_rest_fav',
    ));
});

function dastine_rest_events(WP_REST_Request $req) {
    global $wpdb;
    $body = json_decode($req->get_body(), true);
    if (!is_array($body)) {
        return new WP_REST_Response(array('ok' => false), 400);
    }
    $vid = isset($body['v']) ? (string) $body['v'] : '';
    if (!preg_match('/^[a-z0-9]{8,24}$/', $vid)) {
        return new WP_REST_Response(array('ok' => false), 400);
    }
    $rows = isset($body['e']) && is_array($body['e']) ? array_slice($body['e'], 0, 60) : array();
    $allowed = dastine_allowed_events();
    $now = current_time('mysql', true);
    $t = dastine_events_table();
    $n = 0;
    foreach ($rows as $r) {
        if (!is_array($r) || count($r) < 2) { continue; }
        $pid = absint($r[0]);
        $ev  = (string) $r[1];
        $val = isset($r[2]) ? max(-1, min(3600000, (int) $r[2])) : 0;
        $ctx = isset($r[3]) ? substr(preg_replace('/[^a-z_]/', '', (string) $r[3]), 0, 16) : '';
        if (!in_array($ev, $allowed, true)) { continue; }
        if ($pid && get_post_type($pid) !== 'product') { continue; }
        $wpdb->insert($t, array('ts' => $now, 'vid' => $vid, 'pid' => $pid, 'ev' => $ev, 'val' => $val, 'ctx' => $ctx),
            array('%s', '%s', '%d', '%s', '%d', '%s'));
        $n++;
    }
    if ($n) { delete_transient('dastine_stats'); }
    return new WP_REST_Response(array('ok' => true, 'n' => $n), 200);
}

function dastine_rest_fav(WP_REST_Request $req) {
    $ids = array_filter(array_map('absint', explode(',', (string) $req->get_param('ids'))));
    $ids = array_slice(array_values(array_unique($ids)), 0, 60);
    $html = $ids ? dastine_render_loop($ids, 'fav', 4) : '';
    return new WP_REST_Response(array('html' => $html), 200);
}

/* ---------- scoring ---------- */
function dastine_stats() {
    $cached = get_transient('dastine_stats');
    if (is_array($cached)) { return $cached; }
    global $wpdb;
    $t = dastine_events_table();
    $since = gmdate('Y-m-d H:i:s', time() - 60 * DAY_IN_SECONDS);
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT pid, ev, COUNT(*) n, COUNT(DISTINCT vid) u, AVG(val) a FROM $t WHERE ts >= %s AND pid > 0 GROUP BY pid, ev", $since), ARRAY_A);
    $s = array();
    foreach ((array) $rows as $r) {
        $p = (int) $r['pid'];
        if (!isset($s[$p])) { $s[$p] = array('imp' => 0, 'clk' => 0, 'view' => 0, 'dwell' => 0, 'gal' => 0, 'heart' => 0, 'unheart' => 0, 'cart' => 0, 'share' => 0, 'visitors' => 0); }
        $s[$p][$r['ev']] = ($r['ev'] === 'dwell') ? (int) round($r['a']) : (int) $r['u'];
        if ($r['ev'] === 'view') { $s[$p]['visitors'] = (int) $r['u']; }
    }
    set_transient('dastine_stats', $s, 10 * MINUTE_IN_SECONDS);
    return $s;
}

function dastine_score($pid, $stats) {
    $x = isset($stats[$pid]) ? $stats[$pid] : array();
    $g = function ($k) use ($x) { return isset($x[$k]) ? (float) $x[$k] : 0.0; };
    $hearts = max(0, $g('heart') - $g('unheart'));
    $dwell = min(1.0, $g('dwell') / 30000.0);          // up to 30 seconds counts
    $engaged = $g('clk') + 0.5 * $g('gal') + 3 * $hearts + 5 * $g('cart') + 2 * $g('share') + $dwell * $g('view');
    return ($engaged + 1.0) / ($g('imp') + 8.0);       // smoothed: new pieces start near the middle
}

function dastine_visitor_id() {
    $v = isset($_COOKIE['dastine_v']) ? (string) $_COOKIE['dastine_v'] : '';
    return preg_match('/^[a-z0-9]{8,24}$/', $v) ? $v : '';
}

function dastine_visitor_affinity($vid) {
    if (!$vid) { return array(); }
    global $wpdb;
    $t = dastine_events_table();
    $pids = $wpdb->get_col($wpdb->prepare(
        "SELECT pid FROM $t WHERE vid = %s AND ev IN ('clk','view','heart','cart') AND pid > 0 ORDER BY id DESC LIMIT 40", $vid));
    $aff = array();
    foreach ((array) $pids as $p) {
        foreach ((array) wp_get_post_terms((int) $p, 'product_cat', array('fields' => 'ids')) as $c) {
            $aff[$c] = isset($aff[$c]) ? $aff[$c] + 1 : 1;
        }
    }
    return $aff;
}

function dastine_ranked_ids($limit = 24, $exclude = array()) {
    $ids = wc_get_products(array('status' => 'publish', 'limit' => 300, 'return' => 'ids', 'visibility' => 'catalog'));
    $ids = array_values(array_diff(array_map('intval', $ids), array_map('intval', $exclude)));
    if (!$ids) { return array(); }
    $stats = dastine_stats();
    $aff = dastine_visitor_affinity(dastine_visitor_id());
    $score = array();
    foreach ($ids as $p) {
        $sc = dastine_score($p, $stats);
        if ($aff) {
            $boost = 0;
            foreach ((array) wp_get_post_terms($p, 'product_cat', array('fields' => 'ids')) as $c) {
                if (isset($aff[$c])) { $boost = max($boost, $aff[$c]); }
            }
            $sc *= 1 + min(0.5, 0.1 * $boost);
        }
        $score[$p] = $sc;
    }
    arsort($score);
    $ranked = array_keys($score);
    // Quiet exploration: every 4th place goes to a piece that has been seen little.
    $fresh = array();
    foreach ($ids as $p) {
        $imp = isset($stats[$p]['imp']) ? $stats[$p]['imp'] : 0;
        if ($imp < 40) { $fresh[] = $p; }
    }
    shuffle($fresh);
    $out = array();
    $i = 0;
    while (count($out) < min($limit, count($ids))) {
        if (($i % 4) === 3 && $fresh) {
            $f = array_shift($fresh);
            if (!in_array($f, $out, true)) { $out[] = $f; $i++; continue; }
        }
        $next = array_shift($ranked);
        if ($next === null) { break; }
        if (!in_array($next, $out, true)) { $out[] = $next; }
        $i++;
    }
    return $out;
}

/* ---------- rendering ---------- */
function dastine_render_loop($ids, $ctx, $columns = 4) {
    if (!$ids || !function_exists('wc_get_template_part')) { return ''; }
    $q = new WP_Query(array('post_type' => 'product', 'post__in' => $ids, 'orderby' => 'post__in', 'posts_per_page' => count($ids), 'no_found_rows' => true));
    if (!$q->have_posts()) { return ''; }
    wc_set_loop_prop('columns', $columns);
    wc_set_loop_prop('name', 'dastine_' . $ctx);
    ob_start();
    echo '<div class="woocommerce columns-' . (int) $columns . ' dastine-loop" data-ctx="' . esc_attr($ctx) . '">';
    woocommerce_product_loop_start();
    while ($q->have_posts()) {
        $q->the_post();
        wc_get_template_part('content', 'product');
    }
    woocommerce_product_loop_end();
    echo '</div>';
    wp_reset_postdata();
    wc_reset_loop();
    return ob_get_clean();
}

add_shortcode('dastine_wall', function ($atts) {
    $a = shortcode_atts(array('limit' => 24, 'columns' => 4), $atts);
    $ids = dastine_ranked_ids((int) $a['limit']);
    if (!$ids) {
        return '<p class="dastine-empty">به‌زودی آثارِ تازه این‌جا آویزان می‌شوند.</p>';
    }
    return dastine_render_loop($ids, 'wall', (int) $a['columns']);
});

/* Hero: three pieces picked by the engine (best for this visitor + the newest), as a collage. */
add_shortcode('dastine_hero', function () {
    $ranked = dastine_ranked_ids(6);
    $newest = wc_get_products(array('status' => 'publish', 'limit' => 1, 'orderby' => 'date', 'order' => 'DESC', 'return' => 'ids'));
    $pick = array_slice(array_values(array_unique(array_merge(array_slice($ranked, 0, 2), $newest, $ranked))), 0, 3);
    $items = '';
    foreach ($pick as $i => $pid) {
        $p = wc_get_product($pid);
        if (!$p) { continue; }
        $img = get_the_post_thumbnail_url($pid, $i === 0 ? 'large' : 'medium_large');
        if (!$img) { continue; }
        $items .= sprintf('<li class="product post-%1$d dastine-piece dastine-piece--%2$d"><a href="%3$s"><img src="%4$s" alt="%5$s" loading="%6$s"><span class="dastine-piece__cap"><b>%5$s</b><i>%7$s</i></span></a></li>',
            $pid, $i, esc_url(get_permalink($pid)), esc_url($img), esc_attr($p->get_name()), $i === 0 ? 'eager' : 'lazy', wp_kses_post($p->get_price_html()));
    }
    $mark = esc_url(get_stylesheet_directory_uri() . '/assets/images/dastine-mark.svg');
    return '<section class="dastine-hero2"><img class="dastine-hero2__mark" src="' . $mark . '" alt="" aria-hidden="true">'
        . '<div class="dastine-hero2__in"><div class="dastine-hero2__text">'
        . '<p class="dastine-hero2__eyebrow">زیورِ دست‌سازِ شناسنامه‌دار</p>'
        . '<h1>از دستانِ سازنده،<br>به دستانِ تو</h1>'
        . '<p class="dastine-hero2__lead">هر قطعه را یک نفر با دست می‌سازد و با کارتِ شناسنامه به دستت می‌رسد.</p>'
        . '<div class="dastine-hero2__btns"><a class="dastine-btn dastine-btn--light" href="#gallery">ورود به گالری</a><a class="dastine-btn dastine-btn--ghost" href="/shop/?orderby=date">تازه‌ها</a></div>'
        . '</div>' . ($items ? '<ul class="dastine-hero2__pieces" data-ctx="hero">' . $items . '</ul>' : '') . '</div></section>';
});

add_shortcode('dastine_favorites', function () {
    return '<div class="dastine-favs" data-ctx="fav"><p class="dastine-empty">هنوز اثری را دلخواه نکرده‌ای. روی ♡ کنارِ هر اثر بزن تا این‌جا بماند.</p></div>';
});

/* Related pieces: people who looked at this also looked at… then same hall, then best overall. */
function dastine_related_ids($pid, $n = 4) {
    global $wpdb;
    $t = dastine_events_table();
    $co = $wpdb->get_col($wpdb->prepare(
        "SELECT b.pid FROM $t a JOIN $t b ON a.vid = b.vid AND b.pid <> a.pid AND b.pid > 0
         WHERE a.pid = %d AND a.ev IN ('clk','view','heart','cart') AND b.ev IN ('clk','view','heart','cart')
         GROUP BY b.pid ORDER BY COUNT(DISTINCT b.vid) DESC LIMIT 12", $pid));
    $out = array();
    foreach ((array) $co as $p) {
        $p = (int) $p;
        if (get_post_status($p) === 'publish') { $out[] = $p; }
        if (count($out) >= $n) { return $out; }
    }
    $cats = wp_get_post_terms($pid, 'product_cat', array('fields' => 'ids'));
    if ($cats) {
        $same = wc_get_products(array('status' => 'publish', 'limit' => 30, 'return' => 'ids', 'category' => array_map(function ($c) {
            $term = get_term($c, 'product_cat'); return $term ? $term->slug : '';
        }, $cats), 'exclude' => array_merge(array($pid), $out)));
        $stats = dastine_stats();
        usort($same, function ($x, $y) use ($stats) { return dastine_score($y, $stats) <=> dastine_score($x, $stats); });
        foreach ($same as $p) { if (count($out) >= $n) { break; } $out[] = (int) $p; }
    }
    if (count($out) < $n) {
        foreach (dastine_ranked_ids($n * 2, array_merge(array($pid), $out)) as $p) { if (count($out) >= $n) { break; } $out[] = $p; }
    }
    return $out;
}

add_action('init', function () {
    remove_action('woocommerce_after_single_product_summary', 'woocommerce_output_related_products', 20);
    remove_action('woocommerce_after_single_product_summary', 'woocommerce_upsell_display', 15);
});
add_action('woocommerce_after_single_product_summary', function () {
    $ids = dastine_related_ids(get_the_ID(), 4);
    if (!$ids) { return; }
    echo '<section class="dastine-related"><h2>شاید این‌ها را هم دوست داشته باشی</h2>' . dastine_render_loop($ids, 'related', 4) . '</section>';
}, 20);

/* Museum-style placard line under each title: maker · edition (custom fields dastine_maker, dastine_edition). */
function dastine_placard_line($pid) {
    $maker = trim((string) get_post_meta($pid, 'dastine_maker', true));
    $ed = trim((string) get_post_meta($pid, 'dastine_edition', true));
    $parts = array();
    if ($maker !== '') { $parts[] = 'ساخته‌ی ' . esc_html($maker); }
    if ($ed !== '') { $parts[] = esc_html($ed); }
    return $parts ? '<span class="dastine-placard">' . implode(' · ', $parts) . '</span>' : '';
}
add_action('woocommerce_after_shop_loop_item_title', function () { echo dastine_placard_line(get_the_ID()); }, 5);
add_action('woocommerce_single_product_summary', function () { echo dastine_placard_line(get_the_ID()); }, 6);

/* ---------- the quiet tracker ---------- */
add_action('wp_footer', function () {
    if (is_admin()) { return; }
    $cfg = array('url' => esc_url_raw(rest_url('dastine/v1/')), 'pid' => is_singular('product') ? get_the_ID() : 0);
    ?>
<script id="dastine-engine">
(function(){
  var C=<?php echo wp_json_encode($cfg); ?>;
  var ls=window.localStorage, q=[], seen={};
  function vid(){var v=null;try{v=ls.getItem('dastine_v');}catch(e){}
    if(!v||!/^[a-z0-9]{8,24}$/.test(v)){v=(Date.now().toString(36)+Math.random().toString(36).slice(2,10)).slice(0,20);try{ls.setItem('dastine_v',v);}catch(e){}}
    document.cookie='dastine_v='+v+';path=/;max-age=31536000;SameSite=Lax';return v;}
  var V=vid();
  function ctxOf(el){var c=el&&el.closest('[data-ctx]');if(c)return c.getAttribute('data-ctx');
    var b=document.body.classList;return b.contains('home')?'home':(b.contains('single-product')?'single':'shop');}
  function pidOf(li){var m=(li.className||'').match(/post-(\d+)/);return m?+m[1]:0;}
  function push(p,e,v,c){q.push([p,e,v||0,c||'']);if(q.length>=20)flush();}
  function flush(beacon){if(!q.length)return;var body=JSON.stringify({v:V,e:q.splice(0,60)});
    try{if(beacon&&navigator.sendBeacon){navigator.sendBeacon(C.url+'e',new Blob([body],{type:'application/json'}));return;}}catch(e){}
    fetch(C.url+'e',{method:'POST',headers:{'Content-Type':'application/json'},body:body,keepalive:true}).catch(function(){});}
  setInterval(flush,5000);
  /* favourites */
  function favs(){try{return JSON.parse(ls.getItem('dastine_fav')||'[]');}catch(e){return [];}}
  function setFavs(a){try{ls.setItem('dastine_fav',JSON.stringify(a));}catch(e){}}
  function heartBtn(pid){var b=document.createElement('button');b.type='button';b.className='dastine-heart';
    b.setAttribute('aria-label','افزودن به دلخواه‌ها');b.setAttribute('aria-pressed',favs().indexOf(pid)>-1?'true':'false');
    b.innerHTML='<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>';
    b.addEventListener('click',function(ev){ev.preventDefault();ev.stopPropagation();var a=favs(),i=a.indexOf(pid);
      if(i>-1){a.splice(i,1);push(pid,'unheart',0,ctxOf(b));b.setAttribute('aria-pressed','false');}
      else{a.unshift(pid);push(pid,'heart',0,ctxOf(b));b.setAttribute('aria-pressed','true');}
      setFavs(a.slice(0,60));});return b;}
  /* lists: impressions, clicks, add to cart */
  var io='IntersectionObserver' in window?new IntersectionObserver(function(es){es.forEach(function(en){
    var li=en.target,p=pidOf(li);if(!p)return;
    if(en.isIntersecting&&en.intersectionRatio>=0.5){li._t=setTimeout(function(){var k=p+':'+ctxOf(li);if(!seen[k]){seen[k]=1;push(p,'imp',0,ctxOf(li));}},1000);}
    else if(li._t){clearTimeout(li._t);}});},{threshold:[0.5]}):null;
  function wire(root){(root||document).querySelectorAll('li.product').forEach(function(li,i){if(li._d)return;li._d=1;var p=pidOf(li);if(!p)return;
    if(io)io.observe(li);
    var img=li.querySelector('a.woocommerce-LoopProduct-link, a');if(img&&!li.querySelector('.dastine-heart')){li.style.position='relative';li.appendChild(heartBtn(p));}
    li.addEventListener('click',function(ev){var t=ev.target;
      if(t.closest('.add_to_cart_button')){push(p,'cart',i,ctxOf(li));flush();}
      else if(t.closest('a')){push(p,'clk',i,ctxOf(li));flush(true);}});});}
  wire();
  /* product page: view, dwell, photo browsing, add to cart, heart */
  if(C.pid){var t0=Date.now(),hidden=0,hs=0;push(C.pid,'view',0,'single');
    document.addEventListener('visibilitychange',function(){if(document.hidden){hs=Date.now();}else if(hs){hidden+=Date.now()-hs;hs=0;}});
    window.addEventListener('pagehide',function(){push(C.pid,'dwell',Date.now()-t0-hidden,'single');flush(true);});
    document.addEventListener('click',function(ev){var t=ev.target;
      if(t.closest('.flex-control-nav, .woocommerce-product-gallery__trigger, .flex-direction-nav'))push(C.pid,'gal',0,'single');
      if(t.closest('form.cart button[type=submit], .single_add_to_cart_button')){push(C.pid,'cart',0,'single');flush();}});
    var sum=document.querySelector('.summary, .wp-block-woocommerce-product-price');var form=document.querySelector('form.cart');
    if(form&&!form.querySelector('.dastine-heart')){var hb=heartBtn(C.pid);hb.classList.add('dastine-heart--inline');form.appendChild(hb);}}
  /* favourites page */
  var box=document.querySelector('.dastine-favs');
  if(box){var a=favs();if(a.length){fetch(C.url+'fav?ids='+a.join(',')).then(function(r){return r.json();}).then(function(d){if(d&&d.html){box.innerHTML=d.html;wire(box);}}).catch(function(){});}}
})();
</script>
    <?php
}, 99);

/* ---------- report for us (WooCommerce › موتور دستینه) ---------- */
add_action('admin_menu', function () {
    add_submenu_page('woocommerce', 'موتور دستینه', 'موتور دستینه', 'manage_woocommerce', 'dastine-engine', 'dastine_report_page');
});
function dastine_report_page() {
    $stats = dastine_stats();
    $ids = wc_get_products(array('status' => array('publish', 'private', 'draft'), 'limit' => 300, 'return' => 'ids'));
    usort($ids, function ($x, $y) use ($stats) { return dastine_score($y, $stats) <=> dastine_score($x, $stats); });
    echo '<div class="wrap"><h1>موتور دستینه — ۶۰ روزِ گذشته</h1><p>هر عدد = تعداد بازدیدکننده‌ی جدا. «ماندن» = میانگین ثانیه در صفحه‌ی اثر. امتیاز برای چیدمانِ دیوارِ گالری به کار می‌رود.</p>';
    echo '<table class="widefat striped"><thead><tr><th>اثر</th><th>دیده‌شده</th><th>باز شده</th><th>نرخ باز شدن</th><th>عکس‌ها را ورق زد</th><th>ماندن (ثانیه)</th><th>دلخواه</th><th>سبد</th><th>امتیاز</th></tr></thead><tbody>';
    foreach ($ids as $p) {
        $x = isset($stats[$p]) ? $stats[$p] : array();
        $g = function ($k) use ($x) { return isset($x[$k]) ? (int) $x[$k] : 0; };
        $ctr = $g('imp') ? round(100 * $g('clk') / $g('imp'), 1) . '٪' : '—';
        printf('<tr><td><a href="%s">%s</a></td><td>%d</td><td>%d</td><td>%s</td><td>%d</td><td>%s</td><td>%d</td><td>%d</td><td>%.3f</td></tr>',
            esc_url(get_edit_post_link($p)), esc_html(get_the_title($p)), $g('imp'), $g('clk'), esc_html($ctr), $g('gal'),
            $g('dwell') ? round($g('dwell') / 1000) : '—', max(0, $g('heart') - $g('unheart')), $g('cart'), dastine_score($p, $stats));
    }
    echo '</tbody></table></div>';
}
