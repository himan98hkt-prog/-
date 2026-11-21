/**
 * 명함스캔 → 구글 시트 연동 스크립트
 *
 * 1. 명함을 모을 구글 시트를 열고  확장 프로그램 > Apps Script  를 누릅니다.
 * 2. 이 파일 내용을 전부 붙여 넣고 아래 SECRET 을 아무도 모르는 문자열로 바꿉니다.
 * 3. 배포 > 새 배포 > 유형: 웹 앱
 *      - 실행 계정: 나
 *      - 액세스 권한이 있는 사용자: 모든 사용자
 *    배포 후 나오는 "웹 앱 URL"(…/exec)을 앱 설정 > 구글 시트 주소에 붙여 넣고,
 *    같은 SECRET 을 앱의 "공유 비밀키"에 넣습니다.
 *
 * 같은 명함(id)이 다시 오면 새 줄을 만들지 않고 그 줄을 고칩니다.
 * 고객/거래처를 다른 탭에 나누고 싶으면 SHEET_BY_KIND 를 바꾸세요.
 */
const SECRET = 'CHANGE-ME';

// 구분별 탭 이름. 같은 이름을 쓰면 한 탭에 모입니다.
const SHEET_BY_KIND = { '고객': '명함', '거래처': '명함', '기타': '명함' };

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    if (body.secret !== SECRET) return reply({ ok: false, error: 'bad secret' });

    const headers = body.headers;
    const row = body.row;
    const kindLabel = row[headers.indexOf('구분')];
    const sheet = getSheet(SHEET_BY_KIND[kindLabel] || '명함', headers);

    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      const ids = sheet.getLastRow() > 1 ? sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues().map(function (r) { return r[0]; }) : [];
      const found = ids.indexOf(body.id);
      // 전화번호 앞의 0 이 사라지지 않도록 문자열로 저장
      const values = [row.map(function (v) { return v === '' ? '' : String(v); })];
      const rowNumber = found >= 0 ? found + 2 : sheet.getLastRow() + 1;
      sheet.getRange(rowNumber, 1, 1, row.length).setNumberFormat('@').setValues(values);
      return reply({ ok: true, row: rowNumber });
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    return reply({ ok: false, error: String(err) });
  }
}

function getSheet(name, headers) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
  }
  return sheet;
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
