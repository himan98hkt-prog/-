<?php
/**
 * Plugin Name:       관리노트 인증키 자동 발급
 * Description:       학원 관리노트 · 피아노학원 관리노트가 결제되면 인증키를 만들어 구매자에게 메일로 바로 보냅니다. 코스모스팜 회원관리(퍼널모아)와 우커머스 결제를 지원합니다.
 * Version:           1.0.0
 * Requires at least: 5.8
 * Requires PHP:      7.4
 * Author:            아첼쌤
 * Text Domain:       academy-note-keys
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'ANK_VERSION', '1.0.0' );
define( 'ANK_FILE', __FILE__ );
define( 'ANK_DIR', plugin_dir_path( __FILE__ ) );

require_once ANK_DIR . 'includes/class-ank-keys.php';
require_once ANK_DIR . 'includes/class-ank-settings.php';
require_once ANK_DIR . 'includes/class-ank-store.php';
require_once ANK_DIR . 'includes/class-ank-mailer.php';
require_once ANK_DIR . 'includes/class-ank-issuer.php';
require_once ANK_DIR . 'includes/class-ank-hooks.php';
require_once ANK_DIR . 'includes/class-ank-admin.php';

register_activation_hook( __FILE__, array( 'ANK_Store', 'install' ) );

add_action(
	'plugins_loaded',
	static function () {
		// 플러그인 파일만 덮어써서 올린 경우에도 발급 대장이 준비되게 한다
		ANK_Store::maybe_install();
		ANK_Hooks::init();
		if ( is_admin() ) {
			ANK_Admin::init();
		}
	}
);
