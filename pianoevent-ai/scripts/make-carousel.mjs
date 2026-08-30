/**
 * 인스타 홍보용 카드뉴스(캐러셀) 13장.
 *
 *   npm run carousel     →  배포/카드뉴스/*.png   (1080×1350, 4:5)
 *
 * 카드뉴스는 손바닥만 한 화면에서 **넘기면서** 읽는다. 그래서 규칙은 셋이다.
 *   · 한 장에 말 하나. 두 개를 넣으면 둘 다 안 읽힌다
 *   · 가장 작은 글씨도 26px 아래로 내리지 않는다(휴대폰에서 10px 남짓이 된다)
 *   · 말로 적을 수 있는 것은 **실제로 뽑힌 종이**를 보여 준다
 *
 * 두 배 크기로 찍고 1080 으로 줄인다(글자 가장자리가 매끈해진다).
 */
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from 'playwright'

const OUT = join('배포', '카드뉴스')
const W = 1080, H = 1350, SCALE = 2

const b64 = (f) => {
  const ext = f.endsWith('.png') ? 'png' : 'jpeg'
  return `data:image/${ext};base64,${readFileSync(join('detail', 'assets', f)).toString('base64')}`
}
const I = Object.fromEntries(['logo-gold.png', 'po-real-stage.jpg', 'po-deco.jpg', 'po-oil.jpg',
  'po-engraving.jpg', 'po-ink.jpg', 'po-kids.jpg', 'po-bright.jpg', 'po-real-keys.jpg',
  'doc-cover.jpg', 'doc-inner.jpg', 'doc-cue.jpg', 'doc-mc.jpg', 'doc-cert.jpg',
  'doc-ticket.jpg', 'doc-invite-card.jpg', 'invite.jpg', 'stage.jpg', 'video.jpg',
  's1.jpg', 's2.jpg', 's3.jpg', 'th-1.jpg', 'th-2.jpg', 'th-3.jpg',
].map((f) => [
  // 확장자를 **먼저** 떼야 한다. 안 떼고 낙타등으로 바꾸면 'Jpg' 가 붙어
  // 이름이 어긋나고, src 가 undefined 가 되어 사진이 통째로 빠진다
  f.replace(/\.(jpg|png)$/, '').replace(/-(\w)/g, (_, c) => c.toUpperCase()),
  b64(f),
]))

const CSS = `
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:${W}px;height:${H}px}
  body{font-family:'Noto Sans KR',sans-serif;-webkit-font-smoothing:antialiased;
    color:#2B2620;overflow:hidden;background:#F2E9D8}
  .serif{font-family:'Noto Serif KR',serif;font-weight:900}
  .card{position:absolute;inset:0;display:flex;flex-direction:column;
    padding:78px 72px 68px}
  .card.dark{background:#141118;color:#F4EDE0}
  .card.deep{background:#1E2A56;color:#EFE7D6}
  .eyebrow{font-size:28px;font-weight:700;letter-spacing:.22em;color:#A07C2C}
  .dark .eyebrow,.deep .eyebrow{color:#C8A24A}
  h1{font-family:'Noto Serif KR',serif;font-weight:900;font-size:82px;line-height:1.24;
    letter-spacing:-.03em;margin-top:22px}
  h2{font-family:'Noto Serif KR',serif;font-weight:900;font-size:64px;line-height:1.28;
    letter-spacing:-.03em;margin-top:18px}
  .lead{font-size:34px;line-height:1.62;color:#5A544B;margin-top:26px;letter-spacing:-.02em}
  .dark .lead,.deep .lead{color:#B9AF9C}
  em{font-style:normal;color:#8B1E2E}
  .dark em,.deep em{color:#D9B95C}
  .foot{margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end;
    font-size:25px;font-weight:700;color:#A08E70;letter-spacing:-.01em}
  .dark .foot,.deep .foot{color:#7E7361}
  .foot b{color:#8B1E2E}
  .dark .foot b,.deep .foot b{color:#C8A24A}
  .num{font-family:'Noto Serif KR',serif;font-weight:900;font-size:30px}
  .rule{width:76px;height:5px;background:#A07C2C;border-radius:3px}
  .dark .rule,.deep .rule{background:#C8A24A}
`

/* 한 장의 틀 */
const card = (cls, inner, page, extra = '') => `
<style>${CSS}${extra}</style>
<div class="card ${cls}">
  ${inner}
  <div class="foot"><span><b>연주회 매니저</b> · 아첼쌤</span><span class="num">${page}</span></div>
</div>`

const CARDS = []
const add = (name, cls, inner, page, extra) => CARDS.push([name, card(cls, inner, page, extra)])

/* ── 01 표지 ─────────────────────────────────────────────── */
add('01-표지', 'dark', `
  <div class="rule"></div>
  <h1 style="font-size:88px;margin-top:34px">연주회 한 번에<br>원장님은 며칠<br>밤을 새우십니다</h1>
  <p class="lead" style="font-size:36px">순서표부터 상장까지, 그 많은 종이를<br>왜 늘 원장님 혼자 만드실까요.</p>
  <div class="hero">
    <img src="${I.poRealStage}" style="transform:rotate(-7deg) translateY(8px)">
    <img src="${I.poDeco}" style="transform:rotate(-1deg);z-index:3;width:300px">
    <img src="${I.poOil}" style="transform:rotate(6deg) translateY(8px)">
  </div>
  <p style="font-size:30px;font-weight:700;color:#C8A24A;margin-top:26px">→ 옆으로 넘겨 보세요</p>
`, '01', `
  .hero{margin-top:auto;display:flex;justify-content:center;align-items:center;gap:-20px;padding-top:30px}
  .hero img{width:262px;border-radius:8px;box-shadow:0 22px 50px rgba(0,0,0,.6);margin:0 -18px}
`)

/* ── 02 고충 · 만드시는 것 ───────────────────────────────── */
add('02-만드시는것', '', `
  <div class="eyebrow">원장님의 하루</div>
  <h2>연주회 한 번에<br>원장님이 만드시는 것</h2>
  <div class="chips">
    ${['연주 순서표', '사회자 대본', '포스터', '프로그램 책자', '순서지', '입장권',
       '좌석 배치도', '좌석 이름표', '상장', '학부모 안내문', '학생 준비 안내문',
       '초대장', '리허설 시간표', '당일 진행표', '무대 스크린 슬라이드', '감사 안내문',
       '접수 확인표', '예산표'].map((t) => `<span>${t}</span>`).join('')}
  </div>
  <p class="lead" style="margin-top:48px;font-size:39px;line-height:1.55">
    <em>열여덟 가지.</em><br>이걸 전부, 한글과 파워포인트로,<br>연주회 때마다 처음부터 다시 만드십니다.</p>
`, '02', `
  .chips{display:flex;flex-wrap:wrap;gap:18px;margin-top:48px}
  .chips span{background:#fff;border:2px solid rgba(160,124,44,.3);border-radius:99px;
    padding:21px 30px;font-size:33px;font-weight:700;color:#2B2620}
`)

/* ── 03 진짜 힘든 것 ─────────────────────────────────────── */
add('03-진짜힘든것', '', `
  <div class="eyebrow">그런데 더 힘든 건</div>
  <h2>만드는 게 아니라<br><em>다시 만드는 것</em>입니다</h2>
  <div class="pains">
    <div><b>순서 하나가 바뀌면</b><span>순서표 · 대본 · 프로그램 · 좌석표를 전부 다시 고쳐야 합니다</span></div>
    <div><b>아이가 한 명 빠지면</b><span>인쇄까지 끝낸 종이가 그대로 못 쓰게 됩니다</span></div>
    <div><b>작년 파일은</b><span>어느 폴더에 뒀는지 기억나지 않습니다</span></div>
    <div><b>디자인이 안 되니</b><span>포스터는 외주를 맡기거나, 그냥 글자만 크게 씁니다</span></div>
  </div>
`, '03', `
  .pains{margin-top:44px;display:flex;flex-direction:column;gap:26px}
  .pains div{background:#fff;border-left:9px solid #8B1E2E;border-radius:0 18px 18px 0;
    padding:26px 30px}
  .pains b{display:block;font-size:36px;color:#8B1E2E;letter-spacing:-.02em}
  .pains span{display:block;font-size:30px;line-height:1.55;color:#5A544B;margin-top:8px;letter-spacing:-.02em}
`)

/* ── 04 개발 배경 ────────────────────────────────────────── */
add('04-그래서만들었습니다', 'deep', `
  <div class="eyebrow">아 첼 쌤</div>
  <h2 style="font-size:70px">그래서<br>만들었습니다</h2>
  <p class="lead" style="font-size:35px;color:#CFC5B0">
    피아노학원 원장님들을 오래 만나며 같은 말을 들었습니다.<br><br>
    「연주회는 하고 싶은데, 준비가 무서워요.」<br>
    「아이들 가르칠 시간에 포스터를 만들고 있어요.」<br><br>
    <em>가르치는 시간을 돌려드리는 것</em>이 이 프로그램의 목적입니다.
    원장님이 하실 일은 <em>아이를 고르고 곡을 정하는 것</em>까지,
    나머지 종이 일은 프로그램이 합니다.</p>
  <div class="sign">
    <img src="${I.logoGold}">
    <b>아첼쌤 · accelssam</b>
    <span>피아노학원 성장 노하우 · accelssam.com</span>
  </div>
`, '04', `
  .sign{margin-top:auto;padding-top:30px;text-align:center}
  .sign img{width:236px;display:block;margin:0 auto}
  .sign b{display:block;font-family:'Noto Serif KR',serif;font-weight:900;font-size:40px;
    color:#EFE7D6;margin-top:18px;letter-spacing:-.01em}
  .sign span{display:block;font-size:26px;color:#9C927E;margin-top:10px}
`)

/* ── 05 핵심 · 3분 ───────────────────────────────────────── */
add('05-3분', '', `
  <div class="eyebrow">달라지는 것</div>
  <h2>학생 명단 한 장이면<br>여기까지 <em>3분</em></h2>
  <div class="ba">
    <div class="b">
      <span class="tag">지금까지</span>
      <p>한글 열고 표 그리고<br>순서 짜고 시간 계산하고<br>포스터 만들고 인쇄하고…</p>
      <b>사흘</b>
    </div>
    <div class="arrow">→</div>
    <div class="a">
      <span class="tag">연주회 매니저</span>
      <p>엑셀 명단 붙여넣기<br>「자동으로 짜기」<br>「관객용 한 벌 인쇄」</p>
      <b>3분</b>
    </div>
  </div>
  <p class="lead" style="margin-top:46px;font-size:37px;line-height:1.55">순서를 바꾸시면
    <em>모든 인쇄물이 알아서 따라옵니다.</em><br>고치실 곳을 찾아다니지 않으셔도 됩니다.</p>
  <div class="also">
    <div><b>명단</b>엑셀 붙여넣기</div>
    <div><b>순서</b>자동 배치 · 시각 계산</div>
    <div><b>인쇄</b>테마 한 벌로 통일</div>
  </div>
`, '05', `
  .ba{display:flex;align-items:stretch;gap:18px;margin-top:44px}
  .ba>div{flex:1;border-radius:22px;padding:46px 28px;text-align:center}
  .ba .b{background:#EFE7D8;border:2px solid rgba(90,84,75,.2)}
  .ba .a{background:#1E2A56;color:#EFE7D6}
  .ba .arrow{flex:0 0 60px;display:flex;align-items:center;justify-content:center;
    font-size:56px;color:#A07C2C;font-weight:700}
  .tag{display:inline-block;font-size:28px;font-weight:700;padding:10px 22px;border-radius:99px;
    background:rgba(90,84,75,.14);color:#5A544B}
  .a .tag{background:rgba(217,185,92,.2);color:#D9B95C}
  .ba p{font-size:31px;line-height:1.65;margin-top:26px;color:#5A544B;letter-spacing:-.02em}
  .a p{color:#C3BAA6}
  .ba b{display:block;font-family:'Noto Serif KR',serif;font-weight:900;font-size:76px;margin-top:26px;color:#5A544B}
  .also{display:flex;gap:16px;margin-top:38px}
  .also div{flex:1;background:#fff;border:2px solid rgba(160,124,44,.26);border-radius:18px;
    padding:24px 16px;text-align:center;font-size:26px;color:#5A544B;letter-spacing:-.03em;line-height:1.4}
  .also b{display:block;font-family:'Noto Serif KR',serif;font-weight:900;font-size:36px;
    color:#1E2A56;margin-bottom:8px}
  .a b{color:#D9B95C}
`)

/* ── 06 명단 · 순서 ──────────────────────────────────────── */
add('06-명단과순서', '', `
  <div class="eyebrow">기능 01</div>
  <h2>순서를 <em>대신 짜 드립니다</em></h2>
  <div class="split">
    <ul class="pts">
      <li><b>엑셀 그대로 붙여넣기</b>빈 이름 · 이상한 곡명을 프로그램이 짚어 드립니다</li>
      <li><b>저학년 → 고학년</b>곡 길이와 형제자매까지 헤아려 자동으로</li>
      <li><b>연주 시각까지 자동</b>몇 시 몇 분에 누가 치는지 표로 나옵니다</li>
      <li><b>끌어서 자리 바꾸기</b>바꾸는 즉시 모든 인쇄물이 따라옵니다</li>
      <li><b>사회자 대본도 함께</b>곡 사전 70여 곡 — 작곡가와 소개말이 채워집니다</li>
    </ul>
    <div class="shot"><img src="${I.docInner}"><img src="${I.docMc}"></div>
  </div>
`, '06', `
  .split{display:flex;gap:34px;margin-top:38px;align-items:flex-start}
  .pts{flex:1;list-style:none}
  .pts li{margin-bottom:24px;font-size:28px;line-height:1.5;color:#5A544B;letter-spacing:-.02em;
    padding-left:34px;position:relative}
  .pts li::before{content:'';position:absolute;left:0;top:14px;width:16px;height:16px;
    border-radius:50%;background:#A07C2C}
  .pts b{display:block;font-size:32px;color:#2B2620;margin-bottom:5px}
  .shot{flex:0 0 300px;display:flex;flex-direction:column;gap:16px}
  .shot img{width:100%;border-radius:10px;box-shadow:0 12px 30px rgba(83,62,38,.22)}
`)

/* ── 07 테마 108종 ───────────────────────────────────────── */
add('07-테마108', '', `
  <div class="eyebrow">기능 02</div>
  <h2>테마 하나를 고르면<br><em>83종이 같은 옷</em>을 입습니다</h2>
  <div class="three">
    <figure><img src="${I.th1}"><figcaption>느와르 골드</figcaption></figure>
    <figure><img src="${I.th2}"><figcaption>클래식 네이비</figcaption></figure>
    <figure><img src="${I.th3}"><figcaption>체리 스프링</figcaption></figure>
  </div>
  <p class="lead" style="margin-top:38px;font-size:36px;line-height:1.55">같은 포스터가
    테마에 따라 이렇게 달라집니다. 색과 서체가 한 벌로 맞춰져 있어
    <em>디자인을 고르실 필요가 없습니다.</em></p>
  <div class="kinds">
    ${['정통 클래식', '갈라 (고급)', '계절 26종', '아이 · 파스텔 28종', '사진 중심', '미니멀']
      .map((t) => `<span>${t}</span>`).join('')}
  </div>
`, '07', `
  .three{display:flex;gap:22px;margin-top:40px}
  .three figure{flex:1;text-align:center}
  .three img{width:100%;border-radius:10px;box-shadow:0 14px 34px rgba(83,62,38,.26)}
  .three figcaption{margin-top:16px;font-size:29px;font-weight:700;color:#A07C2C}
  .kinds{display:flex;flex-wrap:wrap;gap:14px;margin-top:30px}
  .kinds span{background:#F8F3E7;border:2px solid rgba(160,124,44,.32);border-radius:99px;
    padding:16px 26px;font-size:29px;font-weight:700;color:#8B1E2E}
`)

/* ── 08 포스터 31종 ──────────────────────────────────────── */
add('08-포스터31', 'dark', `
  <div class="eyebrow">기능 03</div>
  <h2 style="font-size:66px">포스터만 <em>31종</em></h2>
  <p class="lead" style="margin-top:18px;font-size:31px">실사 사진 · 유화 · 수채 · 선화 · 동판화 · 아르데코 · 수묵 · 아이 그림<br>— 전부 프로그램이 실제로 뽑아 낸 것입니다.</p>
  <div class="grid5">
    <img src="${I.poRealStage}"><img src="${I.poOil}"><img src="${I.poEngraving}">
    <img src="${I.poInk}"><img src="${I.poDeco}"><img src="${I.poKids}">
    <img src="${I.poBright}"><img src="${I.poRealKeys}">
  </div>
  <p style="font-size:29px;font-weight:700;color:#C8A24A;margin-top:26px">
    잉크가 적게 드는 <em>밝은 판</em>도 함께 들어 있습니다</p>
`, '08', `
  .grid5{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:34px}
  .grid5 img{width:100%;border-radius:8px;box-shadow:0 10px 26px rgba(0,0,0,.55)}
`)

/* ── 09 인쇄물 83종 ──────────────────────────────────────── */
add('09-인쇄물83', '', `
  <div class="eyebrow">기능 04</div>
  <h2>연주회에 드는 종이,<br><em>83종이 한 번에</em></h2>
  <div class="grid6">
    <figure><img src="${I.docCover}"><figcaption>프로그램 표지</figcaption></figure>
    <figure><img src="${I.docCue}"><figcaption>당일 진행표</figcaption></figure>
    <figure><img src="${I.docMc}"><figcaption>사회자 대본</figcaption></figure>
    <figure><img src="${I.docTicket}"><figcaption>입장권 · 좌석권</figcaption></figure>
    <figure><img src="${I.docInviteCard}"><figcaption>초대장 (QR)</figcaption></figure>
    <figure><img src="${I.docCert}"><figcaption>상장</figcaption></figure>
  </div>
  <p class="lead" style="margin-top:26px;font-size:31px">
    「관객용 한 벌」을 누르시면 포스터 · 프로그램 · 순서지 · 입장권이 <em>한 번에</em> 나옵니다.
    종이가 몇 장 드는지 뽑기 전에 알려 드립니다.</p>
`, '09', `
  .grid6{display:grid;grid-template-columns:repeat(3,1fr);gap:20px 18px;margin-top:34px}
  .grid6 figure{text-align:center}
  .grid6 img{width:100%;height:250px;object-fit:cover;object-position:top;border-radius:8px;
    box-shadow:0 10px 26px rgba(83,62,38,.22)}
  .grid6 figcaption{margin-top:10px;font-size:26px;font-weight:700;color:#A07C2C}
`)

/* ── 10 초대장 · 참석 집계 ───────────────────────────────── */
add('10-초대장', '', `
  <div class="eyebrow">기능 05</div>
  <h2>초대장은 링크 하나,<br>참석은 <em>자동 집계</em></h2>
  <div class="split">
    <ul class="pts">
      <li><b>단톡방에 링크 하나</b>학부모는 로그인 없이 열고 참석을 누릅니다</li>
      <li><b>몇 가정 몇 명인지</b>자동으로 세어 드립니다</li>
      <li><b>그 인원으로 좌석표가</b>좌석 배치도가 그대로 그려집니다</li>
      <li><b>종이 초대장에는 QR</b>휴대폰으로 비추면 바로 열립니다</li>
      <li><b>인터넷이 필요한 건</b>이 초대장 링크 하나뿐입니다</li>
    </ul>
    <div class="phone"><img src="${I.invite}"></div>
  </div>
`, '10', `
  .split{display:flex;gap:34px;margin-top:38px;align-items:flex-start}
  .pts{flex:1;list-style:none}
  .pts li{margin-bottom:24px;font-size:28px;line-height:1.5;color:#5A544B;letter-spacing:-.02em;
    padding-left:34px;position:relative}
  .pts li::before{content:'';position:absolute;left:0;top:14px;width:16px;height:16px;
    border-radius:50%;background:#A07C2C}
  .pts b{display:block;font-size:32px;color:#2B2620;margin-bottom:5px}
  .phone{flex:0 0 348px}
  .phone img{width:100%;border-radius:16px;box-shadow:0 16px 40px rgba(83,62,38,.28)}
`)

/* ── 11 당일 · 무대 · 영상 ───────────────────────────────── */
add('11-당일진행', 'deep', `
  <div class="eyebrow">기능 06</div>
  <h2 style="font-size:58px;margin-top:12px">연주회 당일도<br>이 화면 하나로</h2>
  <div class="shots">
    <figure class="app"><img src="${I.s2}"><figcaption>당일 진행 화면</figcaption></figure>
    <div class="stack">
      <figure><img src="${I.stage}"><figcaption>무대 스크린</figcaption></figure>
      <figure><img src="${I.video}"><figcaption>감동영상</figcaption></figure>
    </div>
  </div>
  <ul class="flat">
    <li>지금 몇 번째인지, 다음이 누구인지 한 화면에</li>
    <li><b>태블릿으로 넘기면 무대 화면도 같이</b> 넘어갑니다</li>
    <li>출석 확인 · 갑작스러운 순서 변경 · 지연 시간 계산</li>
    <li>무대 슬라이드는 <b>파워포인트로도</b> 저장됩니다</li>
    <li>아이들 사진을 넣으면 <b>감동영상</b>이 만들어집니다</li>
  </ul>
`, '11', `
  .card{padding-top:62px;padding-bottom:54px}
  .shots{display:flex;gap:22px;margin-top:28px;align-items:flex-start}
  .shots .app{flex:0 0 330px;text-align:center}
  .shots .app img{width:100%;height:340px;object-fit:cover;object-position:top;
    border-radius:14px;box-shadow:0 16px 38px rgba(0,0,0,.5)}
  .stack{flex:1;display:flex;flex-direction:column;gap:16px}
  .shots figure{text-align:center}
  .shots .stack img{width:100%;height:218px;object-fit:cover;border-radius:10px;
    box-shadow:0 12px 30px rgba(0,0,0,.45)}
  .shots figcaption{margin-top:10px;font-size:25px;font-weight:700;color:#C8A24A}
  .flat{list-style:none;margin-top:34px}
  .flat li{font-size:30px;line-height:1.5;color:#CFC5B0;margin-bottom:19px;
    padding-left:34px;position:relative;letter-spacing:-.02em}
  .flat li::before{content:'';position:absolute;left:0;top:13px;width:14px;height:14px;
    border-radius:50%;background:#C8A24A}
  .flat b{color:#F4EDE0}
`)

/* ── 12 기능 한눈에 ──────────────────────────────────────── */
add('12-기능전체', '', `
  <div class="eyebrow">들어 있는 것 전부</div>
  <h2 style="font-size:52px;margin-top:12px">이만큼 들어 있습니다</h2>
  <div class="all">
    <div><b>인쇄물 83종</b>포스터 31종 · 프로그램 표지/속장 · A5 책자 · 큰 글씨 순서지 · 메모 칸 순서지 · 곡 해설판</div>
    <div><b>초대 · 홍보</b>초대장 카드(QR) · 학부모 안내문 · 학생 준비 안내문 · SNS 정사각 · 세로 스토리 · X배너 · 현수막 시안</div>
    <div><b>행사 당일</b>입장권 · 좌석권 · 좌석 이름표 · 좌석 배치도 · 안내 표지판 · 포토존 보드 · 무대 배치도 · 무대 뒤 순서 카드</div>
    <div><b>진행 문서</b>사회자 대본 · 당일 진행표 · 준비 체크리스트 · 리허설 시간표 · 시상 명단 · 상장 2종 · 감사 책갈피 · 접수 확인표 · 예산표</div>
    <div><b>화면 · 영상</b>무대 스크린 슬라이드(PPT 저장) · 감동영상 편집기(배경 10종) · 대기 화면 · 폐회 화면</div>
    <div><b>그 밖에</b>테마 108종 · 곡 사전 70여 곡 · 모바일 초대장 · 참석 집계 · 자동 저장 · 되돌리기 · 인쇄 미리보기 · 종이 장수 계산 · 프로그램 안 사용설명서</div>
    <div class="no"><b>들어 있지 않은 것</b>악보 · 반주 음원 · 배경 음악 — 저작권이 있어 학원에서 준비하십니다</div>
  </div>
`, '12', `
  .card{padding-top:64px;padding-bottom:56px}
  .all{margin-top:26px;display:flex;flex-direction:column;gap:12px}
  .all div{background:#fff;border-radius:14px;padding:16px 22px;
    font-size:25px;line-height:1.44;color:#5A544B;letter-spacing:-.03em}
  .all b{display:block;font-size:28px;color:#8B1E2E;margin-bottom:4px;letter-spacing:-.02em}
  .all .no{background:#FBF3F4;border:2px solid rgba(139,30,46,.22)}
  .all .no b{color:#8B1E2E}
`)

/* ── 13 안심 + CTA ───────────────────────────────────────── */
add('13-CTA', 'dark', `
  <div class="rule"></div>
  <h2 style="font-size:62px;margin-top:30px">아이들 정보는<br>학원 밖으로<br><em>나가지 않습니다</em></h2>
  <div class="safe">
    <div><b>인터넷 없이</b>설치해서 쓰는 프로그램입니다. 학원 인터넷이 끊겨도 열리고 인쇄됩니다</div>
    <div><b>서버에 안 올라갑니다</b>명단도 사진도 원장님 컴퓨터 안에만 있습니다</div>
    <div><b>내년엔 이름만 바꿔</b>올해 자료가 그대로 남습니다. 두 번째 해부터 진짜로 편합니다</div>
  </div>
  <div class="cta">
    <p>윈도우 · 맥 설치형 &nbsp;|&nbsp; 인증키 한 번이면 계속</p>
    <b>accelssam.com</b>
    <span>프로필 링크에서 받으실 수 있습니다</span>
  </div>
`, '13', `
  .safe{margin-top:36px;display:flex;flex-direction:column;gap:18px}
  .safe div{border-left:6px solid #C8A24A;padding:6px 0 6px 24px}
  .safe b{display:block;font-size:32px;color:#F4EDE0;margin-bottom:6px;letter-spacing:-.02em}
  .safe div{font-size:27px;line-height:1.5;color:#B9AF9C;letter-spacing:-.02em}
  .cta{margin-top:auto;padding-top:34px;text-align:center}
  .cta p{font-size:27px;font-weight:700;color:#B9AF9C}
  .cta b{display:block;font-family:'Noto Serif KR',serif;font-weight:900;
    font-size:60px;color:#D9B95C;margin-top:14px;letter-spacing:-.01em}
  .cta span{display:block;font-size:26px;color:#8E8676;margin-top:12px}
`)

/* ── 찍기 ────────────────────────────────────────────────── */
rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })

const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: SCALE })

// 한글 글꼴이 없으면 네모만 찍힌다 — 그 장이 인스타에 올라가는 것이 가장 나쁘다
{
  const p = await ctx.newPage()
  await p.setContent(`<span id=a style="font:900 100px 'Noto Serif KR',serif">연주회</span>
    <span id=b style="font:900 100px serif">연주회</span>`)
  await p.evaluate(() => document.fonts.ready)
  const [wa, wb] = await p.evaluate(() => ['a', 'b'].map((id) => document.getElementById(id).getBoundingClientRect().width))
  if (wa === wb) { console.error('한글 글꼴(Noto Serif KR)이 없습니다 — 글자가 네모로 찍힙니다.'); process.exit(1) }
  await p.close()
}

const problems = []
for (const [name, html] of CARDS) {
  const page = await ctx.newPage()
  await page.setContent(html, { waitUntil: 'load' })
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(250)

  // 넘치거나 너무 작은 글씨가 있으면 그 자리에서 잡는다
  const bad = await page.evaluate(() => {
    const out = []
    const c = document.querySelector('.card')
    if (c.scrollHeight > c.clientHeight + 1) out.push(`아래로 ${c.scrollHeight - c.clientHeight}px 넘침`)
    // 아래가 크게 비면 「덜 만든 장」으로 보인다. 발치의 위쪽 빈 자리를 잰다
    const foot = c.querySelector('.foot')
    const last = foot.previousElementSibling
    if (last) {
      const gap = Math.round(foot.getBoundingClientRect().top - last.getBoundingClientRect().bottom)
      if (gap > 190) out.push(`아래가 ${gap}px 빔`)
    }
    if (document.documentElement.scrollWidth > document.documentElement.clientWidth + 1) out.push('옆으로 넘침')
    // 사진이 한 장이라도 안 뜨면 그 장은 못 쓴다 — 인스타에 빈 칸이 올라간다
    for (const img of document.querySelectorAll('img')) {
      if (!img.getAttribute('src') || img.getAttribute('src') === 'undefined') out.push('사진 주소가 비었음')
      else if (!img.complete || img.naturalWidth === 0) out.push('사진이 안 뜸')
    }
    for (const el of document.querySelectorAll('p,li,span,b,div,figcaption')) {
      if (!el.textContent.trim() || el.children.length) continue
      const fs = parseFloat(getComputedStyle(el).fontSize)
      if (fs && fs < 25) out.push(`${fs}px 글씨: ${el.textContent.trim().slice(0, 12)}`)
    }
    return out
  })
  if (bad.length) problems.push(`${name} — ${bad.join(' / ')}`)

  const big = join(OUT, `_${name}.png`)
  await page.screenshot({ path: big, type: 'png' })
  const out = join(OUT, `연주회매니저-카드뉴스-${name}.jpg`)
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-i', big,
    '-vf', `scale=${W}:${H}:flags=lanczos`, '-q:v', '2', out])
  rmSync(big)
  console.log(`${out}${bad.length ? '   ⚠ ' + bad.join(' / ') : ''}`)
  await page.close()
}

await browser.close()
if (problems.length) {
  console.error(`\n고칠 것 ${problems.length}장`)
  for (const p of problems) console.error(`  · ${p}`)
  process.exit(1)
}
console.log(`\n${CARDS.length}장 · 1080×1350 · ${OUT}`)
