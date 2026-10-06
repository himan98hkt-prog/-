// 온디바이스 OCR(ML Kit)이 읽은 줄들을 명함 필드로 나눈다 — 규칙 기반, 무료·오프라인.
// 한국 명함의 관례(M/T/F 표기, (주)·주식회사, 팀·본부, 직급, 시·구·로 주소)를 기준으로 한다.
import { formatKoreanPhone, normalizeEmail, normalizeWebsite, phoneDigits } from './normalize';
import { CardFields, EMPTY_FIELDS } from './types';

export interface OcrLineInput {
  text: string;
  block?: number;
  left?: number;
  top?: number;
  width?: number;
  height?: number;
}

export interface ParsedCard {
  fields: CardFields;
  extra: string[];
}

// ── 사전 ────────────────────────────────────────────────────────────────────

const TITLES_KO = [
  '대표이사', '대표', '회장', '부회장', '사장', '부사장', '전무이사', '전무', '상무이사', '상무', '이사', '감사', '고문',
  '본부장', '부문장', '사업부장', '센터장', '연구소장', '소장', '실장', '원장', '부원장', '국장', '지점장', '점장', '공장장',
  '부장', '차장', '과장', '대리', '주임', '사원', '계장', '팀장', '파트장', '그룹장', '셀장', '조장',
  '수석연구원', '책임연구원', '선임연구원', '전임연구원', '연구원', '수석', '책임', '선임', '전임', '프로', '매니저', '디렉터',
  '컨설턴트', '변호사', '변리사', '세무사', '회계사', '노무사', '법무사', '감정평가사', '건축사', '기술사', '약사', '의사', '원장님',
  '교수', '부교수', '조교수', '강사', '연구교수', '선생님', '코치', '디자이너', '엔지니어', '개발자', '기자', '편집장', 'PD', '작가',
  '대표원장', '대표변호사', '파트너', '공동대표', '창업자', '설계사', '팀원', '위원', '위원장', '사무국장', '총장', '학장',
];
const TITLES_EN = [
  'CEO', 'CTO', 'CFO', 'COO', 'CMO', 'CIO', 'CSO', 'VP', 'SVP', 'EVP', 'President', 'Vice President', 'Director', 'Manager',
  'Senior Manager', 'General Manager', 'Team Leader', 'Team Lead', 'Lead', 'Head', 'Engineer', 'Senior Engineer', 'Developer',
  'Designer', 'Consultant', 'Researcher', 'Partner', 'Founder', 'Co-Founder', 'Owner', 'Representative', 'Professor', 'Attorney',
  'Specialist', 'Associate', 'Analyst', 'Officer', 'Executive', 'Chairman', 'Principal', 'Architect', 'Coordinator', 'Assistant',
];

const COMPANY_MARK = /(\(주\)|㈜|\(유\)|\(사\)|\(재\)|주식회사|유한회사|유한책임회사|합자회사|사단법인|재단법인|학교법인|의료법인|협동조합|\bInc\.?|\bCorp\.?|\bCo\.,?\s*Ltd\.?|\bCo\.|\bLtd\.?|\bLLC\b|\bGmbH\b|\bCompany\b|\bCorporation\b|\bGroup\b)/i;
const COMPANY_WORD = /(그룹|은행|증권|보험|캐피탈|카드|병원|의원|치과|한의원|약국|법률사무소|법무법인|특허법인|회계법인|세무법인|노무법인|협회|재단|공사|공단|학교|대학교|대학원|연구원|연구소|컴퍼니|코리아|테크|솔루션즈?|산업|건설|전자|전기|상사|물산|무역|컨설팅|엔지니어링|디자인|미디어|엔터테인먼트|푸드|제약|바이오|화학|물류|통운|에너지|모터스|시스템즈?|네트웍스|소프트|랩스?|스튜디오|파트너스|인베스트먼트|자산운용|홀딩스|아카데미|학원|센터)$/;
const DEPT = /(본부|사업부|사업본부|부문|실|팀|부|센터|연구소|연구실|그룹|파트|셀|과|국|처|담당|지점|지사|영업소|사무소|Division|Dept\.?|Department|Team|Office|Lab|Center|Group)$/i;

// 번호 앞 표기. 전화 아이콘(☎📱📠)이 OCR 에서 C·O·D·P·H 같은 한 글자로 읽히는 일이 많아
// 한 글자 표기는 M/T/F 만 인정하고, 나머지는 단어(Tel, 휴대폰 …)일 때만 인정한다.
const LABEL_WORDS = {
  mobile: 'M|Mobile|Mob|H\\.?P|C\\.?P|Cell|Cellular|Cellphone|휴대폰|휴대전화|핸드폰|모바일|手机',
  phone: 'T|Tel|Telephone|Phone|Ph|Office|Direct|DID|전화|전화번호|대표|대표전화|대표번호|직통|직통전화|사무실',
  fax: 'F|Fax|Facsimile|팩스|전송',
};
const labelAtEnd = (w: string) => new RegExp(`(?:^|[\\s/·,:])(?:${w})\\s*[.:)]?\\s*$`, 'i');
const labelOnly = (w: string) => new RegExp(`^\\(?\\s*(?:${w})\\s*[.:)]?\\s*$`, 'i');
const LABEL = { mobile: labelAtEnd(LABEL_WORDS.mobile), phone: labelAtEnd(LABEL_WORDS.phone), fax: labelAtEnd(LABEL_WORDS.fax) };
const LABEL_ONLY = { mobile: labelOnly(LABEL_WORDS.mobile), phone: labelOnly(LABEL_WORDS.phone), fax: labelOnly(LABEL_WORDS.fax) };
// 번호 뒤에 붙는 표기 — "02-123-4567 (팩스)", "1588-1234 대표"
const LABEL_AFTER = { fax: /^\s*\(?\s*(?:팩스|fax)\s*\)?/i, phone: /^\s*\(?\s*(?:대표|직통|전화|tel)\s*\)?/i };
type PhoneKind = 'mobile' | 'phone' | 'fax';

function labelOf(text: string, set: Record<PhoneKind, RegExp>): PhoneKind | '' {
  return set.mobile.test(text) ? 'mobile' : set.fax.test(text) ? 'fax' : set.phone.test(text) ? 'phone' : '';
}

/** 아이콘이 남긴 기호·잡문자를 지운다 (글자·숫자·공백·구두점만 남김) */
const stripIcons = (s: string) => s.replace(/[^0-9A-Za-z가-힣\s.:()/,+-]/g, ' ');

// 흔한 한국 성씨 (두 글자 성 포함)
const SURNAMES_2 = ['남궁', '선우', '제갈', '황보', '독고', '사공', '서문', '동방'];
const SURNAMES_1 = new Set(
  '김이박최정강조윤장임한오서신권황안송류유전홍고문양손배백허남심노하곽성차주우구민진나지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예경봉사부'.split(''),
);

const NOT_NAME = new Set([
  '주소', '전화', '팩스', '휴대폰', '핸드폰', '이메일', '메일', '홈페이지', '사이트', '대표', '본사', '지사', '공장', '연구소', '센터',
  '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종', '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
  '주식회사', '유한회사', '사무소', '고객', '거래처', '명함', '대한민국', '한국', '영업', '마케팅', '기획', '인사', '총무', '재무', '회계',
]);

const ADDRESS_REGION = /(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충청|충북|충남|전라|전북|전남|경상|경북|경남|제주)/;
const ADDRESS_UNIT = /([가-힣\d]+(시|도|군|구|읍|면|동|리|로|길|가)(?=[\s,\d]|$)|[가-힣]+(로|길)\s*\d)/;
const ADDRESS_CONT = /(\d+\s*(층|호|F\b)|빌딩|타워|센터|오피스텔|아파트|플라자|프라자|Bldg|Building|Tower|Floor|Suite|#\d)/i;
const ADDRESS_EN = /\b(Seoul|Busan|Incheon|Daegu|Daejeon|Gwangju|Ulsan|Sejong|Gyeonggi|Korea|[A-Za-z]+-(ro|gil|daero|dong|gu|si))\b/i;
const ADDRESS_LABEL = /^(주소|본사|지사|공장|연구소|Add(ress)?|A)\s*[.:)]?\s*/i;

const EMAIL = /[A-Za-z0-9._%+-]+\s?@\s?[A-Za-z0-9.-]+\s?\.\s?[A-Za-z]{2,}(?:\.[A-Za-z]{2,})?/;
const WEB = /\b(?:https?:\/\/)?(?:www\.)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?:\/[^\s]*)?|\bhttps?:\/\/[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?:\/[^\s]*)?|\b[A-Za-z0-9-]{2,}\.(?:co\.kr|or\.kr|go\.kr|ac\.kr|re\.kr|ne\.kr|kr|com|net|org|io|co|biz|info|ai)\b(?:\/[^\s]*)?/i;
// 국내 전화번호 (+82, 괄호 지역번호, 점/공백/하이픈 구분, 15xx 대표번호)
// 국내 전화번호. 지역번호를 실제 체계(02, 031~064, 010~019, 070, 080, 050x)로 제한해
// 아이콘이 '0' 으로 읽혀 앞에 붙은 경우("002-…")에도 올바른 번호만 잡는다.
const AREA = '(?:02|0[3-6][1-5]|01[016789]|070|080|050[2-8])';
const PHONE = new RegExp(
  `(?:\\+\\s?82[\\s.-]*(?:\\(0\\)|0)?[\\s.-]*(?:2|[3-6][1-5]|1[016789]|70|80)[\\s.)-]*\\d{3,4}[\\s.-]*\\d{4}` +
    `|\\(?${AREA}\\)?[\\s.)-]*\\d{3,4}[\\s.-]*\\d{4}` +
    `|1[5-9]\\d{2}[\\s.-]*\\d{4})`,
  'g',
);

// ── 유틸 ────────────────────────────────────────────────────────────────────

const clean = (s: string) => s.replace(/[|｜]/g, ' ').replace(/\s+/g, ' ').trim();
const isHangul = (s: string) => /^[가-힣]+$/.test(s);

/** 숫자 자리에 섞인 OCR 오인식(O→0, l/I→1) 바로잡기 — 전화번호 후보에만 적용 */
function fixDigits(s: string): string {
  // 숫자·구분자 사이에 낀 글자만 바꾼다 (lookbehind 없이 — 구형 JS 엔진 호환)
  return s.replace(/([\d][\s.-]?)([OoIl])(?=[\s.-]?\d)/g, (_m, pre: string, c: string) => pre + (/[Oo]/.test(c) ? '0' : '1'));
}

function titleIn(text: string): string {
  const tokens = text.split(/[\s/·,]+/).filter(Boolean);
  // 긴 직함 먼저 (대표이사 > 대표)
  for (const t of tokens) {
    const hit = [...TITLES_KO].sort((a, b) => b.length - a.length).find((w) => t === w || (t.endsWith(w) && t.length <= w.length + 3 && !DEPT.test(t)));
    if (hit) return t === hit ? hit : t;
  }
  const lower = ` ${text.toLowerCase()} `;
  const en = [...TITLES_EN].sort((a, b) => b.length - a.length).find((w) => new RegExp(`[\\s,/]${w.toLowerCase().replace(/[-]/g, '\\-')}[\\s,/]`).test(lower));
  return en ?? '';
}

function looksLikeName(token: string): boolean {
  if (!isHangul(token) || token.length < 2 || token.length > 4) return false;
  if (NOT_NAME.has(token)) return false;
  if (TITLES_KO.includes(token)) return false;
  if (DEPT.test(token) && token.length >= 3) return false;
  if (COMPANY_WORD.test(token)) return false;
  if (token.length === 4) return SURNAMES_2.some((s) => token.startsWith(s));
  return SURNAMES_1.has(token[0]) || SURNAMES_2.some((s) => token.startsWith(s));
}

// ── 본체 ────────────────────────────────────────────────────────────────────

export function parseCardText(input: OcrLineInput[] | string): ParsedCard {
  const rawLines: OcrLineInput[] = typeof input === 'string' ? input.split(/\r?\n/).map((text) => ({ text })) : input;
  const lines = rawLines
    .map((l, i) => ({ ...l, text: clean(l.text), idx: i, used: false }))
    .filter((l) => l.text.length > 0);
  const f: CardFields = { ...EMPTY_FIELDS };
  const maxH = Math.max(1, ...lines.map((l) => l.height ?? 0));

  // 1) 이메일
  for (const l of lines) {
    const m = l.text.match(EMAIL);
    if (m) {
      if (!f.email) f.email = normalizeEmail(m[0].replace(/\s/g, ''));
      l.text = clean(l.text.replace(m[0], '').replace(/(E-?mail|이메일|메일|E)\s*[.:)]?\s*$/i, ''));
    }
  }

  // 2) 웹사이트 (이메일을 지운 뒤라 도메인이 겹치지 않는다)
  for (const l of lines) {
    const m = l.text.match(WEB);
    if (m && !/@/.test(m[0])) {
      if (!f.website) f.website = normalizeWebsite(m[0]);
      l.text = clean(l.text.replace(m[0], '').replace(/(Web|Homepage|Home|홈페이지|W)\s*[.:)]?\s*$/i, ''));
    }
  }

  // 3) 전화·휴대폰·팩스
  //  - 010·011… 은 표기와 상관없이 휴대폰 (아이콘 오인식 표기보다 번호 자체가 확실하다)
  //  - 일반 전화는 번호 앞(또는 윗줄·뒤)의 표기로 전화/팩스를 가르고,
  //    표기가 없으면 첫 번호=전화, 다음 번호는 팩스처럼 보일 때(같은 국번·050x)만 팩스
  type Found = { value: string; digits: string; label: PhoneKind | ''; order: number };
  const found: Found[] = [];
  lines.forEach((l, li) => {
    const text = fixDigits(stripIcons(l.text));
    const matches = [...text.matchAll(PHONE)];
    if (!matches.length) return;
    let cursor = 0;
    let rest = '';
    matches.forEach((m, mi) => {
      const num = m[0].trim();
      const digits = phoneDigits(num);
      if (digits.length < 8) return;
      const before = text.slice(cursor, m.index);
      const after = text.slice((m.index ?? 0) + m[0].length);
      let label = labelOf(before, LABEL);
      if (!label) label = LABEL_AFTER.fax.test(after) ? 'fax' : LABEL_AFTER.phone.test(after) ? 'phone' : '';
      // 표기가 윗줄에 따로 있는 배치 ("Fax" / "02-123-4568")
      if (!label && mi === 0 && !before.trim() && li > 0 && !lines[li - 1].used) {
        const prevLabel = labelOf(clean(stripIcons(lines[li - 1].text)), LABEL_ONLY);
        if (prevLabel) {
          label = prevLabel;
          lines[li - 1].used = true;
        }
      }
      // 내선 번호가 바로 뒤에 붙어 있으면 함께 가져간다
      const ext = after.match(/^\s*(?:\(?\s*(?:내선|ext\.?|#)\s*(\d{1,5})\s*\)?)/i);
      const value = formatKoreanPhone(ext ? `${num} ext ${ext[1]}` : num);
      found.push({ value, digits, label, order: found.length });
      rest += before.replace(LABEL.mobile, '').replace(LABEL.fax, '').replace(LABEL.phone, '') + ' ';
      cursor = (m.index ?? 0) + m[0].length + (ext ? ext[0].length : 0);
    });
    rest += text.slice(cursor).replace(LABEL_AFTER.fax, '').replace(LABEL_AFTER.phone, '');
    l.text = clean(rest.replace(/^[\s:./,()+-]+|[\s:./,()+-]+$/g, ''));
    // 번호를 빼고 남은 것이 아이콘 찌꺼기(한두 글자)뿐이면 버린다
    if (!/[가-힣]{2,}|[A-Za-z]{3,}/.test(l.text)) l.used = true;
  });

  const isMobileNo = (d: string) => /^01[016789]/.test(d);
  const looksLikeFaxOf = (phone: string, cand: string) => {
    const p = phoneDigits(phone);
    if (/^050[2-8]/.test(cand)) return true; // 050 평생번호는 팩스로 많이 쓴다
    // 같은 지역번호·국번이면 팩스 (02-123-4567 / 02-123-4568)
    return p.length === cand.length && p.slice(0, p.length - 4) === cand.slice(0, cand.length - 4);
  };
  const others: string[] = [];
  for (const n of found) {
    if (isMobileNo(n.digits)) {
      if (!f.mobile) f.mobile = n.value;
      else if (phoneDigits(f.mobile) !== n.digits) others.push(`휴대폰 ${n.value}`);
    } else if (n.label === 'fax') {
      if (!f.fax) f.fax = n.value;
      else others.push(`팩스 ${n.value}`);
    } else if (n.label === 'phone' || n.label === 'mobile') {
      if (!f.phone) f.phone = n.value;
      else others.push(`전화 ${n.value}`);
    }
  }
  // 표기 없는 일반 전화: 050x 는 팩스 쪽으로 미루고, 첫 번호=전화, 다음 번호는
  // 같은 국번이거나 번호가 두 개뿐일 때(명함은 대개 전화→팩스 순) 팩스, 그 밖은 기타로 보존
  const unlabeledLand = found.filter((n) => !isMobileNo(n.digits) && !n.label);
  const fax050 = unlabeledLand.find((n) => /^050[2-8]/.test(n.digits));
  const ordered = fax050 && unlabeledLand.length > 1 ? [...unlabeledLand.filter((n) => n !== fax050), fax050] : unlabeledLand;
  for (const n of ordered) {
    if (!f.phone) f.phone = n.value;
    else if (!f.fax && (looksLikeFaxOf(f.phone, n.digits) || unlabeledLand.length <= 2)) f.fax = n.value;
    else others.push(`전화 ${n.value}`);
  }

  // 4) 주소 — 지역명+행정단위 또는 영문 주소, 다음 줄이 층/호/빌딩이면 이어 붙인다
  for (let i = 0; i < lines.length && !f.address; i++) {
    const l = lines[i];
    const t = l.text;
    const labeled = /^(주소|Add(ress)?)\s*[.:)]/i.test(t);
    const ko = ADDRESS_REGION.test(t) && ADDRESS_UNIT.test(t);
    const en = ADDRESS_EN.test(t) && /\d/.test(t) && !/^[A-Za-z]+\s[A-Za-z]+$/.test(t);
    if (!(labeled || ko || en)) continue;
    let addr = t.replace(ADDRESS_LABEL, '');
    l.used = true;
    const next = lines[i + 1];
    if (next && !next.used && ADDRESS_CONT.test(next.text) && !EMAIL.test(next.text) && next.text.length <= 40 && !COMPANY_MARK.test(next.text)) {
      addr += ' ' + next.text;
      next.used = true;
    }
    f.address = clean(addr);
  }

  // 5) 회사 — (주)/주식회사/Inc 등 표기, 없으면 업종 단어로 끝나는 줄
  const companyLine =
    lines.find((l) => !l.used && COMPANY_MARK.test(l.text) && /[가-힣]/.test(l.text)) ??
    lines.find((l) => !l.used && COMPANY_MARK.test(l.text)) ??
    lines.find((l) => !l.used && l.text.split(' ').some((w) => COMPANY_WORD.test(w) && w.length >= 3 && !looksLikeName(w)) && l.text.length <= 25);
  if (companyLine) {
    f.company = companyLine.text;
    companyLine.used = true;
  }

  // 6) 이름 — 한글 2~4자 + 성씨, 글자가 클수록·직함과 같은 줄일수록 가산점
  type Cand = { line: (typeof lines)[number]; token: string; score: number };
  const cands: Cand[] = [];
  for (const l of lines) {
    if (l.used) continue;
    const t = l.text;
    // "홍 길 동" 처럼 한 글자씩 띄어 쓴 이름
    const spaced = /^([가-힣]\s){1,3}[가-힣]$/.test(t) ? t.replace(/\s/g, '') : null;
    const tokens = spaced ? [spaced] : t.split(/[\s/·,()]+/).filter(Boolean);
    const hasTitle = !!titleIn(t);
    tokens.forEach((tok) => {
      if (!looksLikeName(tok)) return;
      let score = 1;
      if (l.height) score += (l.height / maxH) * 3;
      if (hasTitle) score += 1.5;
      if (tokens.length <= 3) score += 0.5;
      if (tok.length === 3) score += 0.7;
      if (tokens.length === 1) score += 0.5;
      cands.push({ line: l, token: tok, score });
    });
  }
  cands.sort((a, b) => b.score - a.score);
  const best = cands[0];
  if (best) {
    f.name = best.token;
    const remainder = clean(best.line.text.replace(/\s/g, '') === best.token ? '' : best.line.text.replace(best.token, ''));
    best.line.used = true;
    if (remainder) {
      const title = titleIn(remainder);
      if (title) f.title = title;
      const deptTok = remainder.split(' ').find((w) => DEPT.test(w) && !TITLES_KO.includes(w) && w !== title);
      if (deptTok) f.department = deptTok;
      if (!title && !deptTok) best.line.text = remainder, (best.line.used = false);
    }
  }

  // 7) 영문 이름 — 한글 이름 줄 근처의 2~3 단어 영문 줄
  const enName = lines.find(
    (l) => !l.used && /^[A-Za-z]+(?:[\s-][A-Za-z]+){1,2}$/.test(l.text) && !COMPANY_MARK.test(l.text) && !titleIn(` ${l.text} `) && !ADDRESS_EN.test(l.text),
  );
  if (enName) {
    f.nameEn = enName.text.replace(/\b([A-Z])([A-Z]+)\b/g, (_m, a: string, b: string) => a + b.toLowerCase());
    enName.used = true;
    if (!f.name) f.name = f.nameEn;
  }

  // 8) 직책·부서 — 남은 줄에서
  for (const l of lines) {
    if (l.used) continue;
    let title = f.title ? '' : titleIn(l.text);
    // "Marketing Manager" 처럼 영문 직함 줄은 줄 전체를 직함으로
    if (title && /^[A-Za-z][A-Za-z &/-]+$/.test(l.text) && l.text.split(' ').length <= 4) title = l.text;
    const words = l.text.split(' ');
    let dept = '';
    if (!f.department) {
      // "경영지원본부 인사팀" 처럼 이어진 부서명은 한 번에
      const start = words.findIndex((w) => DEPT.test(w) && w.length >= 2 && !TITLES_KO.includes(w) && !COMPANY_WORD.test(w));
      if (start >= 0) {
        let end = start;
        while (end + 1 < words.length && DEPT.test(words[end + 1]) && !TITLES_KO.includes(words[end + 1])) end++;
        dept = words.slice(start, end + 1).join(' ');
      }
    }
    if (title) f.title = title;
    if (dept) f.department = dept;
    if (title || dept) {
      const left = clean(l.text.replace(title, '').replace(dept, ''));
      l.used = !left || left.length <= 1;
      if (!l.used) l.text = left;
    }
  }

  // 9) 회사가 아직 없으면 — 이메일 도메인 앞부분이 들어간 줄, 아니면 가장 큰 글씨의 남은 줄
  if (!f.company) {
    const domain = f.email.split('@')[1]?.split('.')[0] ?? '';
    const byDomain = domain.length >= 3 ? lines.find((l) => !l.used && l.text.toLowerCase().replace(/\s/g, '').includes(domain.toLowerCase())) : undefined;
    const byHeight = lines
      .filter((l) => !l.used && l.text.length >= 2 && l.text.length <= 20 && !/\d{3,}/.test(l.text))
      .sort((a, b) => (b.height ?? 0) - (a.height ?? 0))[0];
    const pick = byDomain ?? (byHeight && (byHeight.height ?? 0) >= maxH * 0.6 ? byHeight : undefined);
    if (pick) {
      f.company = pick.text;
      pick.used = true;
    }
  }

  const extra = [
    ...others,
    ...lines.filter((l) => !l.used && l.text.length >= 2 && !/^[\W_]+$/.test(l.text)).map((l) => l.text),
  ].slice(0, 10);
  return { fields: f, extra };
}
