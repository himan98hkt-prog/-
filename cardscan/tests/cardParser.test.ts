// 온디바이스 OCR 결과(줄 목록) → 명함 필드. 실제 한국 명함에서 흔한 배치를 재현한 샘플로 검증한다.
import { describe, expect, it } from 'vitest';
import { OcrLineInput, parseCardText } from '../src/core/cardParser';

/** [텍스트, 글자 높이] 목록을 OCR 줄로 */
const ocr = (...rows: [string, number?][]): OcrLineInput[] =>
  rows.map(([text, height = 30], i) => ({ text, height, top: i * 60, left: 40, width: text.length * 20, block: i }));

describe('parseCardText — 전형적인 국내 명함', () => {
  it('회사·이름+직함·부서·M/T/F·이메일·주소', () => {
    const r = parseCardText(
      ocr(
        ['(주)한빛상사', 40],
        ['영업1팀', 26],
        ['홍길동 팀장', 60],
        ['Gildong Hong', 24],
        ['M. 010-1234-5678', 24],
        ['T. 02-123-4567  F. 02-123-4568', 24],
        ['E. gd.hong@hanbit.co.kr', 24],
        ['서울특별시 중구 세종대로 110 한빛빌딩 5층', 22],
      ),
    );
    expect(r.fields).toMatchObject({
      company: '(주)한빛상사',
      name: '홍길동',
      title: '팀장',
      department: '영업1팀',
      nameEn: 'Gildong Hong',
      mobile: '010-1234-5678',
      phone: '02-123-4567',
      fax: '02-123-4568',
      email: 'gd.hong@hanbit.co.kr',
      address: '서울특별시 중구 세종대로 110 한빛빌딩 5층',
    });
    expect(r.extra).toEqual([]);
  });

  it('직함이 이름 앞, 영문 라벨(Mobile/Tel/Fax), 웹사이트, 두 줄 주소', () => {
    const r = parseCardText(
      ocr(
        ['주식회사 미래테크', 36],
        ['www.miraetech.kr', 20],
        ['대표이사', 24],
        ['김 철 수', 56],
        ['Mobile +82 10-9876-5432', 22],
        ['Tel 031-789-1234 Fax 031-789-1235', 22],
        ['ceo@miraetech.kr', 22],
        ['경기도 성남시 분당구 판교역로 235', 20],
        ['에이치스퀘어 N동 7층', 20],
      ),
    );
    expect(r.fields).toMatchObject({
      company: '주식회사 미래테크',
      name: '김철수',
      title: '대표이사',
      mobile: '010-9876-5432',
      phone: '031-789-1234',
      fax: '031-789-1235',
      email: 'ceo@miraetech.kr',
      website: 'https://www.miraetech.kr',
      address: '경기도 성남시 분당구 판교역로 235 에이치스퀘어 N동 7층',
    });
  });

  it('라벨 없는 번호는 010 이면 휴대폰, 아니면 전화→팩스 순서', () => {
    const r = parseCardText(ocr(['이영희 과장', 50], ['대한물산', 40], ['010 5555 1234'], ['02 333 4444'], ['02 333 4445']));
    expect(r.fields.mobile).toBe('010-5555-1234');
    expect(r.fields.phone).toBe('02-333-4444');
    expect(r.fields.fax).toBe('02-333-4445');
    expect(r.fields.name).toBe('이영희');
    expect(r.fields.title).toBe('과장');
  });

  it('H.P / 휴대폰 / 내선 표기', () => {
    const r = parseCardText(ocr(['박민수', 50], ['H.P : 010-2222-3333'], ['전화 : 02-555-1000 (내선 205)'], ['팩스 : 02-555-1001']));
    expect(r.fields.mobile).toBe('010-2222-3333');
    expect(r.fields.phone).toBe('02-555-1000 (내선 205)');
    expect(r.fields.fax).toBe('02-555-1001');
  });

  it('OCR 이 숫자 0 을 O 로 읽어도 바로잡는다', () => {
    const r = parseCardText(ocr(['최지훈', 50], ['M 01O-7777-8888']));
    expect(r.fields.mobile).toBe('010-7777-8888');
  });

  it('부서가 두 단어(본부 + 팀)', () => {
    const r = parseCardText(ocr(['(주)세종물류', 40], ['경영지원본부 인사팀', 24], ['정수빈 대리', 50], ['010-1111-2222']));
    expect(r.fields.department).toBe('경영지원본부 인사팀');
    expect(r.fields.title).toBe('대리');
    expect(r.fields.name).toBe('정수빈');
  });

  it('두 글자 성(남궁)과 연구원 직함', () => {
    const r = parseCardText(ocr(['한국바이오연구소', 34], ['남궁민수', 52], ['책임연구원', 24], ['M 010-4444-5555'], ['ms.namgung@kbio.re.kr']));
    expect(r.fields.name).toBe('남궁민수');
    expect(r.fields.title).toBe('책임연구원');
    expect(r.fields.company).toBe('한국바이오연구소');
    expect(r.fields.email).toBe('ms.namgung@kbio.re.kr');
  });

  it('영문 명함 (Inc., Seoul 주소)', () => {
    const r = parseCardText(
      ocr(
        ['Startlab Inc.', 36],
        ['JANE PARK', 50],
        ['Marketing Manager', 24],
        ['+82 10 3333 4444', 22],
        ['jane@startlab.io', 22],
        ['12, Teheran-ro 1-gil, Gangnam-gu, Seoul', 20],
      ),
    );
    expect(r.fields.company).toBe('Startlab Inc.');
    expect(r.fields.name).toBe('Jane Park');
    expect(r.fields.nameEn).toBe('Jane Park');
    expect(r.fields.title).toBe('Marketing Manager');
    expect(r.fields.mobile).toBe('010-3333-4444');
    expect(r.fields.address).toBe('12, Teheran-ro 1-gil, Gangnam-gu, Seoul');
  });

  it('회사 표기가 없으면 이메일 도메인과 같은 줄을 회사로', () => {
    const r = parseCardText(ocr(['HANBIT', 44], ['윤서준 실장', 50], ['seojun@hanbit.com'], ['010-1212-3434']));
    expect(r.fields.company).toBe('HANBIT');
    expect(r.fields.name).toBe('윤서준');
    expect(r.fields.title).toBe('실장');
  });

  it('지역명·직함·부서 단어를 이름으로 착각하지 않는다', () => {
    const r = parseCardText(ocr(['서울 본사', 30], ['영업팀', 30], ['대표', 30], ['강민호', 48], ['010-9999-0000']));
    expect(r.fields.name).toBe('강민호');
  });

  it('남는 문구는 기타로 보존', () => {
    const r = parseCardText(ocr(['(주)한빛상사', 40], ['홍길동', 50], ['010-1234-5678'], ['Instagram @hanbit_official'], ['ISO 9001 인증']));
    expect(r.extra).toEqual(['Instagram @hanbit_official', 'ISO 9001 인증']);
  });

  it('빈 입력', () => {
    const r = parseCardText([]);
    expect(r.fields.name).toBe('');
    expect(r.extra).toEqual([]);
  });

  it('문자열(줄바꿈) 입력도 받는다', () => {
    const r = parseCardText('(주)테스트\n홍길동 부장\nT 02-111-2222\nhong@test.com');
    expect(r.fields).toMatchObject({ company: '(주)테스트', name: '홍길동', title: '부장', phone: '02-111-2222', email: 'hong@test.com' });
  });
});

describe('parseCardText — 아이콘(☎📱📠)만 있고 표기가 없는 번호', () => {
  const phones = (...rows: string[]) => parseCardText(ocr(['(주)한빛상사', 40], ['홍길동 팀장', 60], ...rows.map((r) => [r] as [string])));

  it('아이콘이 C·O·D 같은 글자로 읽혀도 번호로 판단', () => {
    const r = phones('C 010-1234-5678', 'O 02-123-4567', 'D 02-123-4568');
    expect(r.fields).toMatchObject({ mobile: '010-1234-5678', phone: '02-123-4567', fax: '02-123-4568' });
    expect(r.fields.company).toBe('(주)한빛상사');
    expect(r.extra).toEqual([]);
  });

  it('아이콘이 기호로 읽힌 경우', () => {
    const r = phones('📱 010-1234-5678', '☎ 02-123-4567', '📠 02-123-4568', '© 1588-0000');
    expect(r.fields).toMatchObject({ mobile: '010-1234-5678', phone: '02-123-4567', fax: '02-123-4568' });
    expect(r.extra).toEqual(['전화 1588-0000']);
  });

  it('아이콘이 0 으로 읽혀 번호 앞에 붙어도 올바른 번호만', () => {
    const r = phones('0010-1234-5678', '002-123-4567');
    expect(r.fields.mobile).toBe('010-1234-5678');
    expect(r.fields.phone).toBe('02-123-4567');
  });

  it('한 줄에 아이콘과 번호가 붙어 이어진 경우', () => {
    const r = phones('📱010-1234-5678 ☎031-765-4321 📠031-765-4322');
    expect(r.fields).toMatchObject({ mobile: '010-1234-5678', phone: '031-765-4321', fax: '031-765-4322' });
  });

  it('잘못 읽힌 표기(T)보다 010 번호가 우선 — 휴대폰으로', () => {
    const r = phones('T 010-1234-5678', 'F 02-123-4568');
    expect(r.fields.mobile).toBe('010-1234-5678');
    expect(r.fields.phone).toBe('');
    expect(r.fields.fax).toBe('02-123-4568');
  });

  it('표기가 윗줄에 따로 있거나 번호 뒤에 붙은 경우', () => {
    const r = phones('Fax', '02-123-4599', '02-123-4500 (대표)');
    expect(r.fields.fax).toBe('02-123-4599');
    expect(r.fields.phone).toBe('02-123-4500');
    const r2 = phones('02-777-1000', '02-777-1001 (팩스)');
    expect(r2.fields).toMatchObject({ phone: '02-777-1000', fax: '02-777-1001' });
  });

  it('050 평생번호는 순서와 상관없이 팩스로', () => {
    const r = phones('0505-123-4567', '02-555-1234');
    expect(r.fields).toMatchObject({ phone: '02-555-1234', fax: '0505-123-4567' });
  });

  it('표기 없는 번호가 셋 이상이면 같은 국번만 팩스, 나머지는 기타로 보존', () => {
    const r = phones('02-111-2222', '031-333-4444', '02-111-2223');
    expect(r.fields).toMatchObject({ phone: '02-111-2222', fax: '02-111-2223' });
    expect(r.extra).toEqual(['전화 031-333-4444']);
  });

  it('아이콘만 따로 한 줄로 읽힌 찌꺼기는 회사·기타로 쓰지 않는다', () => {
    const r = parseCardText(ocr(['홍길동', 60], ['C', 40], ['010-1234-5678'], ['口 02-123-4567']));
    expect(r.fields.company).toBe('');
    expect(r.fields.mobile).toBe('010-1234-5678');
    expect(r.fields.phone).toBe('02-123-4567');
    expect(r.extra).toEqual([]);
  });

  it('사업자번호·계좌·날짜는 전화번호로 잡지 않는다', () => {
    const r = phones('사업자등록번호 123-45-67890', '국민 110-123-456789', '2026-10-06', '010-1234-5678');
    expect(r.fields.mobile).toBe('010-1234-5678');
    expect(r.fields.phone).toBe('');
    expect(r.fields.fax).toBe('');
  });
});

