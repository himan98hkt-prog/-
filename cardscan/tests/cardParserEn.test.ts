// 영어권 명함 — 미국·캐나다·영국·싱가포르·호주·인도·독일 등. 모두 가상의 인물·회사 (US 555-01xx 는 가상 번호 대역).
import { describe, expect, it } from 'vitest';
import { OcrLineInput, parseCardText } from '../src/core/cardParser';
import { CardFields } from '../src/core/types';

/** [텍스트, 글자 높이] → OCR 줄 */
const ocr = (...rows: (string | [string, number])[]): OcrLineInput[] =>
  rows.map((r, i) => {
    const [text, height] = typeof r === 'string' ? [r, 22] : r;
    return { text, height, top: i * 50, left: 40, width: text.length * 14, block: i };
  });

type Case = [title: string, lines: OcrLineInput[], expected: Partial<CardFields>, region?: string];

const CASES: Case[] = [
  [
    '미국 — 기본형',
    ocr(['Acme Robotics, Inc.', 30], ['Jane Smith', 44], ['VP of Sales', 22], 'Mobile +1 (415) 555-0199', 'Office (415) 555-0142', 'jane.smith@acmerobotics.com', 'www.acmerobotics.com', '100 Market Street, Suite 300', 'San Francisco, CA 94105'),
    { company: 'Acme Robotics, Inc.', name: 'Jane Smith', title: 'VP of Sales', mobile: '+1 415 555 0199', phone: '+1 415 555 0142', email: 'jane.smith@acmerobotics.com', website: 'https://www.acmerobotics.com', address: '100 Market Street, Suite 300, San Francisco, CA 94105' },
  ],
  [
    '미국 — 라벨 한 글자(M/T/F)와 점 구분 번호',
    ocr(['BRIGHTPATH CONSULTING LLC', 28], ['Michael J. Turner', 40], ['Senior Consultant', 20], 'M 646.555.0117', 'T 212.555.0186', 'F 212.555.0187', 'mturner@brightpath.co', '350 Fifth Avenue, New York, NY 10118'),
    { company: 'BRIGHTPATH CONSULTING LLC', name: 'Michael J. Turner', title: 'Senior Consultant', mobile: '+1 646 555 0117', phone: '+1 212 555 0186', fax: '+1 212 555 0187', email: 'mturner@brightpath.co', address: '350 Fifth Avenue, New York, NY 10118' },
  ],
  [
    '미국 — 직함이 이름 위, 내선',
    ocr(['Chief Technology Officer', 20], ['David Park', 42], ['Northwind Analytics', 30], 'Direct: (312) 555-0161 ext. 204', 'Cell: 312-555-0178', 'dpark@northwind.ai'),
    { name: 'David Park', title: 'Chief Technology Officer', company: 'Northwind Analytics', mobile: '+1 312 555 0178', phone: '+1 312 555 0161 ext. 204', email: 'dpark@northwind.ai' },
  ],
  [
    '미국 — Dr. 호칭·학위',
    ocr(['Dr. Emily Chen, PhD', 40], ['Principal Research Scientist', 20], ['Helix Biotherapeutics Corp.', 28], 'Tel +1 617 555 0134', 'emily.chen@helixbio.com', '45 Binney St, Cambridge, MA 02142'),
    { name: 'Emily Chen', title: 'Principal Research Scientist', company: 'Helix Biotherapeutics Corp.', phone: '+1 617 555 0134', email: 'emily.chen@helixbio.com', address: '45 Binney St, Cambridge, MA 02142' },
  ],
  [
    '미국 — 부서 줄이 따로',
    ocr(['Summit Financial Group', 30], ['Robert Garcia', 40], ['Account Executive', 20], ['Commercial Banking Division', 18], 'Mobile 305 555 0150', 'robert.garcia@summitfg.com'),
    { company: 'Summit Financial Group', name: 'Robert Garcia', title: 'Account Executive', department: 'Commercial Banking Division', mobile: '+1 305 555 0150', email: 'robert.garcia@summitfg.com' },
  ],
  [
    '미국 — 무료전화·웹사이트 http',
    ocr(['Bluewave Logistics', 30], ['Sarah Johnson', 40], ['Operations Manager', 20], 'Phone: 1-800-555-0199', 'Cell: (713) 555-0128', 's.johnson@bluewavelogistics.com', 'https://bluewavelogistics.com', '2200 Post Oak Blvd, Houston, TX 77056'),
    { company: 'Bluewave Logistics', name: 'Sarah Johnson', title: 'Operations Manager', phone: '+1 800 555 0199', mobile: '+1 713 555 0128', email: 's.johnson@bluewavelogistics.com', address: '2200 Post Oak Blvd, Houston, TX 77056' },
  ],
  [
    '미국 — 높이 정보 없이 (이메일로 이름 찾기)',
    ocr('Greenleaf Studio', 'Creative Director', 'Olivia Martinez', 'olivia@greenleafstudio.com', '(503) 555-0193'),
    { company: 'Greenleaf Studio', name: 'Olivia Martinez', title: 'Creative Director', email: 'olivia@greenleafstudio.com', phone: '+1 503 555 0193' },
  ],
  [
    '미국 — 이름 대문자',
    ocr(['JAMES O\'CONNOR', 38], ['Regional Sales Manager', 20], ['Pinecrest Medical Supplies', 26], 'M: 206-555-0175', 'james.oconnor@pinecrestmed.com'),
    { name: "James O'Connor", title: 'Regional Sales Manager', company: 'Pinecrest Medical Supplies', mobile: '+1 206 555 0175', email: 'james.oconnor@pinecrestmed.com' },
  ],
  [
    '캐나다 — 우편번호',
    ocr(['Maple Ridge Software Ltd.', 28], ['Priya Sharma', 40], ['Product Manager', 20], 'T +1 416 555 0123', 'priya.sharma@mapleridge.ca', '200 Bay Street, Toronto, ON M5J 2J2'),
    { company: 'Maple Ridge Software Ltd.', name: 'Priya Sharma', title: 'Product Manager', phone: '+1 416 555 0123', email: 'priya.sharma@mapleridge.ca', address: '200 Bay Street, Toronto, ON M5J 2J2' },
  ],
  [
    '영국 — +44, 우편번호, 두 줄 주소',
    ocr(['Thornbury & Hale LLP', 28], ['Oliver Bennett', 40], ['Associate Director', 20], 'T +44 20 7946 0321', 'M +44 7911 123456', 'oliver.bennett@thornburyhale.co.uk', '12 Fleet Street', 'London EC4Y 1AA'),
    { company: 'Thornbury & Hale LLP', name: 'Oliver Bennett', title: 'Associate Director', phone: '+44 20 7946 0321', mobile: '+44 7911 123456', email: 'oliver.bennett@thornburyhale.co.uk', address: '12 Fleet Street, London EC4Y 1AA' },
  ],
  [
    '영국 — 국내 표기(0으로 시작), 지역 GB · 번호 체계에 없는 번호는 적힌 그대로',
    ocr(['Harbourside Media Ltd', 28], ['Charlotte Evans', 40], ['Head of Marketing', 20], 'Tel: 020 7946 0958', 'Mob: 07911 654321', 'charlotte@harbourside.media'),
    { company: 'Harbourside Media Ltd', name: 'Charlotte Evans', title: 'Head of Marketing', phone: '+44 20 7946 0958', mobile: '07911 654321', email: 'charlotte@harbourside.media' },
    'GB',
  ],
  [
    '영국 — PLC',
    ocr(['Westbridge Energy PLC', 28], ['George Wilson', 40], ['Managing Director', 20], '+44 161 496 0754', 'g.wilson@westbridge-energy.com', '1 Spinningfields, Manchester M3 3AP'),
    { company: 'Westbridge Energy PLC', name: 'George Wilson', title: 'Managing Director', phone: '+44 161 496 0754', email: 'g.wilson@westbridge-energy.com', address: '1 Spinningfields, Manchester M3 3AP' },
  ],
  [
    '싱가포르 — Pte. Ltd., 우편번호 6자리',
    ocr(['Lionbridge Trading Pte. Ltd.', 28], ['Tan Wei Ming', 40], ['Business Development Manager', 20], 'Tel: +65 6123 4567', 'HP: +65 9123 4567', 'weiming.tan@lionbridgetrading.sg', '1 Raffles Place, #20-01, Singapore 048616'),
    { company: 'Lionbridge Trading Pte. Ltd.', name: 'Tan Wei Ming', title: 'Business Development Manager', phone: '+65 6123 4567', mobile: '+65 9123 4567', email: 'weiming.tan@lionbridgetrading.sg', address: '1 Raffles Place, #20-01, Singapore 048616' },
  ],
  [
    '호주 — Pty Ltd, 주 약어',
    ocr(['Coastline Property Group Pty Ltd', 26], ['Liam Walker', 40], ['Senior Property Advisor', 20], 'P +61 2 9374 4000', 'M +61 412 345 678', 'liam.walker@coastlineproperty.com.au', 'Level 12, 1 Martin Place, Sydney NSW 2000'),
    { company: 'Coastline Property Group Pty Ltd', name: 'Liam Walker', title: 'Senior Property Advisor', phone: '+61 2 9374 4000', mobile: '+61 412 345 678', email: 'liam.walker@coastlineproperty.com.au', address: 'Level 12, 1 Martin Place, Sydney NSW 2000' },
  ],
  [
    '인도 — +91',
    ocr(['Sunrise Infotech Pvt. Ltd.', 28], ['Rahul Mehta', 40], ['Technical Lead', 20], 'Mobile: +91 98765 43210', 'Office: +91 22 2345 6789', 'rahul.mehta@sunriseinfotech.in'),
    { company: 'Sunrise Infotech Pvt. Ltd.', name: 'Rahul Mehta', title: 'Technical Lead', mobile: '+91 98765 43210', phone: '+91 22 2345 6789', email: 'rahul.mehta@sunriseinfotech.in' },
  ],
  [
    '독일 — GmbH',
    ocr(['Kessler Maschinenbau GmbH', 28], ['Lukas Becker', 40], ['Sales Engineer', 20], 'Tel. +49 30 901820', 'Mobil +49 151 23456789', 'Fax +49 30 9018211', 'l.becker@kessler-mb.de', 'www.kessler-mb.de'),
    { company: 'Kessler Maschinenbau GmbH', name: 'Lukas Becker', title: 'Sales Engineer', phone: '+49 30 901820', mobile: '+49 1512 3456789', fax: '+49 30 9018211', email: 'l.becker@kessler-mb.de', website: 'https://www.kessler-mb.de' },
  ],
  [
    '미국 — 회사명에 법인 표기 없음, 이메일 도메인으로',
    ocr(['Jordan Lee', 40], ['Founder & CEO', 20], ['Fieldnote', 30], 'jordan@fieldnote.app', '(415) 555-0107'),
    { name: 'Jordan Lee', title: 'Founder & CEO', company: 'Fieldnote', email: 'jordan@fieldnote.app', phone: '+1 415 555 0107' },
  ],
  [
    '미국 — 한 줄에 전화 두 개',
    ocr(['Redwood Legal Partners', 28], ['Amanda Brooks', 40], ['Attorney at Law', 20], 'T 415.555.0170 | F 415.555.0171', 'abrooks@redwoodlegal.com'),
    { company: 'Redwood Legal Partners', name: 'Amanda Brooks', title: 'Attorney at Law', phone: '+1 415 555 0170', fax: '+1 415 555 0171', email: 'abrooks@redwoodlegal.com' },
  ],
  [
    '미국 — 이름·직함 한 줄',
    ocr(['Kevin Nguyen | Software Engineer', 30], ['Orbital Labs Inc.', 26], 'kevin.nguyen@orbitallabs.io', '+1 408 555 0145'),
    { name: 'Kevin Nguyen', title: 'Software Engineer', company: 'Orbital Labs Inc.', email: 'kevin.nguyen@orbitallabs.io', phone: '+1 408 555 0145' },
  ],
  [
    '미국 — 쉼표 직함',
    ocr(['Natalie Rivera', 40], ['Director, Global Partnerships', 20], ['Vertex Cloud Corporation', 28], 'Mobile: +1 (512) 555-0182', 'nrivera@vertexcloud.com', '500 W 2nd St, Austin, TX 78701'),
    { name: 'Natalie Rivera', title: 'Director, Global Partnerships', company: 'Vertex Cloud Corporation', mobile: '+1 512 555 0182', email: 'nrivera@vertexcloud.com', address: '500 W 2nd St, Austin, TX 78701' },
  ],
  [
    '뉴질랜드',
    ocr(['Kiwi Harvest Exports Ltd', 28], ['Hannah Thompson', 40], ['Export Manager', 20], 'P +64 9 379 0123', 'M +64 21 123 4567', 'hannah@kiwiharvest.co.nz'),
    { company: 'Kiwi Harvest Exports Ltd', name: 'Hannah Thompson', title: 'Export Manager', phone: '+64 9 379 0123', mobile: '+64 21 123 4567', email: 'hannah@kiwiharvest.co.nz' },
  ],
  [
    '홍콩',
    ocr(['Pacific Gate Holdings Limited', 28], ['Wong Ka Ming', 40], ['Investment Director', 20], 'Tel: +852 2123 4567', 'Mobile: +852 9123 4567', 'km.wong@pacificgate.hk'),
    { company: 'Pacific Gate Holdings Limited', name: 'Wong Ka Ming', title: 'Investment Director', phone: '+852 2123 4567', mobile: '+852 9123 4567', email: 'km.wong@pacificgate.hk' },
  ],
  [
    '필리핀',
    ocr(['Manila Bay Ventures Inc.', 28], ['Maria Santos', 40], ['Marketing Officer', 20], 'Mobile: +63 917 123 4567', 'maria.santos@manilabayventures.ph'),
    { company: 'Manila Bay Ventures Inc.', name: 'Maria Santos', title: 'Marketing Officer', mobile: '+63 917 123 4567', email: 'maria.santos@manilabayventures.ph' },
  ],
  [
    '아일랜드',
    ocr(['Shamrock Data Ltd.', 28], ['Ciara Murphy', 40], ['Data Analyst', 20], 'T +353 1 234 5678', 'ciara.murphy@shamrockdata.ie', '25 Grafton Street, Dublin 2, D02 X285'),
    { company: 'Shamrock Data Ltd.', name: 'Ciara Murphy', title: 'Data Analyst', phone: '+353 1 234 5678', email: 'ciara.murphy@shamrockdata.ie' },
  ],
  [
    '한국 회사 영문 명함 (+82, 서울 영문 주소)',
    ocr(['Hanbit Trading Co., Ltd.', 28], ['Minsu Kim', 40], ['Sales Manager', 20], 'M +82 10 2345 6789', 'T +82 2 555 1234', 'minsu.kim@hanbit.co.kr', '110 Sejong-daero, Jung-gu, Seoul, Korea'),
    { company: 'Hanbit Trading Co., Ltd.', name: 'Minsu Kim', title: 'Sales Manager', mobile: '010-2345-6789', phone: '02-555-1234', email: 'minsu.kim@hanbit.co.kr', address: '110 Sejong-daero, Jung-gu, Seoul, Korea' },
  ],
  [
    '미국 — 직함 없이 이름·회사·번호',
    ocr(['Tyler Brooks', 40], ['Brooks Plumbing & Heating', 28], 'Call or text 555-0100', '(720) 555-0136', 'tyler@brooksplumbing.com', 'Denver, CO'),
    { name: 'Tyler Brooks', company: 'Brooks Plumbing & Heating', phone: '+1 720 555 0136', email: 'tyler@brooksplumbing.com' },
  ],
  [
    '미국 — Realtor',
    ocr(['Jessica Allen', 40], ['REALTOR® | Broker Associate', 20], ['Golden Key Realty', 28], 'Cell 480-555-0119', 'jessica@goldenkeyrealty.com', 'goldenkeyrealty.com'),
    { name: 'Jessica Allen', title: 'REALTOR® | Broker Associate', company: 'Golden Key Realty', mobile: '+1 480 555 0119', email: 'jessica@goldenkeyrealty.com' },
  ],
  [
    '미국 — 이름이 회사보다 작은 글씨',
    ocr(['NOVA AEROSPACE', 44], ['Daniel Kim', 30], ['Program Manager', 18], 'daniel.kim@novaaero.com', 'O 310-555-0153', 'M 310-555-0154'),
    { company: 'NOVA AEROSPACE', name: 'Daniel Kim', title: 'Program Manager', email: 'daniel.kim@novaaero.com', phone: '+1 310 555 0153', mobile: '+1 310 555 0154' },
  ],
  [
    '미국 — 이름에 가운데 이니셜과 Jr.',
    ocr(['Thomas A. Reed Jr.', 40], ['General Counsel', 20], ['Harborview Capital Partners', 28], 'tom.reed@harborviewcap.com', 'D 617.555.0102'),
    { name: 'Thomas A. Reed', title: 'General Counsel', company: 'Harborview Capital Partners', email: 'tom.reed@harborviewcap.com', phone: '+1 617 555 0102' },
  ],
  [
    '남아공',
    ocr(['Table Mountain Tours (Pty) Ltd', 26], ['Sipho Ndlovu', 40], ['Tour Operations Lead', 20], 'Tel +27 21 123 4567', 'Cell +27 82 123 4567', 'sipho@tablemountaintours.co.za'),
    { company: 'Table Mountain Tours (Pty) Ltd', name: 'Sipho Ndlovu', title: 'Tour Operations Lead', phone: '+27 21 123 4567', mobile: '+27 82 123 4567', email: 'sipho@tablemountaintours.co.za' },
  ],
  [
    '말레이시아 — Sdn Bhd',
    ocr(['Klang Valley Foods Sdn Bhd', 26], ['Nur Aisyah Binti Ahmad', 36], ['Procurement Executive', 20], 'Tel: +60 3 2123 4567', 'H/P: +60 12 345 6789', 'aisyah@kvfoods.com.my'),
    { company: 'Klang Valley Foods Sdn Bhd', name: 'Nur Aisyah Binti Ahmad', title: 'Procurement Executive', phone: '+60 3 2123 4567', mobile: '+60 12 345 6789', email: 'aisyah@kvfoods.com.my' },
  ],
];

describe('parseCardText — 영어권 명함', () => {
  for (const [title, lines, expected, region] of CASES) {
    it(title, () => {
      const r = parseCardText(lines, { region: region ?? 'US' });
      expect(r.fields).toMatchObject(expected);
    });
  }

  it(`견본 ${CASES.length}장 이상`, () => expect(CASES.length).toBeGreaterThanOrEqual(30));
});

describe('지역·혼합 상황', () => {
  it('한국 휴대폰(지역 KR)으로 미국 명함을 찍어도 국가번호 없는 번호를 미국 번호로', () => {
    const r = parseCardText(ocr(['Acme Robotics, Inc.', 30], ['Jane Smith', 44], ['VP of Sales', 22], 'Mobile (415) 555-0199', 'jane.smith@acmerobotics.com'), { region: 'KR' });
    expect(r.fields).toMatchObject({ name: 'Jane Smith', mobile: '+1 415 555 0199' });
  });

  it('한국 명함에 있는 외국 번호(+1)도 국제 표기로', () => {
    const r = parseCardText(ocr(['(주)한빛상사', 30], ['홍길동 팀장', 44], 'M. 010-1234-5678', 'US Office +1 213 555 0110'));
    expect(r.fields.mobile).toBe('010-1234-5678');
    expect(r.fields.phone).toBe('+1 213 555 0110');
  });

  it('정리 단계가 외국 번호를 국내 형식으로 바꾸지 않는다', async () => {
    const { sanitizeFields } = await import('../src/core/normalize');
    const f = sanitizeFields({ name: 'A', mobile: '+1 415 555 0199', phone: '+44 20 7946 0321', fax: '+65 6123 4567' });
    expect(f).toMatchObject({ mobile: '+1 415 555 0199', phone: '+44 20 7946 0321', fax: '+65 6123 4567' });
  });
});
