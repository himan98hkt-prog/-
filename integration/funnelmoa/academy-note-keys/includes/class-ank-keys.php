<?php
/**
 * 인증키 생성·검증.
 *
 * 두 앱(학원 관리노트 · 피아노학원 관리노트)이 브라우저 안에서 쓰는 규칙을 PHP 로 그대로 옮긴 것이다.
 * 여기서 만든 키가 앱에서 열리려면 값(salt · 문자표 · 해시식)이 앱과 한 글자도 달라서는 안 된다.
 * 바꾸면 이미 판매된 키가 전부 열리지 않게 된다 — 절대 수정하지 말 것.
 *
 * 워드프레스 함수에 기대지 않는 순수 PHP 다 (명령줄 테스트에서 그대로 불러 쓴다).
 */

if ( ! class_exists( 'ANK_Keys' ) ) :

final class ANK_Keys {

	/** 학원 관리노트 방식 (src/core/license.js 와 동일) */
	const SALT = 'ACADEMY-NOTE::2026::a7f3-kQ9v-Zt2m::v1';
	const B32  = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

	/** 피아노학원 관리노트 방식 (src/core/license-piano.js 와 동일) */
	const PIANO_SALT  = 'PAL-x7Qm3vK9nR-accelssam-2026';
	const PIANO_CHARS = 'ACDEFGHJKLMNPQRTUVWXY34679';

	/**
	 * 판매할 수 있는 키 종류.
	 * 'piano' 는 피아노 앱과 학원 앱 양쪽에서 그대로 열리는 공용키라 기본값으로 쓴다.
	 */
	public static function types() {
		return array(
			'piano'  => array( 'label' => '공용키 — 피아노 관리노트 + 학원 관리노트 (Pro)', 'scheme' => 'piano' ),
			'A-pro'  => array( 'label' => '학원 관리노트 통합키 Pro', 'scheme' => 'academy', 'product' => 'A', 'plan' => 'P' ),
			'A-lite' => array( 'label' => '학원 관리노트 통합키 Lite', 'scheme' => 'academy', 'product' => 'A', 'plan' => 'L' ),
			'M-pro'  => array( 'label' => '학원 관리노트 전용 Pro', 'scheme' => 'academy', 'product' => 'M', 'plan' => 'P' ),
			'M-lite' => array( 'label' => '학원 관리노트 전용 Lite', 'scheme' => 'academy', 'product' => 'M', 'plan' => 'L' ),
			'K-pro'  => array( 'label' => '피아노 관리노트 전용 Pro (패치된 피아노 앱)', 'scheme' => 'academy', 'product' => 'K', 'plan' => 'P' ),
			'K-lite' => array( 'label' => '피아노 관리노트 전용 Lite (패치된 피아노 앱)', 'scheme' => 'academy', 'product' => 'K', 'plan' => 'L' ),
		);
	}

	/** 키 한 개 발급. 모르는 종류면 공용키로 만든다. */
	public static function generate( $type = 'piano' ) {
		$types = self::types();
		$t     = isset( $types[ $type ] ) ? $types[ $type ] : $types['piano'];
		if ( 'piano' === $t['scheme'] ) {
			return self::generate_piano();
		}
		$body = $t['product'] . $t['plan'] . self::random_chars( self::B32, 6 );
		return self::format( $body . self::checksum( $body ) );
	}

	/** 표기를 XXXX-XXXX-XXXX 로 맞춘다 */
	public static function format( $raw ) {
		$k = self::normalize( $raw );
		return trim( chunk_split( $k, 4, '-' ), '-' );
	}

	public static function normalize( $key ) {
		return preg_replace( '/[^0-9A-Z]/', '', strtoupper( (string) $key ) );
	}

	/**
	 * 키 판정.
	 * @return array{ok:bool, scheme?:string, product?:string, plan?:string, key?:string}
	 */
	public static function verify( $key ) {
		$k = self::normalize( $key );
		if ( 12 !== strlen( $k ) ) {
			return array( 'ok' => false );
		}
		$body = substr( $k, 0, 8 );
		if ( self::checksum( $body ) === substr( $k, 8 ) ) {
			$head = $body[0];
			if ( 'L' === $head || 'P' === $head ) { // 제품 문자가 없던 초기 발급분
				return array( 'ok' => true, 'scheme' => 'academy', 'product' => 'A', 'plan' => 'P' === $head ? 'pro' : 'lite', 'key' => self::format( $k ) );
			}
			if ( false !== strpos( 'AMK', $head ) && ( 'L' === $body[1] || 'P' === $body[1] ) ) {
				return array( 'ok' => true, 'scheme' => 'academy', 'product' => $head, 'plan' => 'P' === $body[1] ? 'pro' : 'lite', 'key' => self::format( $k ) );
			}
			return array( 'ok' => false );
		}
		if ( self::piano_check_digits( substr( $k, 0, 8 ) ) === substr( $k, 8 ) ) {
			return array( 'ok' => true, 'scheme' => 'piano', 'product' => 'K', 'plan' => 'pro', 'key' => self::format( $k ) );
		}
		return array( 'ok' => false );
	}

	// ── 학원 관리노트 방식 ─────────────────────────────────────

	/** FNV-1a 32bit + 최종 확산. 자바스크립트의 Math.imul 과 같은 32비트 곱셈이다. */
	private static function hash32( $str ) {
		$h = 0x811c9dc5;
		foreach ( self::utf16_units( $str ) as $c ) {
			$h ^= $c;
			$h  = ( $h * 0x01000193 ) & 0xFFFFFFFF;
		}
		$h ^= $h >> 15;
		$h  = ( $h * 0x2545f491 ) & 0xFFFFFFFF;
		$h ^= $h >> 13;
		return $h & 0xFFFFFFFF;
	}

	public static function checksum( $body, $salt = self::SALT ) {
		$h   = self::hash32( $salt . '|' . $body );
		$out = '';
		for ( $i = 0; $i < 4; $i++ ) {
			$out = self::B32[ ( $h >> ( $i * 5 ) ) & 31 ] . $out;
		}
		return $out;
	}

	// ── 피아노 관리노트 방식 ───────────────────────────────────

	/**
	 * 원본의 2중 해시.
	 *
	 * 원본(자바스크립트)은 h1 을 `((h1 ^ c) * 16777619) >>> 0` 으로 계산한다. 이 곱은 2^53 을 넘어
	 * 배정밀도 실수의 반올림이 끼어든다. 정수로 "정확히" 계산하면 오히려 값이 달라지므로,
	 * 같은 반올림이 일어나도록 일부러 실수(double)로 곱한다. PHP 의 float 도 IEEE 754 배정밀도라 결과가 같다.
	 */
	private static function piano_hash( $str ) {
		$h1 = 0x811c9dc5;
		$h2 = 0x1000193;
		foreach ( self::utf16_units( $str ) as $c ) {
			$x = ( $h1 ^ $c ) & 0xFFFFFFFF;
			if ( $x >= 0x80000000 ) {
				$x -= 0x100000000; // 자바스크립트의 ^ 는 부호 있는 32비트를 돌려준다
			}
			$p = fmod( (float) $x * 16777619.0, 4294967296.0 );
			if ( $p < 0 ) {
				$p += 4294967296.0;
			}
			$h1 = (int) $p;
			$h2 = ( ( ( $h2 + $c * 31 ) & 0xFFFFFFFF ) ^ ( ( $h2 << 5 ) & 0xFFFFFFFF ) ) & 0xFFFFFFFF;
		}
		return array( $h1, $h2 );
	}

	/** (h1 · 2^32 + h2) 를 26진수로 낮은 자리부터 뽑는다. 64비트를 넘지 않게 두 덩어리로 나눠 나눈다. */
	private static function piano_encode( $h1, $h2, $length ) {
		$n   = strlen( self::PIANO_CHARS );
		$out = '';
		for ( $i = 0; $i < $length; $i++ ) {
			$r    = $h1 % $n;
			$h1   = intdiv( $h1, $n );
			$t    = $r * 4294967296 + $h2;
			$out .= self::PIANO_CHARS[ $t % $n ];
			$h2   = intdiv( $t, $n );
		}
		return $out;
	}

	public static function piano_check_digits( $head ) {
		list( $h1, $h2 ) = self::piano_hash( self::PIANO_SALT . '#SV#' . strtoupper( (string) $head ) );
		return self::piano_encode( $h1, $h2, 4 );
	}

	/** 미리 만들어 두는 자기검증 키 — 학원명 없이 두 앱에서 그대로 열린다 */
	public static function generate_piano() {
		$head = self::random_chars( self::PIANO_CHARS, 8 );
		return self::format( $head . self::piano_check_digits( $head ) );
	}

	/** 학원명에서 계산하는 키 (기존 피아노 발급기의 '학원명 방식') */
	public static function piano_key_for_name( $name ) {
		$norm = self::piano_normalize_name( $name );
		list( $h1, $h2 ) = self::piano_hash( self::PIANO_SALT . '|' . $norm . '|' . self::PIANO_SALT );
		return self::format( self::piano_encode( $h1, $h2, 12 ) );
	}

	public static function piano_normalize_name( $s ) {
		$s = preg_replace( '/\s+/u', '', (string) $s );
		$s = preg_replace( '/[()（）·.,\-]/u', '', $s );
		return function_exists( 'mb_strtolower' ) ? mb_strtolower( $s, 'UTF-8' ) : strtolower( $s );
	}

	// ── 공용 도구 ─────────────────────────────────────────────

	private static function random_chars( $alphabet, $n ) {
		$out = '';
		$max = strlen( $alphabet ) - 1;
		for ( $i = 0; $i < $n; $i++ ) {
			$out .= $alphabet[ random_int( 0, $max ) ];
		}
		return $out;
	}

	/**
	 * 자바스크립트의 charCodeAt 과 같은 값(UTF-16 코드 단위)의 배열.
	 * mbstring 이 없는 서버에서도 돌도록 UTF-8 을 직접 푼다.
	 */
	private static function utf16_units( $str ) {
		$str   = (string) $str;
		$units = array();
		$len   = strlen( $str );
		for ( $i = 0; $i < $len; ) {
			$b = ord( $str[ $i ] );
			if ( $b < 0x80 ) {
				$cp = $b;
				$i += 1;
			} elseif ( ( $b & 0xE0 ) === 0xC0 && $i + 1 < $len ) {
				$cp = ( ( $b & 0x1F ) << 6 ) | ( ord( $str[ $i + 1 ] ) & 0x3F );
				$i += 2;
			} elseif ( ( $b & 0xF0 ) === 0xE0 && $i + 2 < $len ) {
				$cp = ( ( $b & 0x0F ) << 12 ) | ( ( ord( $str[ $i + 1 ] ) & 0x3F ) << 6 ) | ( ord( $str[ $i + 2 ] ) & 0x3F );
				$i += 3;
			} elseif ( ( $b & 0xF8 ) === 0xF0 && $i + 3 < $len ) {
				$cp = ( ( $b & 0x07 ) << 18 ) | ( ( ord( $str[ $i + 1 ] ) & 0x3F ) << 12 ) | ( ( ord( $str[ $i + 2 ] ) & 0x3F ) << 6 ) | ( ord( $str[ $i + 3 ] ) & 0x3F );
				$i += 4;
			} else {
				$cp = 0xFFFD;
				$i += 1;
			}
			if ( $cp >= 0x10000 ) {
				$cp     -= 0x10000;
				$units[] = 0xD800 | ( $cp >> 10 );
				$units[] = 0xDC00 | ( $cp & 0x3FF );
			} else {
				$units[] = $cp;
			}
		}
		return $units;
	}
}

endif;
