<?php
/**
 * 설정값과 진단 기록.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class ANK_Settings {

	const OPTION = 'ank_settings';
	const LOG    = 'ank_log';

	public static function defaults() {
		return array(
			// 메일의 "눌러서 바로 시작하기" 버튼이 여는 주소 (학원 관리노트를 올려 둔 곳)
			'app_url'       => '',
			'from_name'     => '',
			'from_email'    => '',
			// 발급될 때마다 판매자도 같은 메일을 받는다 (고객 문의 대응용)
			'admin_copy'    => 1,
			'admin_email'   => '',
			// 연결하지 않은 상품이 결제됐을 때: '' = 발급하지 않음
			'default_type'  => '',
			// 상품 연결: [ ['match' => '상품 번호 또는 상품명 일부', 'type' => 'piano', 'app_url' => ''] ]
			'products'      => array(),
			'wc_statuses'   => array( 'completed', 'processing' ),
			'webhook_token' => '',
			'subject'       => '[{사이트명}] {상품명} 인증키를 보내드립니다',
			'intro'         => "{이름}님, 구매해 주셔서 감사합니다.\n아래 인증키를 앱에 넣으면 바로 사용하실 수 있습니다.",
			'outro'         => "기기를 바꿀 때 다시 쓰실 수 있도록 이 메일을 보관해 주세요.\n사용 중 궁금한 점은 이 메일에 답장으로 보내 주세요.",
		);
	}

	public static function all() {
		$saved = get_option( self::OPTION, array() );
		$s     = array_merge( self::defaults(), is_array( $saved ) ? $saved : array() );
		if ( '' === $s['from_name'] ) {
			$s['from_name'] = wp_specialchars_decode( get_bloginfo( 'name' ), ENT_QUOTES );
		}
		if ( '' === $s['admin_email'] ) {
			$s['admin_email'] = get_option( 'admin_email' );
		}
		if ( ! is_array( $s['products'] ) ) {
			$s['products'] = array();
		}
		if ( ! is_array( $s['wc_statuses'] ) ) {
			$s['wc_statuses'] = array( 'completed' );
		}
		return $s;
	}

	public static function get( $key ) {
		$all = self::all();
		return isset( $all[ $key ] ) ? $all[ $key ] : null;
	}

	public static function save( array $patch ) {
		$saved = get_option( self::OPTION, array() );
		update_option( self::OPTION, array_merge( is_array( $saved ) ? $saved : array(), $patch ), false );
	}

	/** 바깥 서비스가 부르는 웹훅 주소의 비밀값. 없으면 한 번 만들어 둔다. */
	public static function webhook_token() {
		$token = self::get( 'webhook_token' );
		if ( ! $token ) {
			$token = bin2hex( random_bytes( 16 ) );
			self::save( array( 'webhook_token' => $token ) );
		}
		return $token;
	}

	/**
	 * 결제된 상품에 어떤 키를 줄지 찾는다.
	 * 상품 번호가 같거나, 상품명에 적어 둔 글자가 들어 있으면 그 줄을 쓴다.
	 * @return array{type:string, app_url:string}|null
	 */
	public static function match_product( $product_ref, $product_title ) {
		$s     = self::all();
		$ref   = trim( (string) $product_ref );
		$title = (string) $product_title;
		foreach ( $s['products'] as $row ) {
			$match = isset( $row['match'] ) ? trim( (string) $row['match'] ) : '';
			if ( '' === $match ) {
				continue;
			}
			$hit = ctype_digit( $match )
				? ( $match === $ref )
				: ( '' !== $title && false !== self::lower_pos( $title, $match ) );
			if ( $hit ) {
				return array(
					'type'    => isset( $row['type'] ) ? $row['type'] : 'piano',
					'app_url' => ! empty( $row['app_url'] ) ? $row['app_url'] : $s['app_url'],
				);
			}
		}
		if ( $s['default_type'] ) {
			return array( 'type' => $s['default_type'], 'app_url' => $s['app_url'] );
		}
		return null;
	}

	private static function lower_pos( $haystack, $needle ) {
		if ( function_exists( 'mb_stripos' ) ) {
			return mb_stripos( $haystack, $needle, 0, 'UTF-8' );
		}
		return stripos( $haystack, $needle );
	}

	// ── 진단 기록 (최근 60건) ─────────────────────────────────

	public static function log( $message, $level = 'info' ) {
		$log = get_option( self::LOG, array() );
		if ( ! is_array( $log ) ) {
			$log = array();
		}
		array_unshift( $log, array( 'at' => current_time( 'mysql' ), 'level' => $level, 'msg' => (string) $message ) );
		update_option( self::LOG, array_slice( $log, 0, 60 ), false );
	}

	public static function logs() {
		$log = get_option( self::LOG, array() );
		return is_array( $log ) ? $log : array();
	}
}
