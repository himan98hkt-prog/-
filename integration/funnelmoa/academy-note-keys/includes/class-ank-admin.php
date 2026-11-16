<?php
/**
 * 관리 화면 — 워드프레스 관리자 > 관리노트 인증키.
 *
 * 탭 네 개: 발급 내역 / 직접 보내기 / 설정 / 연결 상태.
 * 평소에는 볼 일이 없어야 한다(결제되면 알아서 나간다). 고객 문의가 왔을 때 찾아보고 다시 보내는 곳이다.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class ANK_Admin {

	const SLUG = 'academy-note-keys';
	const CAP  = 'manage_options';

	public static function init() {
		add_action( 'admin_menu', array( __CLASS__, 'menu' ) );
		add_action( 'admin_post_ank_save_settings', array( __CLASS__, 'save_settings' ) );
		add_action( 'admin_post_ank_manual_issue', array( __CLASS__, 'manual_issue' ) );
		add_action( 'admin_post_ank_resend', array( __CLASS__, 'resend' ) );
		add_action( 'admin_post_ank_export', array( __CLASS__, 'export' ) );
		add_filter( 'plugin_action_links_' . plugin_basename( ANK_FILE ), array( __CLASS__, 'plugin_links' ) );
	}

	public static function menu() {
		add_menu_page( '관리노트 인증키', '관리노트 인증키', self::CAP, self::SLUG, array( __CLASS__, 'page' ), 'dashicons-admin-network', 58 );
	}

	public static function plugin_links( $links ) {
		array_unshift( $links, '<a href="' . esc_url( self::url( 'settings' ) ) . '">설정</a>' );
		return $links;
	}

	private static function url( $tab = 'list', array $extra = array() ) {
		return add_query_arg( array_merge( array( 'page' => self::SLUG, 'tab' => $tab ), $extra ), admin_url( 'admin.php' ) );
	}

	private static function back( $tab, $notice, $kind = 'ok' ) {
		wp_safe_redirect( self::url( $tab, array( 'ank_notice' => rawurlencode( $notice ), 'ank_kind' => $kind ) ) );
		exit;
	}

	private static function guard( $action ) {
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( '권한이 없습니다.' );
		}
		check_admin_referer( $action );
	}

	// ── 화면 ──────────────────────────────────────────────────

	public static function page() {
		if ( ! current_user_can( self::CAP ) ) {
			return;
		}
		$tab  = isset( $_GET['tab'] ) ? sanitize_key( wp_unslash( $_GET['tab'] ) ) : 'list';
		$tabs = array( 'list' => '발급 내역', 'send' => '직접 보내기', 'settings' => '설정', 'status' => '연결 상태' );
		if ( ! isset( $tabs[ $tab ] ) ) {
			$tab = 'list';
		}

		echo '<div class="wrap ank"><h1>관리노트 인증키</h1>';
		self::styles();
		if ( isset( $_GET['ank_notice'] ) ) {
			$kind = isset( $_GET['ank_kind'] ) && 'error' === $_GET['ank_kind'] ? 'notice-error' : 'notice-success';
			echo '<div class="notice ' . esc_attr( $kind ) . ' is-dismissible"><p>' . esc_html( rawurldecode( wp_unslash( $_GET['ank_notice'] ) ) ) . '</p></div>';
		}
		self::setup_hint();

		echo '<h2 class="nav-tab-wrapper">';
		foreach ( $tabs as $id => $label ) {
			echo '<a class="nav-tab ' . ( $id === $tab ? 'nav-tab-active' : '' ) . '" href="' . esc_url( self::url( $id ) ) . '">' . esc_html( $label ) . '</a>';
		}
		echo '</h2>';

		call_user_func( array( __CLASS__, 'tab_' . $tab ) );
		echo '</div>';
	}

	private static function styles() {
		echo '<style>
			.ank .ank-card{background:#fff;border:1px solid #dcdcde;border-radius:10px;padding:18px 20px;margin:16px 0;max-width:980px}
			.ank .ank-card h2{margin:0 0 6px;font-size:16px}
			.ank .ank-card p.desc{margin:0 0 12px;color:#646970}
			.ank .ank-stats{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
			.ank .ank-stat{background:#fff;border:1px solid #dcdcde;border-radius:10px;padding:12px 18px;min-width:140px}
			.ank .ank-stat b{display:block;font-size:22px}
			.ank .ank-key{font-family:Consolas,Menlo,monospace;font-weight:700;letter-spacing:1px}
			.ank .ank-warn{background:#fcf3e3;border-left:4px solid #dba617;padding:10px 14px;margin:14px 0;max-width:980px}
			.ank .ank-ok{color:#1f7a4d;font-weight:600}.ank .ank-bad{color:#b32d2e;font-weight:600}
			.ank table.ank-map td{padding:4px 8px 4px 0;vertical-align:top}
			.ank ol.ank-steps{margin:8px 0 0 18px;line-height:1.9}
			.ank code.ank-copy{display:inline-block;padding:4px 8px;background:#f0f0f1;border-radius:6px;user-select:all;word-break:break-all}
		</style>';
	}

	/** 아직 할 일이 남았으면 맨 위에서 알려 준다 */
	private static function setup_hint() {
		$s    = ANK_Settings::all();
		$todo = array();
		if ( ! $s['products'] && ! $s['default_type'] ) {
			$todo[] = '<a href="' . esc_url( self::url( 'settings' ) ) . '">설정</a>에서 <b>어떤 상품을 팔 때 키를 보낼지</b> 한 줄 이상 정해 주세요. (아직 연결된 상품이 없어 결제돼도 발급되지 않습니다)';
		}
		if ( '' === trim( $s['app_url'] ) ) {
			$todo[] = '<a href="' . esc_url( self::url( 'settings' ) ) . '">설정</a>에 <b>앱 주소</b>를 넣으면 메일에 “눌러서 바로 시작하기” 버튼이 생깁니다.';
		}
		if ( $todo ) {
			echo '<div class="ank-warn"><b>마무리할 설정이 있습니다</b><ol class="ank-steps"><li>' . wp_kses_post( implode( '</li><li>', $todo ) ) . '</li></ol></div>';
		}
	}

	// 1) 발급 내역
	public static function tab_list() {
		$search = isset( $_GET['s'] ) ? sanitize_text_field( wp_unslash( $_GET['s'] ) ) : '';
		$rows   = ANK_Store::recent( $search, 200 );
		$types  = ANK_Keys::types();

		echo '<div class="ank-stats">'
			. '<div class="ank-stat"><b>' . esc_html( number_format_i18n( ANK_Store::count() ) ) . '</b>지금까지 발급</div>'
			. '<div class="ank-stat"><b class="' . ( ANK_Store::count_unsent() ? 'ank-bad' : '' ) . '">' . esc_html( number_format_i18n( ANK_Store::count_unsent() ) ) . '</b>메일 못 보낸 건</div>'
			. '</div>';

		echo '<form method="get" style="margin:12px 0"><input type="hidden" name="page" value="' . esc_attr( self::SLUG ) . '"><input type="hidden" name="tab" value="list">'
			. '<input type="search" name="s" value="' . esc_attr( $search ) . '" placeholder="메일 · 이름 · 인증키 · 주문번호" style="width:280px"> '
			. '<button class="button">찾기</button> '
			. '<a class="button" href="' . esc_url( wp_nonce_url( admin_url( 'admin-post.php?action=ank_export' ), 'ank_export' ) ) . '">엑셀 파일로 내려받기</a></form>';

		if ( ! $rows ) {
			echo '<div class="ank-card"><p>' . ( $search ? '찾는 내역이 없습니다.' : '아직 발급된 인증키가 없습니다. 결제가 들어오면 여기에 자동으로 쌓입니다.' ) . '</p></div>';
			return;
		}

		echo '<table class="widefat striped" style="max-width:1200px"><thead><tr><th>발급일</th><th>받는 사람</th><th>상품</th><th>인증키</th><th>메일</th><th></th></tr></thead><tbody>';
		foreach ( $rows as $row ) {
			$sent = (int) $row['send_count'] > 0;
			echo '<tr>'
				. '<td>' . esc_html( substr( $row['created_at'], 0, 16 ) ) . '<br><small>' . esc_html( $row['order_ref'] ) . '</small></td>'
				. '<td>' . esc_html( $row['name'] ) . '<br><small>' . esc_html( $row['email'] ? $row['email'] : '(메일 없음)' ) . '</small></td>'
				. '<td>' . esc_html( $row['product_title'] ) . '<br><small>' . esc_html( isset( $types[ $row['key_type'] ] ) ? $types[ $row['key_type'] ]['label'] : $row['key_type'] ) . '</small></td>'
				. '<td><span class="ank-key">' . esc_html( $row['license_key'] ) . '</span></td>'
				. '<td>' . ( $sent ? '<span class="ank-ok">보냄</span><br><small>' . esc_html( substr( (string) $row['sent_at'], 0, 16 ) ) . ( (int) $row['send_count'] > 1 ? ' · ' . (int) $row['send_count'] . '회' : '' ) . '</small>' : '<span class="ank-bad">못 보냄</span>' ) . '</td>'
				. '<td><form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" style="display:flex;gap:6px;align-items:center">'
				. wp_nonce_field( 'ank_resend', '_wpnonce', true, false )
				. '<input type="hidden" name="action" value="ank_resend"><input type="hidden" name="id" value="' . (int) $row['id'] . '">'
				. '<input type="email" name="email" value="' . esc_attr( $row['email'] ) . '" style="width:190px" placeholder="받는 메일">'
				. '<button class="button">다시 보내기</button></form></td>'
				. '</tr>';
		}
		echo '</tbody></table>';
	}

	// 2) 직접 보내기
	public static function tab_send() {
		$me = wp_get_current_user();
		echo '<div class="ank-card"><h2>인증키 직접 보내기</h2><p class="desc">계좌이체로 받았거나, 선물·재발급처럼 결제 없이 키를 줄 때 씁니다. 누르는 즉시 새 키가 만들어져 메일로 나갑니다.</p>'
			. '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '">'
			. wp_nonce_field( 'ank_manual_issue', '_wpnonce', true, false )
			. '<input type="hidden" name="action" value="ank_manual_issue">'
			. '<table class="form-table" role="presentation">'
			. '<tr><th>받는 사람 메일</th><td><input type="email" name="email" class="regular-text" required placeholder="customer@example.com"></td></tr>'
			. '<tr><th>이름</th><td><input type="text" name="name" class="regular-text" placeholder="예) 김원장"></td></tr>'
			. '<tr><th>키 종류</th><td>' . self::type_select( 'type', 'piano' ) . '</td></tr>'
			. '<tr><th>상품명 (메일 제목에 들어갑니다)</th><td><input type="text" name="product_title" class="regular-text" value="학원 관리노트"></td></tr>'
			. '<tr><th>메모</th><td><input type="text" name="memo" class="regular-text" placeholder="예) 계좌이체 11/16"></td></tr>'
			. '</table><p><button class="button button-primary">키 만들어 보내기</button></p></form></div>';

		echo '<div class="ank-card"><h2>메일이 잘 가는지 먼저 확인</h2><p class="desc">내 메일(' . esc_html( $me->user_email ) . ')로 시험 삼아 한 통 보냅니다. 받은 메일의 버튼이 잘 열리는지 확인해 보세요.</p>'
			. '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '">'
			. wp_nonce_field( 'ank_manual_issue', '_wpnonce', true, false )
			. '<input type="hidden" name="action" value="ank_manual_issue"><input type="hidden" name="email" value="' . esc_attr( $me->user_email ) . '">'
			. '<input type="hidden" name="name" value="' . esc_attr( $me->display_name ) . '"><input type="hidden" name="type" value="piano">'
			. '<input type="hidden" name="product_title" value="학원 관리노트"><input type="hidden" name="memo" value="시험 발송">'
			. '<button class="button">내 메일로 시험 발송</button></form></div>';
	}

	private static function type_select( $name, $current ) {
		$out = '<select name="' . esc_attr( $name ) . '">';
		foreach ( ANK_Keys::types() as $id => $t ) {
			$out .= '<option value="' . esc_attr( $id ) . '"' . selected( $current, $id, false ) . '>' . esc_html( $t['label'] ) . '</option>';
		}
		return $out . '</select>';
	}

	// 3) 설정
	public static function tab_settings() {
		$s = ANK_Settings::all();
		echo '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '">'
			. wp_nonce_field( 'ank_save_settings', '_wpnonce', true, false )
			. '<input type="hidden" name="action" value="ank_save_settings">';

		// 상품 연결
		echo '<div class="ank-card"><h2>① 어떤 상품을 팔 때 키를 보낼까요</h2>'
			. '<p class="desc">왼쪽 칸에 <b>상품 번호</b>(숫자) 또는 <b>상품 이름의 일부</b>를 적습니다. 예) <code>관리노트</code> 라고 적으면 이름에 “관리노트”가 들어간 상품이 결제될 때마다 키가 나갑니다.</p>'
			. '<table class="ank-map"><tr><th align="left">상품 번호 또는 이름 일부</th><th align="left">보낼 키</th><th align="left">앱 주소 (비워 두면 아래 기본 주소)</th></tr>';
		$rows = array_merge( $s['products'], array( array(), array() ) );
		foreach ( $rows as $row ) {
			echo '<tr><td><input type="text" name="match[]" value="' . esc_attr( isset( $row['match'] ) ? $row['match'] : '' ) . '" placeholder="예) 관리노트"></td>'
				. '<td>' . self::type_select( 'type[]', isset( $row['type'] ) ? $row['type'] : 'piano' ) . '</td>'
				. '<td><input type="url" name="row_url[]" value="' . esc_attr( isset( $row['app_url'] ) ? $row['app_url'] : '' ) . '" style="width:320px" placeholder="https://"></td></tr>';
		}
		echo '</table><p class="description">줄을 지우려면 왼쪽 칸을 비우고 저장하세요. 저장하면 빈 줄이 다시 두 개 생깁니다.</p>';
		self::found_products();
		echo '</div>';

		echo '<div class="ank-card"><h2>② 앱 주소</h2><p class="desc">학원 관리노트를 올려 둔 주소입니다. 넣어 두면 메일에 <b>“눌러서 바로 시작하기”</b> 버튼이 생기고, 고객은 키를 직접 입력하지 않아도 됩니다.</p>'
			. '<input type="url" name="app_url" value="' . esc_attr( $s['app_url'] ) . '" class="large-text" placeholder="https://내사이트.com/note/lite.html"></div>';

		echo '<div class="ank-card"><h2>③ 메일</h2><table class="form-table" role="presentation">'
			. '<tr><th>보내는 사람 이름</th><td><input type="text" name="from_name" value="' . esc_attr( $s['from_name'] ) . '" class="regular-text"></td></tr>'
			. '<tr><th>보내는 메일 주소</th><td><input type="email" name="from_email" value="' . esc_attr( $s['from_email'] ) . '" class="regular-text"><p class="description">비워 두면 워드프레스 기본 주소로 나갑니다.</p></td></tr>'
			. '<tr><th>판매자 메일</th><td><input type="email" name="admin_email" value="' . esc_attr( $s['admin_email'] ) . '" class="regular-text">'
			. '<p><label><input type="checkbox" name="admin_copy" value="1"' . checked( ! empty( $s['admin_copy'] ), true, false ) . '> 키가 나갈 때마다 나에게도 같은 메일 보내기</label></p>'
			. '<p class="description">고객이 메일에 답장하면 이 주소로 옵니다.</p></td></tr>'
			. '<tr><th>제목</th><td><input type="text" name="subject" value="' . esc_attr( $s['subject'] ) . '" class="large-text"></td></tr>'
			. '<tr><th>첫 인사</th><td><textarea name="intro" rows="3" class="large-text">' . esc_textarea( $s['intro'] ) . '</textarea></td></tr>'
			. '<tr><th>맺음말</th><td><textarea name="outro" rows="3" class="large-text">' . esc_textarea( $s['outro'] ) . '</textarea>'
			. '<p class="description">쓸 수 있는 낱말: <code>{이름}</code> <code>{상품명}</code> <code>{인증키}</code> <code>{주문번호}</code> <code>{사이트명}</code> — 인증키 상자와 시작 버튼은 자동으로 들어갑니다.</p></td></tr>'
			. '</table></div>';

		echo '<div class="ank-card"><h2>④ 그 밖에</h2><table class="form-table" role="presentation">'
			. '<tr><th>연결하지 않은 상품이 결제되면</th><td><select name="default_type"><option value="">키를 보내지 않음 (권장)</option>';
		foreach ( ANK_Keys::types() as $id => $t ) {
			echo '<option value="' . esc_attr( $id ) . '"' . selected( $s['default_type'], $id, false ) . '>' . esc_html( $t['label'] ) . ' 을 보냄</option>';
		}
		echo '</select><p class="description">관리노트만 파는 사이트라면 여기서 키 종류를 골라 두면 ①을 비워 둬도 됩니다.</p></td></tr>'
			. '<tr><th>우커머스 주문이 이 상태가 되면 발급</th><td>'
			. '<label><input type="checkbox" name="wc_statuses[]" value="completed"' . checked( in_array( 'completed', $s['wc_statuses'], true ), true, false ) . '> 완료됨</label> &nbsp; '
			. '<label><input type="checkbox" name="wc_statuses[]" value="processing"' . checked( in_array( 'processing', $s['wc_statuses'], true ), true, false ) . '> 처리 중 (결제 확인됨)</label>'
			. '<p class="description">카드 결제는 보통 곧바로 “처리 중” 또는 “완료됨”이 됩니다. 무통장입금은 입금 확인 후 상태를 바꿀 때 나갑니다.</p></td></tr>'
			. '</table></div>';

		echo '<p><button class="button button-primary button-hero">저장</button></p></form>';
	}

	/** 사이트에서 찾은 상품을 번호와 함께 보여 준다 — 번호를 찾아 헤매지 않도록 */
	private static function found_products() {
		$found = array();
		if ( function_exists( 'wc_get_products' ) ) {
			foreach ( wc_get_products( array( 'limit' => 40, 'status' => 'publish' ) ) as $p ) {
				$found[] = array( $p->get_id(), $p->get_name(), '우커머스' );
			}
		}
		foreach ( array( 'cosmosfarm_product', 'cosmosfarm_products' ) as $type ) {
			if ( post_type_exists( $type ) ) {
				foreach ( get_posts( array( 'post_type' => $type, 'numberposts' => 40, 'post_status' => 'any' ) ) as $p ) {
					$found[] = array( $p->ID, $p->post_title, '코스모스팜' );
				}
			}
		}
		if ( ! $found ) {
			return;
		}
		echo '<details style="margin-top:10px"><summary>이 사이트에서 찾은 상품 ' . count( $found ) . '개 보기</summary><table class="widefat striped" style="max-width:640px;margin-top:8px"><thead><tr><th>번호</th><th>상품 이름</th><th>종류</th></tr></thead><tbody>';
		foreach ( $found as $f ) {
			echo '<tr><td><code>' . (int) $f[0] . '</code></td><td>' . esc_html( $f[1] ) . '</td><td>' . esc_html( $f[2] ) . '</td></tr>';
		}
		echo '</tbody></table></details>';
	}

	// 4) 연결 상태
	public static function tab_status() {
		$cf = has_action( 'cosmosfarm_members_subscription_request_pay' ) && ( class_exists( 'Cosmosfarm_Members' ) || defined( 'COSMOSFARM_MEMBERS_VERSION' ) );
		$wc = class_exists( 'WooCommerce' );
		$yes = '<span class="ank-ok">연결됨</span>';
		$no  = '<span style="color:#646970">설치되어 있지 않음</span>';

		echo '<div class="ank-card"><h2>결제 연결</h2><table class="widefat striped" style="max-width:720px"><tbody>'
			. '<tr><td>코스모스팜 회원관리 (결제 상품)</td><td>' . ( $cf ? $yes : $no ) . '</td></tr>'
			. '<tr><td>우커머스</td><td>' . ( $wc ? $yes : $no ) . '</td></tr>'
			. '<tr><td>웹훅 주소 (다른 결제 도구용)</td><td>' . $yes . '</td></tr>'
			. '</tbody></table>'
			. '<p class="description">둘 중 사이트에서 실제로 결제에 쓰는 것이 “연결됨”이면 됩니다. 결제가 들어오면 아래 기록에 한 줄씩 남습니다.</p></div>';

		$url = rest_url( 'academy-note/v1/issue' );
		echo '<div class="ank-card"><h2>웹훅 주소</h2><p class="desc">위 두 가지가 아닌 결제 도구(페이앱·스마트스토어 연동·재피어 등)를 쓴다면, 결제 완료 때 아래 주소를 부르게 하면 됩니다.</p>'
			. '<p><b>주소</b><br><code class="ank-copy">' . esc_html( $url ) . '</code></p>'
			. '<p><b>비밀값</b> (머리말 <code>X-ANK-Token</code> 또는 <code>token</code> 값으로 함께 보냅니다)<br><code class="ank-copy">' . esc_html( ANK_Settings::webhook_token() ) . '</code></p>'
			. '<p><b>보낼 값</b>: <code>order_id</code>(주문 번호, 필수) · <code>email</code>(필수) · <code>name</code> · <code>product</code>(상품명) · <code>product_id</code></p>'
			. '<p class="description">비밀값은 키를 찍어 낼 수 있는 열쇠입니다. 다른 사람에게 보여 주지 마세요.</p></div>';

		echo '<div class="ank-card"><h2>최근 기록</h2>';
		$logs = ANK_Settings::logs();
		if ( ! $logs ) {
			echo '<p>아직 기록이 없습니다.</p>';
		} else {
			echo '<table class="widefat striped"><tbody>';
			foreach ( $logs as $l ) {
				echo '<tr><td style="width:150px;white-space:nowrap">' . esc_html( $l['at'] ) . '</td><td class="' . ( 'error' === $l['level'] ? 'ank-bad' : '' ) . '">' . esc_html( $l['msg'] ) . '</td></tr>';
			}
			echo '</tbody></table>';
		}
		echo '</div>';
	}

	// ── 처리 ──────────────────────────────────────────────────

	public static function save_settings() {
		self::guard( 'ank_save_settings' );
		$types = ANK_Keys::types();

		$products = array();
		$matches  = isset( $_POST['match'] ) ? (array) wp_unslash( $_POST['match'] ) : array();
		$tsel     = isset( $_POST['type'] ) ? (array) wp_unslash( $_POST['type'] ) : array();
		$urls     = isset( $_POST['row_url'] ) ? (array) wp_unslash( $_POST['row_url'] ) : array();
		foreach ( $matches as $i => $match ) {
			$match = sanitize_text_field( $match );
			if ( '' === $match ) {
				continue;
			}
			$type       = isset( $tsel[ $i ] ) && isset( $types[ $tsel[ $i ] ] ) ? $tsel[ $i ] : 'piano';
			$products[] = array( 'match' => $match, 'type' => $type, 'app_url' => isset( $urls[ $i ] ) ? esc_url_raw( trim( $urls[ $i ] ) ) : '' );
		}

		$default  = isset( $_POST['default_type'] ) ? sanitize_text_field( wp_unslash( $_POST['default_type'] ) ) : '';
		$statuses = isset( $_POST['wc_statuses'] ) ? array_values( array_intersect( array( 'completed', 'processing' ), array_map( 'sanitize_key', (array) wp_unslash( $_POST['wc_statuses'] ) ) ) ) : array();

		ANK_Settings::save(
			array(
				'products'     => $products,
				'app_url'      => isset( $_POST['app_url'] ) ? esc_url_raw( trim( wp_unslash( $_POST['app_url'] ) ) ) : '',
				'from_name'    => isset( $_POST['from_name'] ) ? sanitize_text_field( wp_unslash( $_POST['from_name'] ) ) : '',
				'from_email'   => isset( $_POST['from_email'] ) ? sanitize_email( wp_unslash( $_POST['from_email'] ) ) : '',
				'admin_email'  => isset( $_POST['admin_email'] ) ? sanitize_email( wp_unslash( $_POST['admin_email'] ) ) : '',
				'admin_copy'   => empty( $_POST['admin_copy'] ) ? 0 : 1,
				'subject'      => isset( $_POST['subject'] ) ? sanitize_text_field( wp_unslash( $_POST['subject'] ) ) : '',
				'intro'        => isset( $_POST['intro'] ) ? sanitize_textarea_field( wp_unslash( $_POST['intro'] ) ) : '',
				'outro'        => isset( $_POST['outro'] ) ? sanitize_textarea_field( wp_unslash( $_POST['outro'] ) ) : '',
				'default_type' => isset( $types[ $default ] ) ? $default : '',
				'wc_statuses'  => $statuses ? $statuses : array( 'completed' ),
			)
		);
		self::back( 'settings', '저장했습니다.' );
	}

	public static function manual_issue() {
		self::guard( 'ank_manual_issue' );
		$email = isset( $_POST['email'] ) ? sanitize_email( wp_unslash( $_POST['email'] ) ) : '';
		if ( ! is_email( $email ) ) {
			self::back( 'send', '메일 주소를 확인해 주세요.', 'error' );
		}
		$result = ANK_Issuer::issue(
			array(
				'order_ref'     => 'manual:' . gmdate( 'ymdHis' ) . '-' . wp_rand( 100, 999 ),
				'source'        => 'manual',
				'product_title' => isset( $_POST['product_title'] ) ? sanitize_text_field( wp_unslash( $_POST['product_title'] ) ) : '학원 관리노트',
				'email'         => $email,
				'name'          => isset( $_POST['name'] ) ? sanitize_text_field( wp_unslash( $_POST['name'] ) ) : '',
				'type'          => isset( $_POST['type'] ) ? sanitize_text_field( wp_unslash( $_POST['type'] ) ) : 'piano',
				'memo'          => isset( $_POST['memo'] ) ? sanitize_text_field( wp_unslash( $_POST['memo'] ) ) : '',
			)
		);
		if ( 'issued' !== $result['status'] ) {
			self::back( 'send', '발급하지 못했습니다: ' . ( isset( $result['reason'] ) ? $result['reason'] : $result['status'] ), 'error' );
		}
		if ( ! $result['sent'] ) {
			self::back( 'list', sprintf( '키 %s 는 만들었지만 메일을 보내지 못했습니다. 사이트의 메일 발송 설정을 확인해 주세요.', $result['row']['license_key'] ), 'error' );
		}
		self::back( 'list', sprintf( '%s 에게 인증키 %s 를 보냈습니다.', $email, $result['row']['license_key'] ) );
	}

	public static function resend() {
		self::guard( 'ank_resend' );
		$id    = isset( $_POST['id'] ) ? (int) $_POST['id'] : 0;
		$email = isset( $_POST['email'] ) ? sanitize_email( wp_unslash( $_POST['email'] ) ) : '';
		$row   = ANK_Store::find( $id );
		if ( ! $row ) {
			self::back( 'list', '내역을 찾지 못했습니다.', 'error' );
		}
		if ( is_email( $email ) && $email !== $row['email'] ) {
			ANK_Store::update_email( $id, $email ); // 고객이 메일 주소를 잘못 적은 경우
		}
		$sent = ANK_Issuer::resend( $id );
		self::back( 'list', $sent ? '다시 보냈습니다.' : '메일을 보내지 못했습니다. 메일 주소와 사이트의 메일 발송 설정을 확인해 주세요.', $sent ? 'ok' : 'error' );
	}

	public static function export() {
		self::guard( 'ank_export' );
		nocache_headers();
		header( 'Content-Type: text/csv; charset=UTF-8' );
		header( 'Content-Disposition: attachment; filename="academy-note-keys-' . gmdate( 'Ymd' ) . '.csv"' );
		$out = fopen( 'php://output', 'w' );
		fwrite( $out, "\xEF\xBB\xBF" ); // 엑셀이 한글을 깨뜨리지 않게
		fputcsv( $out, array( '발급일', '주문', '경로', '상품', '키 종류', '인증키', '이름', '메일', '발송 횟수', '마지막 발송', '메모' ) );
		$offset = 0;
		do {
			$rows = ANK_Store::recent( '', 500, $offset );
			foreach ( $rows as $r ) {
				fputcsv( $out, array( $r['created_at'], $r['order_ref'], $r['source'], $r['product_title'], $r['key_type'], $r['license_key'], $r['name'], $r['email'], $r['send_count'], $r['sent_at'], $r['memo'] ) );
			}
			$offset += 500;
		} while ( count( $rows ) === 500 );
		fclose( $out );
		exit;
	}
}
