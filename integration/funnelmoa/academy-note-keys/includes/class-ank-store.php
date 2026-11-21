<?php
/**
 * 발급 대장 — 어떤 주문에 어떤 키가 나갔는지 남긴다.
 *
 * 같은 주문에는 키를 한 번만 준다. 결제 알림은 여러 번 올 수 있고(PG 재전송, 주문 상태 변경),
 * 그때마다 새 키를 만들면 한 번 결제로 여러 개가 풀린다. order_ref 에 유일 제약을 걸어 막는다.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class ANK_Store {

	const DB_VERSION = '1';

	public static function table() {
		global $wpdb;
		return $wpdb->prefix . 'ank_keys';
	}

	public static function install() {
		global $wpdb;
		$table   = self::table();
		$charset = $wpdb->get_charset_collate();
		$sql     = "CREATE TABLE {$table} (
			id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
			order_ref varchar(120) NOT NULL,
			source varchar(30) NOT NULL DEFAULT '',
			product_ref varchar(60) NOT NULL DEFAULT '',
			product_title varchar(255) NOT NULL DEFAULT '',
			key_type varchar(20) NOT NULL DEFAULT '',
			license_key varchar(20) NOT NULL DEFAULT '',
			email varchar(190) NOT NULL DEFAULT '',
			name varchar(120) NOT NULL DEFAULT '',
			memo varchar(255) NOT NULL DEFAULT '',
			send_count int(11) NOT NULL DEFAULT 0,
			sent_at datetime DEFAULT NULL,
			created_at datetime NOT NULL,
			PRIMARY KEY  (id),
			UNIQUE KEY order_ref (order_ref),
			KEY email (email),
			KEY license_key (license_key)
		) {$charset};";
		require_once ABSPATH . 'wp-admin/includes/upgrade.php';
		dbDelta( $sql );
		update_option( 'ank_db_version', self::DB_VERSION, false );
	}

	public static function maybe_install() {
		if ( get_option( 'ank_db_version' ) !== self::DB_VERSION ) {
			self::install();
		}
	}

	public static function find_by_order( $order_ref ) {
		global $wpdb;
		$table = self::table();
		return $wpdb->get_row( $wpdb->prepare( "SELECT * FROM {$table} WHERE order_ref = %s", $order_ref ), ARRAY_A );
	}

	public static function find( $id ) {
		global $wpdb;
		$table = self::table();
		return $wpdb->get_row( $wpdb->prepare( "SELECT * FROM {$table} WHERE id = %d", $id ), ARRAY_A );
	}

	/**
	 * 새 줄을 넣는다. 같은 주문이 이미 있으면(동시에 두 번 들어온 경우 포함) false.
	 * @return int|false 새 줄 번호
	 */
	public static function insert( array $row ) {
		global $wpdb;
		$wpdb->suppress_errors( true ); // 중복 주문은 정상 흐름이다 — 화면에 DB 오류를 띄우지 않는다
		$ok = $wpdb->insert(
			self::table(),
			array(
				'order_ref'     => $row['order_ref'],
				'source'        => $row['source'],
				'product_ref'   => $row['product_ref'],
				'product_title' => $row['product_title'],
				'key_type'      => $row['key_type'],
				'license_key'   => $row['license_key'],
				'email'         => $row['email'],
				'name'          => $row['name'],
				'memo'          => $row['memo'],
				'created_at'    => current_time( 'mysql' ),
			)
		);
		$wpdb->suppress_errors( false );
		return $ok ? (int) $wpdb->insert_id : false;
	}

	public static function mark_sent( $id ) {
		global $wpdb;
		$table = self::table();
		$wpdb->query( $wpdb->prepare( "UPDATE {$table} SET send_count = send_count + 1, sent_at = %s WHERE id = %d", current_time( 'mysql' ), $id ) );
	}

	public static function update_email( $id, $email ) {
		global $wpdb;
		$wpdb->update( self::table(), array( 'email' => $email ), array( 'id' => (int) $id ) );
	}

	/** 최근 발급분. 검색어는 메일·이름·키·주문번호·상품명 어디에 있어도 찾는다. */
	public static function recent( $search = '', $limit = 100, $offset = 0 ) {
		global $wpdb;
		$table = self::table();
		$limit = max( 1, (int) $limit );
		$offset = max( 0, (int) $offset );
		if ( '' !== $search ) {
			$like = '%' . $wpdb->esc_like( $search ) . '%';
			return $wpdb->get_results(
				$wpdb->prepare(
					"SELECT * FROM {$table} WHERE email LIKE %s OR name LIKE %s OR license_key LIKE %s OR order_ref LIKE %s OR product_title LIKE %s ORDER BY id DESC LIMIT %d OFFSET %d",
					$like, $like, $like, $like, $like, $limit, $offset
				),
				ARRAY_A
			);
		}
		return $wpdb->get_results( $wpdb->prepare( "SELECT * FROM {$table} ORDER BY id DESC LIMIT %d OFFSET %d", $limit, $offset ), ARRAY_A );
	}

	public static function by_email( $email ) {
		global $wpdb;
		$table = self::table();
		return $wpdb->get_results( $wpdb->prepare( "SELECT * FROM {$table} WHERE email = %s ORDER BY id DESC", $email ), ARRAY_A );
	}

	public static function count() {
		global $wpdb;
		$table = self::table();
		return (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$table}" );
	}

	public static function count_unsent() {
		global $wpdb;
		$table = self::table();
		return (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$table} WHERE send_count = 0" );
	}
}
