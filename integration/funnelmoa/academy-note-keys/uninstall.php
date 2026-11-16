<?php
/**
 * 플러그인을 지울 때.
 *
 * 발급 대장은 판매 기록이다. 플러그인을 지웠다고 "누구에게 어떤 키를 줬는지" 가 사라지면 안 되므로
 * 일부러 남겨 둔다(다시 설치하면 그대로 이어진다). 설정과 진단 기록만 지운다.
 * 대장까지 지우려면 DB 에서 {접두어}ank_keys 표를 직접 지우면 된다.
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

delete_option( 'ank_settings' );
delete_option( 'ank_log' );
