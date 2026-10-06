// 영어권(한글이 없는) 명함 분석 — 미국·영국·싱가포르·호주·인도·유럽 등.
// 전화는 국제 전화번호 표준(libphonenumber, 무료·오프라인)으로 판별하고,
// 이름·직함·회사·부서는 줄마다 점수를 매겨 가장 그럴듯한 줄을 고른다
// (이메일 아이디에 든 이름, 글자 크기, 법인 표기, 직함 단어, 이메일 도메인과 같은 회사명 …).
import { CountryCode, findNumbers } from 'libphonenumber-js/max';
import { t } from '../i18n/core';
import { formatKoreanPhone } from './normalize';
import { CardFields } from './types';

export interface LatinLine {
  text: string;
  height?: number;
  used: boolean;
}

type PhoneKind = 'mobile' | 'phone' | 'fax';
export interface IntlNumber {
  value: string;
  digits: string;
  label: PhoneKind | '';
  /** 번호 체계상 휴대폰 (표기가 없을 때 판단에 쓴다) */
  mobileType: boolean;
  country: string;
  start: number;
  end: number;
}

// 번호 앞 표기 (영어권 — 한 글자 표기도 인정: 아이콘 오인식이 적은 영문 명함 기준)
const L_MOBILE = 'M|Mob|Mobile|Mobil|Cell|Cellular|C|H\\.?P|H/P|HP|Handphone';
const L_PHONE = 'T|Tel|Tele|Telephone|Phone|Ph|P|O|Office|Off|Direct|Dir|D|DID|Main|Work|W|Landline|Call';
const L_FAX = 'F|Fax|Facsimile';
const labelEnd = (w: string) => new RegExp(`(?:^|[\\s/·,:|])(?:${w})\\s*[.:)]?\\s*$`, 'i');
const LABEL = { mobile: labelEnd(L_MOBILE), fax: labelEnd(L_FAX), phone: labelEnd(L_PHONE) };
const labelOf = (s: string): PhoneKind | '' => (LABEL.fax.test(s) ? 'fax' : LABEL.mobile.test(s) ? 'mobile' : LABEL.phone.test(s) ? 'phone' : '');
const ALL_LABELS = new RegExp(`(?:^|[\\s/·,:|])(?:${L_MOBILE}|${L_PHONE}|${L_FAX})\\s*[.:)]?\\s*$`, 'i');

const asCountry = (r?: string): CountryCode | undefined => (r && /^[A-Z]{2}$/.test(r) ? (r as CountryCode) : undefined);

/**
 * 한 줄에서 국제 전화번호 찾기.
 * onlyForeign: 한국 명함 경로에서 쓸 때 — '+국가번호' 로 쓴 외국 번호만 (국내 번호는 기존 규칙이 처리)
 */
export function findIntlNumbers(text: string, region?: string, onlyForeign = false): IntlNumber[] {
  const out: IntlNumber[] = [];
  let found: ReturnType<typeof findNumbers> = [];
  try {
    found = findNumbers(text, { defaultCountry: asCountry(region) ?? 'US', v2: true });
  } catch {
    return out;
  }
  let cursor = 0;
  for (const m of found) {
    const n = m.number;
    const raw = text.slice(m.startsAt, m.endsAt);
    if (onlyForeign && (n.country === 'KR' || !/\+\s*\d/.test(raw))) continue;
    // 한국 번호는 국가번호가 없으면 늘 0(또는 15xx 대표번호)으로 시작한다 —
    // "(415) 555-0199" 를 041 지역번호로 읽는 식의 오해석을 버린다
    if (n.country === 'KR' && !/^\s*(?:\+\s*82|\(?\s*0|1[5-9]\d{2})/.test(raw)) continue;
    const before = text.slice(cursor, m.startsAt);
    const after = text.slice(m.endsAt);
    let label = labelOf(before);
    if (!label && /^\s*\(?\s*fax\b/i.test(after)) label = 'fax';
    const type = n.getType();
    const value = n.country === 'KR' ? formatKoreanPhone(n.formatNational()) : n.formatInternational();
    out.push({ value, digits: n.number.replace(/\D/g, ''), label, mobileType: type === 'MOBILE', country: n.country ?? '', start: m.startsAt, end: m.endsAt });
    cursor = m.endsAt;
  }
  return out;
}

/** 찾은 번호와 그 앞 표기를 줄에서 지운다 */
export function removeNumbers(text: string, nums: IntlNumber[]): string {
  let s = text;
  for (const n of [...nums].sort((a, b) => b.start - a.start)) {
    let start = n.start;
    const before = s.slice(0, start);
    const lab = before.match(ALL_LABELS);
    if (lab) start -= lab[0].length - (/^[\s/·,:|]/.test(lab[0]) ? 1 : 0);
    s = s.slice(0, start) + ' ' + s.slice(n.end);
  }
  return s.replace(/[|]\s*(?=[|]|$)/g, ' ').replace(/^[\s|,:;/-]+|[\s|,:;/-]+$/g, '').replace(/\s+/g, ' ').trim();
}

// ── 주소 ────────────────────────────────────────────────────────────────────
const STREET =
  /\b\d{1,6}[A-Za-z]?\s+(?:[\w'.-]+\s+){0,4}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl|Parkway|Pkwy|Highway|Hwy|Square|Sq|Terrace|Circle|Plaza|Quay|Row|Crescent|Close|Walk|Broadway|Spinningfields|Wharf|Mall|Center|Centre)\b\.?/i;
const US_CITY_ZIP = /\b[A-Z][A-Za-z .'-]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b/;
const CA_POST = /\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b/;
const UK_POST = /\b[A-Z]{1,2}\d[A-Z\d]?\s+\d[A-Z]{2}\b/;
const AU_STATE = /\b(?:NSW|VIC|QLD|WA|SA|TAS|ACT|NT)\s+\d{4}\b/;
const SG_POST = /\bSingapore\s+\d{6}\b/i;
const KR_EN = /\b(Seoul|Busan|Incheon|Daegu|Daejeon|Gwangju|Ulsan|Sejong|Gyeonggi|[A-Za-z]+-(ro|gil|daero|dong|gu|si))\b/i;
const ADDR_CONT = /^(?:(?:Suite|Ste|Unit|Level|Floor|Fl|Room|Rm|Building|Bldg|Tower|#)\s*[\w-]+|[A-Z][A-Za-z .'-]+,?\s+(?:[A-Z]{2}\s+\d{5}|[A-Z]{1,2}\d[A-Z\d]?\s+\d[A-Z]{2}|[A-Z]\d[A-Z]\s?\d[A-Z]\d|\d{4,6}))/;
const POSTAL = (s: string) => US_CITY_ZIP.test(s) || CA_POST.test(s) || UK_POST.test(s) || AU_STATE.test(s) || SG_POST.test(s);
const isAddress = (s: string) => /\d/.test(s) && (STREET.test(s) || POSTAL(s) || (KR_EN.test(s) && /\d/.test(s)) || /^(?:Level|Suite|Floor)\s+\d+/i.test(s));

// ── 회사·직함·부서·이름 ───────────────────────────────────────────────────────
const LEGAL =
  /(?:\bInc\b\.?|\bIncorporated\b|\bCorp\b\.?|\bCorporation\b|\bLLC\b|\bL\.L\.C\.|\bLLP\b|\bPLC\b|\bLtd\b\.?|\bLimited\b|\bGmbH\b|\bAG\b|\bS\.?A\.?S?\b|\bB\.V\.|\bN\.V\.|\bPte\b\.?|\bPty\b|\bPvt\b\.?|\bSdn\.?\s*Bhd\b|\bBhd\b|\bCo\.,?|\bK\.K\.|\bOy\b|\bAB\b|\bSRL\b|\bS\.r\.l\.|\bGroup\b|\bHoldings\b)/;
const COMPANY_WORDS =
  /\b(?:Partners|Associates|Holdings|Realty|Studio|Studios|Labs?|Logistics|Consulting|Consultants|Technologies|Technology|Tech|Solutions|Systems|Software|Analytics|Ventures|Capital|Media|Foods?|Energy|Exports?|Imports?|Tours|Travel|Trading|Supplies|Supply|Plumbing|Heating|Aerospace|Robotics|Therapeutics|Biotherapeutics|Pharma|Pharmaceuticals|Bank|Financial|Finance|Insurance|Medical|Health|Healthcare|Clinic|Hospital|Legal|Law|Property|Properties|Infotech|Industries|Industrial|Manufacturing|Engineering|Construction|Builders|Motors|Airlines|Hotel|Hotels|Restaurant|Cafe|Coffee|Design|Designs|Agency|Marketing|Communications|Networks|Digital|Interactive|Cloud|Data|Security|Electronics|Electric|Chemicals|Bio|Biotech|Maschinenbau|Institute|University|College|School|Academy|Foundation|Association|Society|Council|Ministry|Department of|Bureau|Services|Service|Enterprises|International|Global|Worldwide|Brands|Retail|Store|Shop|Market|Markets)\b/i;
const TITLE_WORDS =
  /\b(?:President|Vice|VP|SVP|EVP|AVP|Director|Manager|Mgr|Engineer|Developer|Designer|Consultant|Analyst|Specialist|Officer|Executive|Representative|Rep|Advisor|Adviser|Architect|Scientist|Coordinator|Administrator|Accountant|Attorney|Lawyer|Counsel|Solicitor|Barrister|Recruiter|Producer|Editor|Strategist|Agent|Broker|Realtor|REALTOR|Associate|Founder|Co-?Founder|Owner|Chairman|Chairwoman|Chair|CEO|CTO|CFO|COO|CMO|CIO|CPO|CRO|CSO|CDO|Head|Lead|Intern|Professor|Lecturer|Researcher|Nurse|Physician|Doctor|Dentist|Pharmacist|Technician|Partner|Principal|Assistant|Secretary|Supervisor|Superintendent|Controller|Treasurer|Auditor|Trainer|Teacher|Instructor|Chef|Pilot|Captain|Operator|Programmer|Planner|Buyer|Merchandiser|Curator|Photographer|Writer|Journalist|Reporter|Evangelist|Ambassador|Leader|Owner|Proprietor|Commissioner|Inspector|Surveyor|Therapist|Counselor|Coach)\b/;
const DEPT_WORDS = /\b(?:Department|Dept\.?|Division|Team|Unit|Practice|Bureau)\b/i;
const HONORIFIC = /^(?:Dr|Mr|Mrs|Ms|Miss|Mx|Prof|Sir|Dame|Rev)\.?\s+/i;
const CREDENTIALS = /(?:,?\s+(?:Ph\.?D|MBA|CPA|CFA|PMP|Esq|MD|M\.D|DDS|JD|RN|PE|P\.Eng|CPP|LLB|LLM|MSc|BSc|BA|MA|Jr|Sr|II|III|IV)\.?)+\s*$/i;
const PARTICLES = new Set(['de', 'da', 'del', 'della', 'der', 'den', 'van', 'von', 'bin', 'binti', 'bint', 'al', 'el', 'la', 'le', 'du', 'dos', 'das', 'di', 'mc']);

const letters = (s: string) => s.toLowerCase().replace(/[^a-z]/g, '');

/** 이름처럼 생긴 줄을 다듬는다 — 호칭(Dr.)·학위(PhD, Jr.) 빼고, 전부 대문자면 첫 글자만 대문자로 */
export function cleanPersonName(raw: string): string {
  let s = raw.replace(HONORIFIC, '').replace(CREDENTIALS, '').replace(/[,]+$/, '').trim();
  if (/[A-Z]/.test(s) && s === s.toUpperCase()) {
    s = s.toLowerCase().replace(/(^|[\s'-])([a-z])/g, (_m, p: string, c: string) => p + c.toUpperCase());
  }
  return s;
}

function nameShape(s: string): boolean {
  const name = cleanPersonName(s);
  if (!name || /\d|@/.test(name) || name.length > 40) return false;
  const tokens = name.split(/\s+/);
  if (tokens.length < 2 || tokens.length > 5) return false;
  return tokens.every((w) => PARTICLES.has(w.toLowerCase()) || /^[A-Z][a-zA-Z'’-]*\.?$/.test(w) || /^[A-Z]\.?$/.test(w));
}

interface Scored {
  line: LatinLine;
  text: string;
}

/** 이메일·웹·전화를 뺀 뒤 남은 줄들로 영어권 명함의 나머지 칸을 채운다 */
export function parseLatinRest(lines: LatinLine[], f: CardFields, others: string[]) {
  const maxH = Math.max(1, ...lines.map((l) => l.height ?? 0));
  const local = f.email.split('@')[0] ?? '';
  const domain = letters(f.email.split('@')[1]?.split('.')[0] ?? '');

  // "Kevin Nguyen | Software Engineer" 처럼 한 줄에 이름·직함이 있으면 나눠 본다
  for (const l of [...lines]) {
    if (l.used || !/\s[|•]\s|\s-\s/.test(l.text)) continue;
    const parts = l.text.split(/\s+[|•-]\s+/).map((p) => p.trim()).filter(Boolean);
    if (parts.length === 2 && nameShape(parts[0]) && TITLE_WORDS.test(parts[1])) {
      l.text = parts[0];
      lines.splice(lines.indexOf(l) + 1, 0, { text: parts[1], height: l.height, used: false });
    }
  }

  // 주소 — 거리·우편번호 줄에서 시작해 이어지는 줄(도시·우편번호·Suite)을 붙인다
  for (let i = 0; i < lines.length && !f.address; i++) {
    const l = lines[i];
    if (l.used || !isAddress(l.text)) continue;
    const parts = [l.text];
    l.used = true;
    for (let j = i + 1; j < lines.length && parts.length < 3; j++) {
      const n = lines[j];
      if (n.used) continue;
      if (isAddress(n.text) || ADDR_CONT.test(n.text) || POSTAL(n.text)) {
        parts.push(n.text);
        n.used = true;
      } else break;
    }
    f.address = parts.map((p) => p.replace(/^(?:Address|Add|A)\s*[.:]\s*/i, '').replace(/,\s*$/, '')).join(', ');
  }

  const rest = (): Scored[] => lines.filter((l) => !l.used && /[A-Za-z]/.test(l.text)).map((l) => ({ line: l, text: l.text }));
  const hRatio = (l: LatinLine) => (l.height ? l.height / maxH : 0.5);

  // 이름
  const nameScore = (s: Scored) => {
    if (!nameShape(s.text) || LEGAL.test(s.text) || DEPT_WORDS.test(s.text)) return -1;
    let score = 1 + hRatio(s.line) * 3;
    if (TITLE_WORDS.test(s.text)) score -= 3;
    if (COMPANY_WORDS.test(s.text)) score -= 2;
    if (HONORIFIC.test(s.text) || CREDENTIALS.test(s.text)) score += 2;
    // 이메일 아이디에 이름 조각이 들어 있으면 강한 근거 (jane.smith@, mturner@)
    const hits = cleanPersonName(s.text)
      .split(/\s+/)
      .map(letters)
      .filter((w) => w.length >= 2 && local && letters(local).includes(w)).length;
    score += Math.min(hits, 2) * 3;
    // 회사 도메인과 같은 줄은 이름이 아니다
    if (domain.length >= 4 && letters(s.text).includes(domain)) score -= 4;
    return score;
  };
  const people = rest()
    .map((s) => ({ s, score: nameScore(s) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score);
  if (people[0]) {
    f.name = cleanPersonName(people[0].s.text);
    people[0].s.line.used = true;
  }

  // 직함 — 직함 단어가 든 줄 (회사 법인 표기가 있으면 제외)
  const titles = rest()
    .filter((s) => TITLE_WORDS.test(s.text) && !LEGAL.test(s.text) && s.text.split(/\s+/).length <= 8 && !/\d{3,}/.test(s.text))
    .sort((a, b) => Number(DEPT_WORDS.test(a.text)) - Number(DEPT_WORDS.test(b.text)));
  if (titles[0]) {
    f.title = titles[0].text;
    titles[0].line.used = true;
  }

  // 부서
  const dept = rest().find((s) => DEPT_WORDS.test(s.text) && !LEGAL.test(s.text) && s.text.split(/\s+/).length <= 6);
  if (dept) {
    f.department = dept.text;
    dept.line.used = true;
  }

  // 회사 — 법인 표기 > 이메일 도메인과 같은 이름 > 업종 단어 > 큰 글씨
  const companyScore = (s: Scored) => {
    if (/\d{3,}/.test(s.text) || s.text.length > 60) return -1;
    let score = 0;
    if (LEGAL.test(s.text)) score += 6;
    const flat = letters(s.text);
    if (domain.length >= 3 && flat.length >= 3 && (flat.includes(domain) || domain.includes(flat))) score += 5;
    if (COMPANY_WORDS.test(s.text)) score += 2;
    if (/^[A-Z0-9 &.,'-]{3,}$/.test(s.text)) score += 1;
    if (TITLE_WORDS.test(s.text)) score -= 3;
    if (nameShape(s.text) && !COMPANY_WORDS.test(s.text) && !LEGAL.test(s.text)) score -= 2;
    score += hRatio(s.line) * 1.5;
    return score;
  };
  const companies = rest()
    .map((s) => ({ s, score: companyScore(s) }))
    .filter((x) => x.score >= 1.5)
    .sort((a, b) => b.score - a.score);
  if (companies[0]) {
    f.company = companies[0].s.text;
    companies[0].s.line.used = true;
  }

  // 이름을 못 찾았는데 이메일 아이디가 이름처럼 생겼으면 (jane.smith → Jane Smith)
  if (!f.name && /^[a-z]+[._][a-z]+$/i.test(local)) {
    f.name = local
      .split(/[._]/)
      .map((w) => w[0].toUpperCase() + w.slice(1).toLowerCase())
      .join(' ');
  }
  void others;
}

/** 다른 번호 칸이 차 있을 때 기타로 남기는 문구 */
export const otherPhone = (kind: PhoneKind, value: string) =>
  kind === 'mobile' ? t('휴대폰 {1}', { 1: value }) : kind === 'fax' ? t('팩스 {1}', { 1: value }) : t('전화 {1}', { 1: value });
