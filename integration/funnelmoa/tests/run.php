<?php
/**
 * 플러그인 동작 확인 — 워드프레스 없이 명령줄에서 돈다.
 *
 *   php integration/funnelmoa/tests/run.php            전체 실행 (실패하면 종료 코드 1)
 *   php integration/funnelmoa/tests/run.php --keys 5   공용키 5개만 뽑아 한 줄에 하나씩 출력 (앱 쪽 교차 검증용)
 *   php integration/funnelmoa/tests/run.php --mail out.html  발송되는 메일을 파일로 저장 (눈으로 확인)
 */

require __DIR__ . '/wp-stubs.php';
require __DIR__ . '/../academy-note-keys/academy-note-keys.php';

if ( in_array( '--keys', $argv, true ) ) {
	$n = (int) ( $argv[ array_search( '--keys', $argv, true ) + 1 ] ?? 5 );
	foreach ( array_keys( ANK_Keys::types() ) as $type ) {
		for ( $i = 0; $i < $n; $i++ ) {
			echo $type, ' ', ANK_Keys::generate( $type ), "\n";
		}
	}
	exit( 0 );
}

$passed = 0;
$failed = 0;
function check( $label, $cond, $detail = '' ) {
	global $passed, $failed;
	if ( $cond ) { $passed++; echo "  ✓ {$label}\n"; }
	else { $failed++; echo "  ✗ {$label}" . ( $detail ? " — {$detail}" : '' ) . "\n"; }
}
function mails() { return $GLOBALS['ank_test']['mails']; }
function last_mail() { $m = mails(); return end( $m ); }
function reset_mails() { $GLOBALS['ank_test']['mails'] = array(); }

// 워드프레스가 플러그인을 켜는 순서 그대로
ANK_Store::install();
ANK_Settings::save( array(
	'app_url'  => 'https://note.example.com/lite.html',
	'products' => array(
		array( 'match' => '관리노트', 'type' => 'piano', 'app_url' => '' ),
		array( 'match' => '777', 'type' => 'M-lite', 'app_url' => 'https://lite.example.com/lite.html' ),
	),
) );
do_action( 'plugins_loaded' );
do_action( 'rest_api_init' );

echo "\n[1] 키 규칙 — 앱과 같은 값이 나오는가\n";
$vectors = array( '아첼음악학원' => 'XVXA-FGGN-97KU', '가온피아노학원' => 'FQQH-9TRV-XTAV', '아라 잉글리시' => 'UTVE-JUVP-7WQ3', 'Test Academy' => 'EFLA-64YE-NKG6', '아첼 음악학원 (강남)' => 'RNUP-GUGG-NURQ' );
foreach ( $vectors as $name => $key ) {
	check( "학원명 방식: {$name} → {$key}", ANK_Keys::piano_key_for_name( $name ) === $key, ANK_Keys::piano_key_for_name( $name ) );
}
foreach ( array( 'ACDEFGHJ' => 'PYDG', '79AK3MCU' => 'ADYC', 'XXXXXXXX' => 'AUKD' ) as $head => $sum ) {
	check( "검증코드: {$head} → {$sum}", ANK_Keys::piano_check_digits( $head ) === $sum );
}
check( '앱 안내문에 적힌 확인용 키를 같은 뜻으로 읽는다',
	ANK_Keys::verify( 'AL2H-4K7P-KGMK' ) == array( 'ok' => true, 'scheme' => 'academy', 'product' => 'A', 'plan' => 'lite', 'key' => 'AL2H-4K7P-KGMK' )
	&& ANK_Keys::verify( 'AP9R-3TQX-71C3' )['plan'] === 'pro'
	&& ANK_Keys::verify( 'ML6Q-2WJD-7PG7' )['product'] === 'M'
	&& ANK_Keys::verify( '79AK-3MCU-ADYC' )['scheme'] === 'piano' );
$all_ok = true;
foreach ( array_keys( ANK_Keys::types() ) as $type ) {
	for ( $i = 0; $i < 200; $i++ ) {
		$k = ANK_Keys::generate( $type );
		$v = ANK_Keys::verify( $k );
		if ( ! $v['ok'] || ! preg_match( '/^[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}$/', $k ) ) { $all_ok = false; }
	}
}
check( '종류별로 200개씩 만든 키가 모두 검증을 통과한다', $all_ok );
check( '아무 문자열이나 통과시키지 않는다', ! ANK_Keys::verify( 'ABCD-EFGH-JKMN' )['ok'] && ! ANK_Keys::verify( '' )['ok'] );
$k = ANK_Keys::normalize( ANK_Keys::generate( 'piano' ) );
$broken = substr( $k, 0, 5 ) . ( 'A' === $k[5] ? 'C' : 'A' ) . substr( $k, 6 );
check( '한 글자만 바꿔도 거부한다', ! ANK_Keys::verify( $broken )['ok'] );

echo "\n[2] 우커머스 결제 → 메일\n";
$order = new Fake_WC_Order( array( 11 => new Fake_WC_Item( 501, '학원 관리노트 평생 이용권', 1 ), 12 => new Fake_WC_Item( 900, '피아노 교재 세트', 1 ) ), 'kim@example.com', '김', '원장' );
$GLOBALS['ank_test']['wc_orders'][1001] = $order;
do_action( 'woocommerce_order_status_completed', 1001 );
$row = ANK_Store::find_by_order( 'wc:1001:11:1' );
check( '주문이 완료되면 키가 발급된다', $row && ANK_Keys::verify( $row['license_key'] )['ok'] );
check( '상품명에 "관리노트"가 들어간 상품에만 발급한다 (교재 세트는 건너뜀)', ANK_Store::count() === 1 );
$mail = last_mail();
check( '구매자 메일로 보낸다', $mail && $mail['to'] === 'kim@example.com' );
check( '메일에 인증키가 들어 있다', $mail && false !== strpos( $mail['message'], $row['license_key'] ) );
check( '메일에 "눌러서 바로 시작하기" 주소가 들어 있다', $mail && false !== strpos( $mail['message'], 'https://note.example.com/lite.html#key=' . $row['license_key'] ) );
check( '메일 제목에 상품명이 들어간다', $mail && false !== strpos( $mail['subject'], '학원 관리노트 평생 이용권' ) );
check( '이름은 성+이름 순서로 부른다', $mail && false !== strpos( $mail['message'], '김원장님' ) );
check( '판매자에게도 사본이 간다 (숨은 참조)', $mail && in_array( 'Bcc: seller@example.com', $mail['headers'], true ) );
check( '주문 메모에 발급 사실을 남긴다', count( $order->notes ) === 1 && false !== strpos( $order->notes[0], $row['license_key'] ) );
check( '발송 횟수가 기록된다', (int) $row['send_count'] === 1 && '' !== (string) $row['sent_at'] );

echo "\n[3] 같은 주문 신호가 또 와도 키는 한 번만\n";
reset_mails();
do_action( 'woocommerce_order_status_completed', 1001 );
do_action( 'woocommerce_order_status_processing', 1001 );
check( '새 키를 만들지 않는다', ANK_Store::count() === 1 && ANK_Store::find_by_order( 'wc:1001:11:1' )['license_key'] === $row['license_key'] );
check( '메일도 다시 보내지 않는다', count( mails() ) === 0 );

echo "\n[4] 수량 3개 주문 → 키 3개\n";
reset_mails();
$GLOBALS['ank_test']['wc_orders'][1002] = new Fake_WC_Order( array( 21 => new Fake_WC_Item( 501, '학원 관리노트 평생 이용권', 3 ) ), 'lee@example.com', '이', '선생' );
do_action( 'woocommerce_order_status_processing', 1002 );
$three = array( ANK_Store::find_by_order( 'wc:1002:21:1' ), ANK_Store::find_by_order( 'wc:1002:21:2' ), ANK_Store::find_by_order( 'wc:1002:21:3' ) );
check( '키 3개가 서로 다르게 발급된다', $three[0] && $three[1] && $three[2] && count( array_unique( array_column( $three, 'license_key' ) ) ) === 3 );
check( '메일 3통이 나간다', count( mails() ) === 3 );

echo "\n[5] 상품 번호로 연결 · 줄마다 다른 키 종류와 앱 주소\n";
reset_mails();
$GLOBALS['ank_test']['wc_orders'][1003] = new Fake_WC_Order( array( 31 => new Fake_WC_Item( 777, '기본형 이용권', 1 ) ), 'park@example.com', '박', '쌤' );
do_action( 'woocommerce_order_status_completed', 1003 );
$r5 = ANK_Store::find_by_order( 'wc:1003:31:1' );
check( '번호 777 상품에는 학원 전용 Lite 키가 나간다', $r5 && ANK_Keys::verify( $r5['license_key'] ) == array( 'ok' => true, 'scheme' => 'academy', 'product' => 'M', 'plan' => 'lite', 'key' => $r5['license_key'] ) );
check( '그 줄에 적은 앱 주소로 시작 링크를 만든다', false !== strpos( last_mail()['message'], 'https://lite.example.com/lite.html#key=' ) );

echo "\n[6] 코스모스팜 회원관리(퍼널모아) 결제\n";
reset_mails();
class Fake_CF_Order { function ID() { return 3301; } function user() { return (object) array( 'ID' => 7, 'user_email' => 'choi@example.com', 'display_name' => '최원장' ); } }
class Fake_CF_Product { function ID() { return 88; } function title() { return '피아노학원 관리노트'; } }
do_action( 'cosmosfarm_members_subscription_request_pay', new Fake_CF_Order(), new Fake_CF_Product() );
$r6 = ANK_Store::find_by_order( 'cf:3301' );
check( '결제 성공 신호에 키가 발급된다', $r6 && $r6['source'] === 'cosmosfarm' && ANK_Keys::verify( $r6['license_key'] )['scheme'] === 'piano' );
check( '회원 메일로 보낸다', last_mail()['to'] === 'choi@example.com' );
check( '무엇을 읽었는지 진단 기록에 남는다', false !== strpos( json_encode( ANK_Settings::logs(), JSON_UNESCAPED_UNICODE ), '코스모스팜 결제 신호를 받았습니다 — 주문 3301' ) );
reset_mails();
do_action( 'cosmosfarm_members_subscription_request_pay', new Fake_CF_Order(), new Fake_CF_Product(), array( 'x' => 1 ) );
check( '같은 주문이 다시 와도 한 번만 (인자가 3개로 와도 동작)', count( mails() ) === 0 && ANK_Store::find_by_order( 'cf:3301' )['license_key'] === $r6['license_key'] );

// 메서드 이름이 다른 버전 — 속성만 있고, 메일은 주문 글의 메타에 있는 경우
reset_mails();
$GLOBALS['ank_test']['postmeta'][3302] = array( 'buyer_email' => 'meta@example.com', 'buyer_name' => '메타원장' );
$GLOBALS['ank_test']['postmeta'][89]   = array( '_title' => '학원 관리노트 Pro' );
do_action( 'cosmosfarm_members_subscription_request_pay', (object) array( 'ID' => 3302 ), (object) array( 'ID' => 89 ) );
$r6b = ANK_Store::find_by_order( 'cf:3302' );
check( '객체 모양이 달라도(속성·글 메타) 메일과 상품명을 찾아낸다', $r6b && $r6b['email'] === 'meta@example.com' && $r6b['name'] === '메타원장' && $r6b['product_title'] === '학원 관리노트 Pro' );

echo "\n[7] 메일이 못 나갔을 때\n";
reset_mails();
$GLOBALS['ank_test']['mail_ok'] = false;
$GLOBALS['ank_test']['wc_orders'][1004] = new Fake_WC_Order( array( 41 => new Fake_WC_Item( 501, '학원 관리노트 평생 이용권', 1 ) ), 'fail@example.com', '정', '원장' );
do_action( 'woocommerce_order_status_completed', 1004 );
$r7 = ANK_Store::find_by_order( 'wc:1004:41:1' );
check( '키는 발급되어 대장에 남는다 (결제하고 키가 사라지는 일은 없다)', $r7 && (int) $r7['send_count'] === 0 );
$warn = last_mail();
check( '판매자에게 "보내지 못했다"고 알린다 (키 포함)', $warn && $warn['to'] === 'seller@example.com' && false !== strpos( $warn['message'], $r7['license_key'] ) );
check( '못 보낸 건수가 관리 화면 숫자에 잡힌다', ANK_Store::count_unsent() === 1 );
$GLOBALS['ank_test']['mail_ok'] = true;
reset_mails();
do_action( 'woocommerce_order_status_completed', 1004 );
check( '다음 신호 때 같은 키로 다시 보낸다', count( mails() ) === 1 && false !== strpos( last_mail()['message'], $r7['license_key'] ) && ANK_Store::count_unsent() === 0 );

echo "\n[8] 관리자가 직접 다시 보내기 (메일 주소 정정)\n";
reset_mails();
ANK_Store::update_email( $r7['id'], 'fixed@example.com' );
check( '고친 주소로 같은 키가 나간다', ANK_Issuer::resend( $r7['id'] ) && last_mail()['to'] === 'fixed@example.com' && false !== strpos( last_mail()['message'], $r7['license_key'] ) );
check( '발송 횟수가 올라간다', (int) ANK_Store::find( $r7['id'] )['send_count'] === 2 );

echo "\n[9] 웹훅 주소\n";
$route = $GLOBALS['ank_test']['routes']['academy-note/v1/issue'];
$token = ANK_Settings::webhook_token();
check( '비밀값 없이는 거절한다', ! call_user_func( $route['permission_callback'], new Fake_Request( array( 'order_id' => 'X1', 'email' => 'a@b.co' ) ) ) );
check( '틀린 비밀값도 거절한다', ! call_user_func( $route['permission_callback'], new Fake_Request( array(), array( 'x-ank-token' => 'nope' ) ) ) );
check( '맞는 비밀값이면 통과한다', call_user_func( $route['permission_callback'], new Fake_Request( array(), array( 'x-ank-token' => $token ) ) ) );
reset_mails();
$res = call_user_func( $route['callback'], new Fake_Request( array( 'order_id' => 'PAY-55', 'email' => 'hook@example.com', 'name' => '훅원장', 'product' => '학원 관리노트' ) ) );
check( '키를 발급하고 응답에 담아 준다', $res->status === 200 && $res->data['ok'] && ANK_Keys::verify( $res->data['key'] )['ok'] && $res->data['sent'] );
$res2 = call_user_func( $route['callback'], new Fake_Request( array( 'order_id' => 'PAY-55', 'email' => 'hook@example.com', 'product' => '학원 관리노트' ) ) );
check( '같은 주문 번호로 다시 부르면 같은 키를 돌려준다', $res2->data['status'] === 'duplicate' && $res2->data['key'] === $res->data['key'] && count( mails() ) === 1 );
$res3 = call_user_func( $route['callback'], new Fake_Request( array( 'order_id' => 'PAY-56', 'email' => 'not-an-email' ) ) );
check( '메일 주소가 이상하면 발급하지 않는다', $res3->status === 400 );
$res4 = call_user_func( $route['callback'], new Fake_Request( array( 'order_id' => 'PAY-57', 'email' => 'x@example.com', 'product' => '전혀 다른 상품' ) ) );
check( '연결되지 않은 상품은 발급하지 않는다', $res4->status === 422 && $res4->data['status'] === 'skipped' );

echo "\n[10] 마이페이지 — 내 인증키\n";
$sc = $GLOBALS['ank_test']['shortcodes']['academy_note_keys'];
check( '로그인 전에는 키를 보여 주지 않는다', false === strpos( call_user_func( $sc ), $row['license_key'] ) );
$GLOBALS['ank_test']['current'] = (object) array( 'ID' => 3, 'user_email' => 'kim@example.com', 'display_name' => '김원장' );
$html = call_user_func( $sc );
check( '로그인한 회원에게 자기 키만 보여 준다', false !== strpos( $html, $row['license_key'] ) && false === strpos( $html, $r6['license_key'] ) );

echo "\n[11] 메일 내용이 깨지지 않는가\n";
reset_mails();
ANK_Issuer::issue( array( 'order_ref' => 'manual:xss', 'source' => 'manual', 'product_title' => '<b>관리노트</b>', 'email' => 'safe@example.com', 'name' => '<script>alert(1)</script>', 'type' => 'piano' ) );
check( '이름·상품명에 섞인 태그는 메일에 그대로 실리지 않는다', false === strpos( last_mail()['message'], '<script>' ) );
check( '앱 주소가 비어 있으면 버튼 없이 입력 방법만 안내한다', ( function () {
	ANK_Settings::save( array( 'app_url' => '', 'products' => array( array( 'match' => '관리노트', 'type' => 'piano', 'app_url' => '' ) ) ) );
	ANK_Issuer::issue( array( 'order_ref' => 'manual:nourl', 'source' => 'manual', 'product_title' => '학원 관리노트', 'email' => 'nourl@example.com', 'name' => '', 'type' => 'piano' ) );
	$m = last_mail()['message'];
	return false === strpos( $m, '눌러서 바로 시작하기' ) && false !== strpos( $m, '인증하고 시작하기' ) && false !== strpos( $m, '원장님' );
} )() );

echo "\n[12] 관리 화면\n";
ANK_Settings::save( array( 'app_url' => '', 'products' => array() ) );
$_GET = array();
foreach ( array( 'list', 'send', 'settings', 'status' ) as $tab ) {
	$_GET['tab'] = $tab;
	ob_start();
	$err = '';
	try { ANK_Admin::page(); } catch ( Throwable $e ) { $err = $e->getMessage(); }
	$html = ob_get_clean();
	check( "'{$tab}' 탭이 오류 없이 그려진다", '' === $err && strlen( $html ) > 400, $err );
	if ( 'list' === $tab ) {
		check( '할 일이 남았으면 맨 위에서 알려 준다 (상품 연결 · 앱 주소)', false !== strpos( $html, '마무리할 설정이 있습니다' ) );
		check( '발급 내역에 인증키와 다시 보내기 버튼이 보인다', false !== strpos( $html, $row['license_key'] ) && false !== strpos( $html, '다시 보내기' ) );
	}
	if ( 'status' === $tab ) {
		check( '웹훅 주소와 최근 기록을 보여 준다', false !== strpos( $html, 'wp-json/academy-note/v1/issue' ) && false !== strpos( $html, '인증키를 보냈습니다' ) );
	}
}
$_POST = array(
	'match' => array( '관리노트', '', '42' ), 'type' => array( 'piano', 'piano', 'A-lite' ), 'row_url' => array( '', '', 'https://b.example.com/lite.html' ),
	'app_url' => ' https://a.example.com/lite.html ', 'from_name' => '아첼쌤', 'from_email' => 'help@example.com', 'admin_email' => 'seller@example.com',
	'admin_copy' => '1', 'subject' => '[{사이트명}] {상품명}', 'intro' => "첫 줄\n둘째 줄", 'outro' => '끝', 'default_type' => 'nope', 'wc_statuses' => array( 'completed', 'weird' ),
);
$redirect = '';
try { ANK_Admin::save_settings(); } catch ( Ank_Redirect $e ) { $redirect = $e->getMessage(); }
$saved = ANK_Settings::all();
check( '설정을 저장하면 빈 줄은 버리고 채운 줄만 남는다', count( $saved['products'] ) === 2 && $saved['products'][1] === array( 'match' => '42', 'type' => 'A-lite', 'app_url' => 'https://b.example.com/lite.html' ) );
check( '모르는 값은 안전한 기본값으로 바꾼다', '' === $saved['default_type'] && array( 'completed' ) === $saved['wc_statuses'] && 'https://a.example.com/lite.html' === $saved['app_url'] );
check( '저장 뒤 설정 탭으로 돌아간다', false !== strpos( $redirect, 'tab=settings' ) );
reset_mails();
$_POST = array( 'email' => 'direct@example.com', 'name' => '직접', 'type' => 'A-pro', 'product_title' => '학원 관리노트', 'memo' => '계좌이체' );
try { ANK_Admin::manual_issue(); } catch ( Ank_Redirect $e ) { $redirect = $e->getMessage(); }
$direct = ANK_Store::by_email( 'direct@example.com' );
check( '직접 보내기 — 고른 종류의 키를 만들어 보낸다', count( $direct ) === 1 && ANK_Keys::verify( $direct[0]['license_key'] )['plan'] === 'pro' && last_mail()['to'] === 'direct@example.com' && $direct[0]['memo'] === '계좌이체' );
$_POST = array();

if ( in_array( '--mail', $argv, true ) ) {
	$out = $argv[ array_search( '--mail', $argv, true ) + 1 ] ?? 'mail.html';
	ANK_Settings::save( array( 'app_url' => 'https://note.example.com/lite.html' ) );
	reset_mails();
	ANK_Issuer::issue( array( 'order_ref' => 'manual:preview', 'source' => 'manual', 'product_title' => '학원 관리노트', 'email' => 'preview@example.com', 'name' => '김원장', 'type' => 'piano' ) );
	file_put_contents( $out, last_mail()['message'] );
	echo "\n메일 미리보기 저장: {$out}\n";
}

echo "\n통과 {$passed} · 실패 {$failed}\n";
exit( $failed ? 1 : 0 );
