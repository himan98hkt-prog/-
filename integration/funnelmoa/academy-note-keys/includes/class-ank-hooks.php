<?php
/**
 * 결제 연동 — "결제가 끝났다" 는 신호를 받아 발급으로 넘긴다.
 *
 * 퍼널모아(코스모스팜 워드프레스 호스팅)에서 결제가 지나가는 길은 세 가지다.
 *   1) 코스모스팜 회원관리의 결제 상품      → cosmosfarm_members_subscription_request_pay
 *   2) 우커머스 주문                        → woocommerce_order_status_{completed|processing}
 *   3) 그 밖의 결제 도구                    → 웹훅 주소(REST) 또는 academy_note_issue_key 액션
 * 어느 길로 오든 같은 주문에는 키가 한 번만 나간다(ANK_Issuer 가 주문 번호로 막는다).
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class ANK_Hooks {

	public static function init() {
		// 1) 코스모스팜 회원관리 — 첫 결제가 성공한 뒤 실행된다
		add_action( 'cosmosfarm_members_subscription_request_pay', array( __CLASS__, 'on_cosmosfarm_pay' ), 20, 3 );

		// 2) 우커머스
		foreach ( (array) ANK_Settings::get( 'wc_statuses' ) as $status ) {
			add_action( 'woocommerce_order_status_' . sanitize_key( $status ), array( __CLASS__, 'on_wc_order' ), 20, 1 );
		}

		// 3) 다른 코드·서비스에서 직접 부르는 길
		add_action( 'academy_note_issue_key', array( __CLASS__, 'on_custom_action' ), 10, 1 );
		add_action( 'rest_api_init', array( __CLASS__, 'register_rest' ) );

		add_shortcode( 'academy_note_keys', array( __CLASS__, 'shortcode_my_keys' ) );
	}

	// ── 코스모스팜 회원관리 ───────────────────────────────────

	/**
	 * 코스모스팜의 주문·상품 객체는 버전에 따라 메서드 이름이 조금씩 다르다.
	 * 있는 것만 골라 읽고, 무엇을 읽었는지 진단 기록에 남겨 연결 상태를 눈으로 확인할 수 있게 한다.
	 */
	public static function on_cosmosfarm_pay( $order = null, $product = null, $custom_data = null ) {
		$order_id   = self::read( $order, array( 'ID', 'id', 'order_id', 'get_id' ) );
		$product_id = self::read( $product, array( 'ID', 'id', 'product_id', 'get_id' ) );
		$title      = self::read( $product, array( 'title', 'get_title', 'name' ) );
		if ( '' === $title && $product_id && function_exists( 'get_the_title' ) ) {
			$title = get_the_title( (int) $product_id );
		}

		$user = self::read( $order, array( 'user', 'User', 'get_user' ), null );
		if ( ! is_object( $user ) ) {
			$user_id = (int) self::read( $order, array( 'user_id', 'get_user_id' ), 0 );
			$user    = $user_id ? get_userdata( $user_id ) : wp_get_current_user();
		}

		$email = self::read( $order, array( 'buyer_email', 'get_buyer_email', 'email' ) );
		$name  = self::read( $order, array( 'buyer_name', 'get_buyer_name', 'name' ) );
		if ( $order_id ) {
			if ( ! is_email( $email ) ) {
				$email = get_post_meta( (int) $order_id, 'buyer_email', true );
			}
			if ( '' === $name ) {
				$name = get_post_meta( (int) $order_id, 'buyer_name', true );
			}
		}
		if ( ! is_email( $email ) && is_object( $user ) && ! empty( $user->user_email ) ) {
			$email = $user->user_email;
		}
		if ( '' === (string) $name && is_object( $user ) && ! empty( $user->display_name ) ) {
			$name = $user->display_name;
		}

		// 주문 번호를 못 읽는 버전이라도 같은 사람·같은 상품·같은 분(分)에는 한 번만 나가게 한다
		$order_ref = $order_id
			? 'cf:' . $order_id
			: 'cf:' . md5( strtolower( (string) $email ) . '|' . $product_id . '|' . gmdate( 'YmdHi' ) );

		ANK_Settings::log(
			sprintf(
				'코스모스팜 결제 신호를 받았습니다 — 주문 %s, 상품 %s(%s), 메일 %s',
				$order_id ? $order_id : '(번호 없음)',
				$title ? $title : '(이름 없음)',
				$product_id ? $product_id : '-',
				$email ? $email : '(없음)'
			)
		);

		ANK_Issuer::issue(
			array(
				'order_ref'     => $order_ref,
				'source'        => 'cosmosfarm',
				'product_ref'   => (string) $product_id,
				'product_title' => (string) $title,
				'email'         => (string) $email,
				'name'          => (string) $name,
			)
		);
	}

	/** 객체에서 값 하나를 꺼낸다 — 메서드가 있으면 메서드, 없으면 같은 이름의 속성 */
	private static function read( $obj, array $names, $default = '' ) {
		if ( ! is_object( $obj ) ) {
			return $default;
		}
		foreach ( $names as $name ) {
			try {
				if ( is_callable( array( $obj, $name ) ) ) {
					$v = $obj->$name();
				} elseif ( isset( $obj->$name ) ) {
					$v = $obj->$name;
				} else {
					continue;
				}
			} catch ( \Throwable $e ) {
				continue;
			}
			if ( null !== $v && '' !== $v && false !== $v ) {
				return $v;
			}
		}
		return $default;
	}

	// ── 우커머스 ──────────────────────────────────────────────

	public static function on_wc_order( $order_id ) {
		if ( ! function_exists( 'wc_get_order' ) ) {
			return;
		}
		$order = wc_get_order( $order_id );
		if ( ! $order ) {
			return;
		}
		// 한국식 이름은 성+이름을 붙여 쓴다. 이름 칸 하나에 다 적는 가게도 있어 둘을 그냥 잇는다.
		$name  = trim( $order->get_billing_last_name() . $order->get_billing_first_name() );
		$email = $order->get_billing_email();

		foreach ( $order->get_items() as $item_id => $item ) {
			$product_id = (int) $item->get_product_id();
			$title      = $item->get_name();
			$match      = ANK_Settings::match_product( $product_id, $title );
			if ( ! $match && $item->get_variation_id() ) {
				$match = ANK_Settings::match_product( (int) $item->get_variation_id(), $title );
			}
			if ( ! $match ) {
				continue; // 관리노트가 아닌 다른 상품
			}
			$qty = max( 1, (int) $item->get_quantity() );
			for ( $n = 1; $n <= $qty; $n++ ) {
				$result = ANK_Issuer::issue(
					array(
						'order_ref'     => sprintf( 'wc:%d:%d:%d', $order_id, $item_id, $n ),
						'source'        => 'woocommerce',
						'product_ref'   => (string) $product_id,
						'product_title' => $title,
						'email'         => $email,
						'name'          => $name,
						'type'          => $match['type'],
						'app_url'       => $match['app_url'],
					)
				);
				if ( 'issued' === $result['status'] && is_callable( array( $order, 'add_order_note' ) ) ) {
					$order->add_order_note( sprintf( '관리노트 인증키 발급: %s (%s)', $result['row']['license_key'], $result['sent'] ? '메일 발송됨' : '메일 발송 실패' ) );
				}
			}
		}
	}

	// ── 직접 호출 ─────────────────────────────────────────────

	public static function on_custom_action( $args ) {
		if ( is_array( $args ) ) {
			ANK_Issuer::issue( array_merge( array( 'source' => 'custom' ), $args ) );
		}
	}

	public static function register_rest() {
		register_rest_route(
			'academy-note/v1',
			'/issue',
			array(
				'methods'             => 'POST',
				'callback'            => array( __CLASS__, 'rest_issue' ),
				'permission_callback' => array( __CLASS__, 'rest_allowed' ),
			)
		);
	}

	/** 주소를 아는 것만으로는 키를 받을 수 없다 — 설정 화면의 비밀값이 맞아야 한다 */
	public static function rest_allowed( $request ) {
		$given = $request->get_header( 'x-ank-token' );
		if ( ! $given ) {
			$given = $request->get_param( 'token' );
		}
		return is_string( $given ) && '' !== $given && hash_equals( ANK_Settings::webhook_token(), $given );
	}

	public static function rest_issue( $request ) {
		$order = (string) $request->get_param( 'order_id' );
		$email = (string) $request->get_param( 'email' );
		if ( '' === $order || ! is_email( $email ) ) {
			return new WP_REST_Response( array( 'ok' => false, 'reason' => 'order_id 와 email 이 필요합니다' ), 400 );
		}
		$result = ANK_Issuer::issue(
			array(
				'order_ref'     => 'hook:' . $order,
				'source'        => 'webhook',
				'product_ref'   => (string) $request->get_param( 'product_id' ),
				'product_title' => (string) $request->get_param( 'product' ),
				'email'         => $email,
				'name'          => (string) $request->get_param( 'name' ),
				'type'          => (string) $request->get_param( 'type' ),
			)
		);
		$ok = in_array( $result['status'], array( 'issued', 'duplicate' ), true );
		return new WP_REST_Response(
			array(
				'ok'     => $ok,
				'status' => $result['status'],
				'key'    => $ok ? $result['row']['license_key'] : null,
				'sent'   => ! empty( $result['sent'] ),
				'reason' => isset( $result['reason'] ) ? $result['reason'] : null,
			),
			$ok ? 200 : 422
		);
	}

	// ── 내 인증키 보기 (마이페이지에 [academy_note_keys] 로 넣는다) ──

	public static function shortcode_my_keys() {
		if ( ! is_user_logged_in() ) {
			return '<p>로그인하면 구매한 인증키를 볼 수 있습니다.</p>';
		}
		$user = wp_get_current_user();
		$rows = ANK_Store::by_email( $user->user_email );
		if ( ! $rows ) {
			return '<p>아직 발급된 인증키가 없습니다.</p>';
		}
		$out = '<div class="ank-my-keys">';
		foreach ( $rows as $row ) {
			$match = ANK_Settings::match_product( $row['product_ref'], $row['product_title'] );
			$start = ANK_Mailer::start_url( $match ? $match['app_url'] : ANK_Settings::get( 'app_url' ), $row['license_key'] );
			$out  .= '<div style="border:1px solid #e9e3d9;border-radius:12px;padding:16px 18px;margin:0 0 12px;background:#fff;">'
				. '<div style="font-size:14px;color:#8a837a;">' . esc_html( $row['product_title'] ) . ' · ' . esc_html( substr( $row['created_at'], 0, 10 ) ) . '</div>'
				. '<div style="font:bold 22px/1.6 Consolas,Menlo,monospace;letter-spacing:2px;">' . esc_html( $row['license_key'] ) . '</div>'
				. ( $start ? '<a href="' . esc_url( $start ) . '" style="display:inline-block;margin-top:6px;padding:10px 18px;border-radius:10px;background:#2c4a7c;color:#fff;text-decoration:none;font-weight:bold;">눌러서 바로 시작하기</a>' : '' )
				. '</div>';
		}
		return $out . '</div>';
	}
}
