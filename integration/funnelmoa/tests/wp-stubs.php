<?php
/**
 * 워드프레스 없이 플러그인을 돌려 보기 위한 최소한의 흉내.
 *
 * 진짜 워드프레스·우커머스·코스모스팜을 대신하는 것이 아니다. 플러그인이 부르는 함수만
 * 같은 이름·같은 약속으로 만들어, "결제 신호 → 키 발급 → 메일" 흐름이 끝까지 도는지 확인한다.
 * DB 는 SQLite 메모리 DB 에 실제 SQL 을 실행한다(유일 제약으로 중복 발급을 막는지까지 본다).
 */

define( 'ABSPATH', __DIR__ . '/fake-wp/' );
define( 'ARRAY_A', 'ARRAY_A' );
define( 'ENT_QUOTES_STUB', true );

$GLOBALS['ank_test'] = array(
	'options'   => array( 'admin_email' => 'seller@example.com' ),
	'actions'   => array(),
	'mails'     => array(),
	'mail_ok'   => true,
	'postmeta'  => array(),
	'users'     => array(),
	'current'   => null,
	'wc_orders' => array(),
	'routes'    => array(),
	'shortcodes' => array(),
);

// ── 훅 ────────────────────────────────────────────────────
function add_action( $hook, $cb, $prio = 10, $args = 1 ) { $GLOBALS['ank_test']['actions'][ $hook ][] = array( $cb, $args ); return true; }
function add_filter( $hook, $cb, $prio = 10, $args = 1 ) { return add_action( $hook, $cb, $prio, $args ); }
function has_action( $hook ) { return ! empty( $GLOBALS['ank_test']['actions'][ $hook ] ); }
function do_action( $hook, ...$args ) {
	foreach ( $GLOBALS['ank_test']['actions'][ $hook ] ?? array() as $entry ) {
		call_user_func_array( $entry[0], array_slice( $args, 0, $entry[1] ) );
	}
}
function apply_filters( $hook, $value, ...$args ) {
	foreach ( $GLOBALS['ank_test']['actions'][ $hook ] ?? array() as $entry ) {
		$value = call_user_func_array( $entry[0], array_slice( array_merge( array( $value ), $args ), 0, $entry[1] ) );
	}
	return $value;
}
function add_shortcode( $tag, $cb ) { $GLOBALS['ank_test']['shortcodes'][ $tag ] = $cb; }
function register_activation_hook( $file, $cb ) {}
function plugin_dir_path( $file ) { return dirname( $file ) . '/'; }
function plugin_basename( $file ) { return basename( dirname( $file ) ) . '/' . basename( $file ); }
function is_admin() { return false; }

// ── 옵션 ──────────────────────────────────────────────────
function get_option( $key, $default = false ) { return $GLOBALS['ank_test']['options'][ $key ] ?? $default; }
function update_option( $key, $value, $autoload = null ) { $GLOBALS['ank_test']['options'][ $key ] = $value; return true; }
function delete_option( $key ) { unset( $GLOBALS['ank_test']['options'][ $key ] ); return true; }
function get_bloginfo( $what = 'name' ) { return '아첼쌤 스토어'; }
function current_time( $type ) { return gmdate( 'Y-m-d H:i:s' ); }

// ── 문자열 ────────────────────────────────────────────────
function wp_specialchars_decode( $s, $q = null ) { return htmlspecialchars_decode( (string) $s, ENT_QUOTES ); }
function esc_html( $s ) { return htmlspecialchars( (string) $s, ENT_QUOTES, 'UTF-8' ); }
function esc_attr( $s ) { return esc_html( $s ); }
function esc_url( $s ) { return str_replace( array( '"', "'", '<', '>' ), '', (string) $s ); }
function is_email( $s ) { return (bool) filter_var( (string) $s, FILTER_VALIDATE_EMAIL ); }
function sanitize_email( $s ) { return is_email( trim( (string) $s ) ) ? trim( (string) $s ) : ''; }
function sanitize_key( $s ) { return preg_replace( '/[^a-z0-9_\-]/', '', strtolower( (string) $s ) ); }
function sanitize_text_field( $s ) { return trim( strip_tags( (string) $s ) ); }
function wp_strip_all_tags( $s ) { return trim( strip_tags( (string) $s ) ); }

// ── 메일 ──────────────────────────────────────────────────
function wp_mail( $to, $subject, $message, $headers = array() ) {
	if ( ! $GLOBALS['ank_test']['mail_ok'] ) {
		// 판매자에게 가는 경고 메일은 실패 설정과 무관하게 기록한다 (무엇을 알렸는지 보려고)
		if ( $to === get_option( 'admin_email' ) ) {
			$GLOBALS['ank_test']['mails'][] = compact( 'to', 'subject', 'message', 'headers' );
		}
		return false;
	}
	$GLOBALS['ank_test']['mails'][] = compact( 'to', 'subject', 'message', 'headers' );
	return true;
}

// ── 사용자·글 ─────────────────────────────────────────────
function get_post_meta( $id, $key, $single = false ) { return $GLOBALS['ank_test']['postmeta'][ $id ][ $key ] ?? ''; }
function get_the_title( $id ) { return $GLOBALS['ank_test']['postmeta'][ $id ]['_title'] ?? ''; }
function get_userdata( $id ) { return $GLOBALS['ank_test']['users'][ $id ] ?? false; }
function wp_get_current_user() { return $GLOBALS['ank_test']['current'] ?? (object) array( 'ID' => 0, 'user_email' => '', 'display_name' => '' ); }
function is_user_logged_in() { return ! empty( $GLOBALS['ank_test']['current'] ); }

// ── REST ──────────────────────────────────────────────────
function register_rest_route( $ns, $route, $args ) { $GLOBALS['ank_test']['routes'][ $ns . $route ] = $args; }
function rest_url( $path = '' ) { return 'https://shop.example.com/wp-json/' . $path; }
class WP_REST_Response { public $data; public $status; function __construct( $data, $status = 200 ) { $this->data = $data; $this->status = $status; } }
class Fake_Request {
	private $params; private $headers;
	function __construct( $params = array(), $headers = array() ) { $this->params = $params; $this->headers = $headers; }
	function get_param( $k ) { return $this->params[ $k ] ?? null; }
	function get_header( $k ) { return $this->headers[ strtolower( $k ) ] ?? null; }
}

// ── 우커머스 ──────────────────────────────────────────────
function wc_get_order( $id ) { return $GLOBALS['ank_test']['wc_orders'][ $id ] ?? false; }
class Fake_WC_Item {
	public $product_id; public $name; public $qty; public $variation_id;
	function __construct( $product_id, $name, $qty = 1, $variation_id = 0 ) { $this->product_id = $product_id; $this->name = $name; $this->qty = $qty; $this->variation_id = $variation_id; }
	function get_product_id() { return $this->product_id; }
	function get_variation_id() { return $this->variation_id; }
	function get_name() { return $this->name; }
	function get_quantity() { return $this->qty; }
}
class Fake_WC_Order {
	public $items; public $email; public $last; public $first; public $notes = array();
	function __construct( $items, $email, $last = '', $first = '' ) { $this->items = $items; $this->email = $email; $this->last = $last; $this->first = $first; }
	function get_items() { return $this->items; }
	function get_billing_email() { return $this->email; }
	function get_billing_last_name() { return $this->last; }
	function get_billing_first_name() { return $this->first; }
	function add_order_note( $note ) { $this->notes[] = $note; }
}

// ── DB (SQLite 로 실제 SQL 을 실행) ───────────────────────
class Fake_WPDB {
	public $prefix = 'wp_';
	public $insert_id = 0;
	private $db;
	function __construct() { $this->db = new SQLite3( ':memory:' ); $this->db->enableExceptions( false ); }
	function get_charset_collate() { return ''; }
	function suppress_errors( $on = true ) {}
	function esc_like( $s ) { return addcslashes( $s, '_%\\' ); }
	function prepare( $sql, ...$args ) {
		if ( 1 === count( $args ) && is_array( $args[0] ) ) { $args = $args[0]; }
		$i = 0;
		return preg_replace_callback( '/%[sd]/', function ( $m ) use ( &$i, $args ) {
			$v = $args[ $i++ ];
			return '%d' === $m[0] ? (string) (int) $v : "'" . SQLite3::escapeString( (string) $v ) . "'";
		}, $sql );
	}
	function query( $sql ) { return @$this->db->exec( $sql ); }
	function get_results( $sql, $mode = null ) {
		$res = @$this->db->query( $sql ); $out = array();
		if ( $res ) { while ( $r = $res->fetchArray( SQLITE3_ASSOC ) ) { $out[] = $r; } }
		return $out;
	}
	function get_row( $sql, $mode = null ) { $rows = $this->get_results( $sql ); return $rows ? $rows[0] : null; }
	function get_var( $sql ) { $row = $this->get_row( $sql ); return $row ? array_values( $row )[0] : null; }
	function insert( $table, $data ) {
		$cols = implode( ',', array_keys( $data ) );
		$vals = implode( ',', array_map( function ( $v ) { return "'" . SQLite3::escapeString( (string) $v ) . "'"; }, array_values( $data ) ) );
		$ok   = @$this->db->exec( "INSERT INTO {$table} ({$cols}) VALUES ({$vals})" );
		if ( $ok ) { $this->insert_id = $this->db->lastInsertRowID(); }
		return $ok ? 1 : false;
	}
	function update( $table, $data, $where ) {
		$set = implode( ',', array_map( function ( $k, $v ) { return "{$k}='" . SQLite3::escapeString( (string) $v ) . "'"; }, array_keys( $data ), $data ) );
		$w   = implode( ' AND ', array_map( function ( $k, $v ) { return "{$k}='" . SQLite3::escapeString( (string) $v ) . "'"; }, array_keys( $where ), $where ) );
		return @$this->db->exec( "UPDATE {$table} SET {$set} WHERE {$w}" );
	}
	function create_ledger( $table ) {
		$this->db->exec( "CREATE TABLE IF NOT EXISTS {$table} (
			id INTEGER PRIMARY KEY AUTOINCREMENT, order_ref TEXT NOT NULL UNIQUE, source TEXT DEFAULT '', product_ref TEXT DEFAULT '',
			product_title TEXT DEFAULT '', key_type TEXT DEFAULT '', license_key TEXT DEFAULT '', email TEXT DEFAULT '', name TEXT DEFAULT '',
			memo TEXT DEFAULT '', send_count INTEGER NOT NULL DEFAULT 0, sent_at TEXT, created_at TEXT NOT NULL)" );
	}
}
$GLOBALS['wpdb'] = new Fake_WPDB();
/** 진짜 dbDelta 는 MySQL 문법을 해석한다. 여기서는 같은 뜻의 SQLite 표를 만든다. */
function dbDelta( $sql ) {
	if ( preg_match( '/CREATE TABLE (\S+)/', $sql, $m ) ) { $GLOBALS['wpdb']->create_ledger( $m[1] ); }
}

// ── 관리 화면 (화면이 오류 없이 그려지는지, 저장이 되는지만 본다) ──
class Ank_Redirect extends Exception {}
function add_menu_page( ...$a ) {}
function admin_url( $path = '' ) { return 'https://shop.example.com/wp-admin/' . $path; }
function add_query_arg( $args, $url ) { return $url . ( false === strpos( $url, '?' ) ? '?' : '&' ) . http_build_query( $args ); }
function wp_nonce_field( $action, $name = '_wpnonce', $referer = true, $echo = true ) { return '<input type="hidden" name="' . $name . '" value="nonce">'; }
function wp_nonce_url( $url, $action ) { return $url . '&_wpnonce=nonce'; }
function check_admin_referer( $action ) { return true; }
function current_user_can( $cap ) { return true; }
function wp_die( $msg ) { throw new Exception( $msg ); }
function wp_safe_redirect( $url ) { throw new Ank_Redirect( $url ); }
function wp_unslash( $v ) { return $v; }
function wp_kses_post( $s ) { return $s; }
function wp_rand( $a, $b ) { return random_int( $a, $b ); }
function esc_textarea( $s ) { return esc_html( $s ); }
function esc_url_raw( $s ) { return filter_var( $s, FILTER_VALIDATE_URL ) ? $s : ''; }
function sanitize_textarea_field( $s ) { return trim( strip_tags( (string) $s ) ); }
function number_format_i18n( $n ) { return number_format( $n ); }
function selected( $a, $b, $echo = true ) { return (string) $a === (string) $b ? ' selected' : ''; }
function checked( $a, $b = true, $echo = true ) { return $a == $b ? ' checked' : ''; }
function post_type_exists( $t ) { return false; }
function nocache_headers() {}
