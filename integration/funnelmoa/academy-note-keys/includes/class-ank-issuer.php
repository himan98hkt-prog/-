<?php
/**
 * 발급 — 주문 하나에 키 하나를 만들고, 대장에 적고, 메일로 보낸다.
 * 결제 연동(우커머스·코스모스팜·웹훅)과 관리자 수동 발급이 모두 이 한 곳을 지난다.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class ANK_Issuer {

	/**
	 * @param array $args {
	 *   @type string $order_ref     주문을 가리키는 고유값 (같은 값으로는 한 번만 발급된다)
	 *   @type string $source        woocommerce | cosmosfarm | webhook | manual
	 *   @type string $product_ref   상품 번호
	 *   @type string $product_title 상품명
	 *   @type string $email         받는 사람
	 *   @type string $name          받는 사람 이름
	 *   @type string $type          키 종류를 직접 정할 때 (없으면 상품 연결 설정을 따른다)
	 *   @type string $memo
	 * }
	 * @return array{status:string, row?:array, sent?:bool, reason?:string}
	 *         status: issued(새로 발급) | duplicate(이미 발급된 주문) | skipped(연결 안 된 상품) | error
	 */
	public static function issue( array $args ) {
		$args = array_merge(
			array( 'order_ref' => '', 'source' => 'manual', 'product_ref' => '', 'product_title' => '', 'email' => '', 'name' => '', 'type' => '', 'memo' => '', 'app_url' => '' ),
			$args
		);
		$order_ref = substr( trim( (string) $args['order_ref'] ), 0, 120 );
		if ( '' === $order_ref ) {
			return array( 'status' => 'error', 'reason' => '주문 번호가 없습니다' );
		}

		$types = ANK_Keys::types();
		$match = null;
		if ( $args['type'] && isset( $types[ $args['type'] ] ) ) {
			$match = array( 'type' => $args['type'], 'app_url' => $args['app_url'] ? $args['app_url'] : ANK_Settings::get( 'app_url' ) );
		} else {
			$match = ANK_Settings::match_product( $args['product_ref'], $args['product_title'] );
		}
		if ( ! $match ) {
			ANK_Settings::log( sprintf( '연결되지 않은 상품이라 발급하지 않았습니다 — %s (번호 %s, 주문 %s)', $args['product_title'], $args['product_ref'], $order_ref ) );
			return array( 'status' => 'skipped', 'reason' => '연결되지 않은 상품' );
		}
		if ( ! isset( $types[ $match['type'] ] ) ) {
			$match['type'] = 'piano';
		}

		// 이미 발급된 주문 — 새 키를 만들지 않는다. 지난번에 메일이 못 나갔다면 그것만 다시 시도한다.
		$existing = ANK_Store::find_by_order( $order_ref );
		if ( $existing ) {
			$sent = false;
			if ( 0 === (int) $existing['send_count'] && is_email( $existing['email'] ) ) {
				$sent = self::deliver( $existing, $match['app_url'] );
			}
			return array( 'status' => 'duplicate', 'row' => $existing, 'sent' => $sent );
		}

		$email = sanitize_email( $args['email'] );
		$row   = array(
			'order_ref'     => $order_ref,
			'source'        => substr( sanitize_key( $args['source'] ), 0, 30 ),
			'product_ref'   => substr( (string) $args['product_ref'], 0, 60 ),
			'product_title' => substr( wp_strip_all_tags( (string) $args['product_title'] ), 0, 255 ),
			'key_type'      => $match['type'],
			'license_key'   => ANK_Keys::generate( $match['type'] ),
			'email'         => $email,
			'name'          => substr( wp_strip_all_tags( (string) $args['name'] ), 0, 120 ),
			'memo'          => substr( wp_strip_all_tags( (string) $args['memo'] ), 0, 255 ),
		);

		$id = ANK_Store::insert( $row );
		if ( ! $id ) {
			// 같은 주문이 동시에 두 번 들어와 다른 쪽이 먼저 적었다 — 그쪽 것을 쓴다
			$existing = ANK_Store::find_by_order( $order_ref );
			if ( $existing ) {
				return array( 'status' => 'duplicate', 'row' => $existing, 'sent' => false );
			}
			ANK_Settings::log( '발급 대장에 적지 못했습니다 — 주문 ' . $order_ref, 'error' );
			return array( 'status' => 'error', 'reason' => '발급 대장에 적지 못했습니다' );
		}
		$row = ANK_Store::find( $id );

		$sent = self::deliver( $row, $match['app_url'] );
		if ( ! $sent ) {
			self::warn_admin( $row );
		}
		do_action( 'ank_key_issued', $row, $sent );
		return array( 'status' => 'issued', 'row' => ANK_Store::find( $id ), 'sent' => $sent );
	}

	/** 대장에 있는 키를 다시 보낸다 (관리 화면의 '다시 보내기') */
	public static function resend( $id ) {
		$row = ANK_Store::find( $id );
		if ( ! $row ) {
			return false;
		}
		$match = ANK_Settings::match_product( $row['product_ref'], $row['product_title'] );
		return self::deliver( $row, $match ? $match['app_url'] : ANK_Settings::get( 'app_url' ) );
	}

	private static function deliver( array $row, $app_url ) {
		if ( ! is_email( $row['email'] ) ) {
			ANK_Settings::log( sprintf( '메일 주소가 없어 보내지 못했습니다 — 주문 %s (키는 발급 내역에 있습니다)', $row['order_ref'] ), 'error' );
			return false;
		}
		$sent = ANK_Mailer::send( $row, $app_url );
		if ( $sent ) {
			ANK_Store::mark_sent( $row['id'] );
			ANK_Settings::log( sprintf( '%s 에게 인증키를 보냈습니다 — %s (주문 %s)', $row['email'], $row['product_title'], $row['order_ref'] ) );
		} else {
			ANK_Settings::log( sprintf( '메일 발송에 실패했습니다 — %s (주문 %s). 발급 내역에서 다시 보낼 수 있습니다', $row['email'], $row['order_ref'] ), 'error' );
		}
		return $sent;
	}

	/** 고객에게 메일이 나가지 못했을 때 판매자에게라도 알린다 — 결제하고 키를 못 받는 일이 없도록 */
	private static function warn_admin( array $row ) {
		$admin = ANK_Settings::get( 'admin_email' );
		if ( ! is_email( $admin ) ) {
			return;
		}
		$body = "인증키는 발급됐지만 고객에게 메일을 보내지 못했습니다.\n\n"
			. '주문: ' . $row['order_ref'] . "\n"
			. '상품: ' . $row['product_title'] . "\n"
			. '고객: ' . $row['name'] . ' <' . $row['email'] . ">\n"
			. '인증키: ' . $row['license_key'] . "\n\n"
			. "워드프레스 관리자 > 관리노트 인증키 > 발급 내역에서 메일 주소를 확인하고 '다시 보내기'를 눌러 주세요.";
		wp_mail( $admin, '[확인 필요] 인증키 메일을 보내지 못했습니다', $body );
	}
}
