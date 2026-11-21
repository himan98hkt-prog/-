<?php
/**
 * 인증키 안내 메일.
 *
 * 받는 사람은 컴퓨터가 익숙하지 않은 원장님이다. 그래서
 *   · 인증키를 크게, 한 덩어리로 보여 주고
 *   · "눌러서 바로 시작하기" 버튼 하나로 입력 없이 인증까지 끝나게 하고
 *   · 버튼이 안 될 때를 위한 세 줄짜리 방법만 덧붙인다.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class ANK_Mailer {

	/** 앱이 읽는 주소 형식: …/lite.html#key=XXXX-XXXX-XXXX (앱이 열리면서 스스로 인증한다) */
	public static function start_url( $app_url, $key ) {
		$app_url = trim( (string) $app_url );
		if ( '' === $app_url ) {
			return '';
		}
		$base = explode( '#', $app_url, 2 );
		return $base[0] . '#key=' . rawurlencode( $key );
	}

	public static function vars( array $row, $app_url ) {
		return array(
			'{이름}'     => '' !== $row['name'] ? $row['name'] : '원장',
			'{인증키}'   => $row['license_key'],
			'{상품명}'   => '' !== $row['product_title'] ? $row['product_title'] : '학원 관리노트',
			'{주문번호}' => $row['order_ref'],
			'{사이트명}' => wp_specialchars_decode( get_bloginfo( 'name' ), ENT_QUOTES ),
			'{앱주소}'   => (string) $app_url,
			'{바로시작}' => self::start_url( $app_url, $row['license_key'] ),
		);
	}

	public static function render( $template, array $vars ) {
		return strtr( (string) $template, $vars );
	}

	/**
	 * @return bool 보냈으면 true
	 */
	public static function send( array $row, $app_url ) {
		if ( ! is_email( $row['email'] ) ) {
			return false;
		}
		$s       = ANK_Settings::all();
		$vars    = self::vars( $row, $app_url );
		$subject = self::render( $s['subject'], $vars );
		$html    = self::html( $row, $vars, $s );

		$headers = array( 'Content-Type: text/html; charset=UTF-8' );
		if ( is_email( $s['from_email'] ) ) {
			$headers[] = sprintf( 'From: %s <%s>', self::header_name( $s['from_name'] ), $s['from_email'] );
		}
		if ( is_email( $s['admin_email'] ) ) {
			$headers[] = 'Reply-To: ' . $s['admin_email'];
			if ( ! empty( $s['admin_copy'] ) && strtolower( $s['admin_email'] ) !== strtolower( $row['email'] ) ) {
				$headers[] = 'Bcc: ' . $s['admin_email'];
			}
		}

		$args = apply_filters(
			'ank_mail_args',
			array( 'to' => $row['email'], 'subject' => $subject, 'message' => $html, 'headers' => $headers ),
			$row
		);
		return (bool) wp_mail( $args['to'], $args['subject'], $args['message'], $args['headers'] );
	}

	private static function header_name( $name ) {
		return '=?UTF-8?B?' . base64_encode( (string) $name ) . '?=';
	}

	private static function paragraphs( $text ) {
		$out = '';
		foreach ( preg_split( '/\r\n|\r|\n/', trim( (string) $text ) ) as $line ) {
			if ( '' === trim( $line ) ) {
				continue;
			}
			$out .= '<p style="margin:0 0 8px;font-size:15px;line-height:1.75;color:#3d3a36;">' . esc_html( $line ) . '</p>';
		}
		return $out;
	}

	/** 메일 프로그램마다 CSS 지원이 달라 표와 인라인 스타일로만 짠다 */
	public static function html( array $row, array $vars, array $s ) {
		$key   = esc_html( $row['license_key'] );
		$start = $vars['{바로시작}'];
		$app   = $vars['{앱주소}'];
		$intro = self::paragraphs( self::render( $s['intro'], $vars ) );
		$outro = self::paragraphs( self::render( $s['outro'], $vars ) );
		$title = esc_html( $vars['{상품명}'] );
		$site  = esc_html( $vars['{사이트명}'] );

		$button = '';
		$steps  = '';
		if ( '' !== $start ) {
			$button = '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px auto 6px;"><tr><td style="border-radius:12px;background:#2c4a7c;">'
				. '<a href="' . esc_url( $start ) . '" style="display:inline-block;padding:16px 34px;font-size:17px;font-weight:bold;color:#ffffff;text-decoration:none;">눌러서 바로 시작하기</a>'
				. '</td></tr></table>'
				. '<p style="margin:0 0 4px;font-size:13px;color:#8a837a;text-align:center;">버튼을 누르면 인증키가 자동으로 입력됩니다.</p>';
			$steps  = '<p style="margin:0 0 6px;font-size:14px;font-weight:bold;color:#1a1714;">버튼이 열리지 않으면</p>'
				. '<ol style="margin:0;padding-left:20px;font-size:14px;line-height:1.9;color:#3d3a36;">'
				. '<li>인터넷 주소창에 <a href="' . esc_url( $app ) . '" style="color:#2c4a7c;">' . esc_html( $app ) . '</a> 를 넣고 엽니다.</li>'
				. '<li>첫 화면의 <b>인증키 입력</b> 칸에 위 인증키를 넣습니다. (이 메일을 통째로 복사해 붙여 넣어도 됩니다)</li>'
				. '<li><b>인증하고 시작하기</b>를 누릅니다.</li>'
				. '</ol>';
		} else {
			$steps = '<p style="margin:0 0 6px;font-size:14px;font-weight:bold;color:#1a1714;">사용 방법</p>'
				. '<ol style="margin:0;padding-left:20px;font-size:14px;line-height:1.9;color:#3d3a36;">'
				. '<li>앱을 엽니다.</li>'
				. '<li>첫 화면의 <b>인증키 입력</b> 칸에 위 인증키를 넣습니다.</li>'
				. '<li><b>인증하고 시작하기</b>를 누릅니다.</li>'
				. '</ol>';
		}

		return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>'
			. '<body style="margin:0;padding:0;background:#f4efe4;font-family:-apple-system,BlinkMacSystemFont,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;">'
			. '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4efe4;"><tr><td align="center" style="padding:28px 14px;">'
			. '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:18px;overflow:hidden;">'
			. '<tr><td style="height:5px;background:#c5a059;font-size:0;line-height:0;">&nbsp;</td></tr>'
			. '<tr><td style="padding:30px 30px 8px;">'
			. '<p style="margin:0 0 6px;font-size:12px;letter-spacing:2px;color:#a8843f;font-weight:bold;">인증키 안내</p>'
			. '<h1 style="margin:0 0 16px;font-size:22px;line-height:1.4;color:#1a1714;">' . $title . '</h1>'
			. $intro
			. '</td></tr>'
			. '<tr><td style="padding:10px 30px 0;">'
			. '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fdf8ec;border:1px solid #ecdcb4;border-radius:14px;"><tr><td align="center" style="padding:20px 12px;">'
			. '<p style="margin:0 0 6px;font-size:13px;color:#8a837a;">내 인증키</p>'
			. '<p style="margin:0;font-size:28px;font-weight:bold;letter-spacing:3px;color:#1a1714;font-family:Consolas,Menlo,monospace;">' . $key . '</p>'
			. '</td></tr></table>'
			. $button
			. '</td></tr>'
			. '<tr><td style="padding:18px 30px 6px;">' . $steps . '</td></tr>'
			. '<tr><td style="padding:16px 30px 28px;">' . $outro . '</td></tr>'
			. '<tr><td style="padding:16px 30px;background:#faf8f4;border-top:1px solid #e9e3d9;">'
			. '<p style="margin:0;font-size:12px;color:#8a837a;">' . $site . ' · 주문 ' . esc_html( $row['order_ref'] ) . '</p>'
			. '</td></tr>'
			. '</table></td></tr></table></body></html>';
	}
}
