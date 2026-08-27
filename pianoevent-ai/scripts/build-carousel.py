"""
상품 캐러셀 이미지의 원본 HTML 을 만든다.

  python3 scripts/build-carousel.py     →  promo/carousel.html
  node scripts/carousel-shot.mjs        →  carousel/01.png … 14.png (1080×1080)

쇼핑몰 상품 갤러리에 그대로 올릴 수 있는 정사각 슬라이드다.
테마 색 견본과 곡 사전 곡 수는 실제 소스에서 뽑아 쓴다 — 숫자가 어긋나지 않게.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ── 실제 소스에서 숫자와 색을 가져온다 ─────────────────────────
themes_src = (ROOT / 'lib' / 'design' / 'themes.ts').read_text()
templates_src = (ROOT / 'lib' / 'design' / 'templates.ts').read_text()
catalog_src = (ROOT / 'lib' / 'program' / 'catalog.ts').read_text()

THEME_COUNT = len(re.findall(r"^    family: '", themes_src, re.M))
TEMPLATE_COUNT = len(re.findall(r"^    category: '", templates_src, re.M))
CATALOG_COUNT = len(re.findall(r"^  E\('", catalog_src, re.M))

CATEGORY_COUNT = {
    key: len(re.findall(rf"^    category: '{key}',$", templates_src, re.M))
    for key in ['poster', 'program', 'invite', 'stage', 'ops']
}

# 테마 견본 — id, 이름, paper/band/accent
theme_blocks = themes_src.split('\n  {\n')[1:]
THEMES = []
for block in theme_blocks:
    tid = re.search(r"id: '([^']+)'", block)
    name = re.search(r"name: '([^']+)'", block)
    paper = re.search(r"paper: '(#[0-9a-fA-F]{6})'", block)
    band = re.search(r"band: '(#[0-9a-fA-F]{6})'", block)
    accent = re.search(r"accent: '(#[0-9a-fA-F]{6})'", block)
    family = re.search(r"family: '([^']+)'", block)
    if tid and name and paper and band and accent and family:
        THEMES.append(
            dict(id=tid[1], name=name[1], paper=paper[1], band=band[1], accent=accent[1], family=family[1])
        )

FAMILY_LABEL = {
    'classic': '고급 · 클래식',
    'lovely': '사랑스러운',
    'season': '계절 · 시즌',
    'modern': '모던 · 편집',
    'kids': '아이들 · 활기',
}

assert THEME_COUNT == len(THEMES), f'테마 수가 맞지 않습니다 {THEME_COUNT} vs {len(THEMES)}'

CSS = """
:root{
  --cream:#F8F3E7; --cream2:#F2E9D8; --white:#fff;
  --ink:#2B2620; --ink2:#5A544B;
  --navy:#1E2A56; --navy-dk:#131C3D;
  --burgundy:#8B1E2E; --gold:#A07C2C; --gold-lt:#D9B95C; --gold-pale:#EAD9A8;
  --serif:'Nanum Myeongjo','Apple SD Gothic Neo',Batang,serif;
  --sans:'Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#666;font-family:var(--sans);word-break:keep-all;}
.slide{
  width:1080px;height:1080px;position:relative;overflow:hidden;
  background:var(--cream);color:var(--ink);
  padding:76px 76px 80px;display:flex;flex-direction:column;
  margin:0 auto 24px;
}
.slide.dark{background:var(--navy-dk);color:#F4EFE4;}
.slide.dark .eyebrow{color:var(--gold-lt);}
.slide.dark h2,.slide.dark .big{color:#fff;}
.slide.dark .lead{color:#C9C3B4;}
.slide.dark .card{background:rgba(255,255,255,.06);border-color:rgba(217,185,92,.35);}
.slide.dark .foot{color:#8E8878;border-color:rgba(255,255,255,.14);}

.eyebrow{font-size:20px;letter-spacing:.28em;font-weight:700;color:var(--gold);}
h2{font-family:var(--serif);font-size:56px;line-height:1.24;font-weight:800;color:var(--navy);margin-top:20px;letter-spacing:-.02em;}
h2 .hi{color:var(--burgundy);}
.lead{font-size:24px;line-height:1.7;color:var(--ink2);margin-top:20px;max-width:24em;}
.rule{width:84px;height:4px;background:var(--gold);margin-top:24px;border-radius:3px;}

.foot{
  margin-top:auto;padding-top:26px;border-top:1px solid rgba(43,38,32,.16);
  display:flex;justify-content:space-between;align-items:flex-end;
  font-size:19px;color:#8A8478;
}
.foot b{font-family:var(--serif);color:var(--navy);}
.slide.dark .foot b{color:var(--gold-lt);}
.pageno{font-size:17px;letter-spacing:.12em;}

.body{margin-top:32px;flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;}

/* 숫자 격자 */
.stats{display:grid;grid-template-columns:1fr 1fr;gap:22px;}
.stat{background:var(--white);border:1px solid rgba(160,124,44,.28);border-radius:18px;padding:30px 28px;}
.slide.dark .stat{background:rgba(255,255,255,.06);border-color:rgba(217,185,92,.34);}
.stat .v{font-family:var(--serif);font-size:64px;font-weight:800;color:var(--burgundy);line-height:1;}
.slide.dark .stat .v{color:var(--gold-lt);}
.stat .k{font-size:22px;color:var(--ink2);margin-top:12px;line-height:1.5;}
.slide.dark .stat .k{color:#C9C3B4;}

/* 목록 */
.list{display:flex;flex-direction:column;gap:16px;}
.item{display:flex;gap:18px;align-items:flex-start;font-size:25px;line-height:1.55;}
.item .mk{
  flex:0 0 auto;width:40px;height:40px;border-radius:50%;
  background:var(--gold-pale);color:var(--burgundy);
  display:grid;place-items:center;font-size:21px;font-weight:800;margin-top:4px;
}
.slide.dark .item .mk{background:rgba(217,185,92,.22);color:var(--gold-lt);}
.item .mk.x{background:#F3D9DC;color:var(--burgundy);}
.item b{font-weight:700;}

/* 칩 */
.chips{display:flex;flex-wrap:wrap;gap:12px;}
.chip{
  padding:10px 19px;border-radius:999px;background:var(--white);
  border:1px solid rgba(160,124,44,.32);font-size:21px;
}
.slide.dark .chip{background:rgba(255,255,255,.07);border-color:rgba(217,185,92,.3);color:#EDE7D8;}
.chip.on{background:var(--navy);color:#fff;border-color:var(--navy);font-weight:700;}

/* 연쇄 */
.chain{text-align:center;}
.seed{display:inline-block;padding:17px 40px;border-radius:999px;background:var(--navy);color:#fff;
  font-size:27px;font-weight:700;}
.arrow{font-size:30px;color:var(--gold);margin:14px 0 13px;}
.chain .chips{justify-content:center;}
.chain .chips .chip{font-size:20px;padding:10px 18px;}
.chain-note{margin-top:24px;font-size:23px;font-weight:700;color:var(--burgundy);}

/* 테마 색 견본 */
.swatches{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;}
.sw{border-radius:14px;overflow:hidden;border:1px solid rgba(43,38,32,.14);background:var(--white);}
.sw .bar{height:48px;display:flex;}
.sw .bar i{flex:1;display:block;}
.sw p{font-size:14px;padding:8px 6px;text-align:center;color:var(--ink2);line-height:1.3;}

/* 비교표 */
.cmp{width:100%;border-collapse:collapse;font-size:21px;}
.cmp th,.cmp td{padding:14px 12px;text-align:left;border-bottom:1px solid rgba(43,38,32,.14);}
.cmp thead th{font-size:20px;color:var(--ink2);background:rgba(160,124,44,.1);}
.cmp .ours{background:var(--navy);color:#fff;font-weight:700;}
.cmp tbody .ours{background:rgba(30,42,86,.08);color:var(--navy);font-weight:700;}
.cmp tbody th{font-weight:700;width:8.4em;}

/* 카드 */
.card{background:var(--white);border:1px solid rgba(160,124,44,.3);border-radius:18px;padding:26px 28px;}
.card .t{font-family:var(--serif);font-size:30px;font-weight:800;color:var(--navy);}
.card .d{font-size:22px;color:var(--ink2);margin-top:11px;line-height:1.6;}
.slide.dark .card .t{color:var(--gold-lt);}
.slide.dark .card .d{color:#C9C3B4;}

.before-after{display:grid;grid-template-columns:1fr auto 1fr;gap:22px;align-items:center;}
.ba{border-radius:18px;padding:28px 24px;text-align:center;}
.ba.old{background:rgba(139,30,46,.08);border:1px dashed rgba(139,30,46,.4);}
.ba.new{background:var(--navy);color:#fff;}
.ba .lbl{font-size:19px;letter-spacing:.14em;font-weight:700;opacity:.8;}
.ba .v{font-family:var(--serif);font-size:52px;font-weight:800;margin-top:12px;line-height:1.2;}
.ba.old .v{color:var(--burgundy);}
.ba .s{font-size:20px;margin-top:10px;opacity:.85;}
.ba-arrow{font-size:40px;color:var(--gold);}

.cta-box{background:var(--gold);color:#231A08;border-radius:18px;padding:24px 30px;text-align:center;
  font-size:28px;font-weight:800;font-family:var(--serif);}
"""


def slide(n, total, body, dark=False, eyebrow='', title='', lead=''):
    head = ''
    if eyebrow:
        head += f'<p class="eyebrow">{eyebrow}</p>'
    if title:
        head += f'<h2>{title}</h2>'
    if lead:
        head += f'<p class="lead">{lead}</p>'
    if title:
        head += '<div class="rule"></div>'
    return f'''
<section class="slide{' dark' if dark else ''}" id="s{n:02d}">
  {head}
  <div class="body">{body}</div>
  <div class="foot">
    <span><b>피아노 이벤트 솔루션</b> &nbsp;·&nbsp; accelssam.com</span>
    <span class="pageno">{n:02d} / {total:02d}</span>
  </div>
</section>'''


TOTAL = 14
S = []

# 01 표지 ────────────────────────────────────────────────────
S.append(slide(1, TOTAL, dark=True,
    eyebrow='PIANOEVENT · 피아노학원 연주회 올인원',
    title='연주회 준비에 쓰던 사흘,<br>이제 <span class="hi" style="color:#D9B95C">30분</span>이면 끝납니다',
    lead=f'학생 명단 하나만 넣으면 순서표부터 인쇄물 {TEMPLATE_COUNT}종까지 한 자리에서 만들어집니다.',
    body=f'''
    <div class="stats">
      <div class="stat"><p class="v">{CATALOG_COUNT}곡</p><p class="k">곡 사전<br>작곡가 · 시간 · 해설 자동</p></div>
      <div class="stat"><p class="v">{TEMPLATE_COUNT}종</p><p class="k">인쇄물 양식</p></div>
      <div class="stat"><p class="v">{THEME_COUNT}종</p><p class="k">디자인 테마</p></div>
      <div class="stat"><p class="v">0원</p><p class="k">디자인 외주비</p></div>
    </div>'''))

# 02 문제 ────────────────────────────────────────────────────
S.append(slide(2, TOTAL,
    eyebrow='연주회 시즌마다',
    title='이런 밤을<br>보내지 않으셨나요',
    body='''
    <div class="list">
      <div class="item"><span class="mk x">✕</span><span>엑셀로 순서를 짜다가 <b>학생 한 명이 바뀌면</b> 러닝타임을 처음부터 다시 계산</span></div>
      <div class="item"><span class="mk x">✕</span><span>곡 해설을 검색해 옮기고 학생 소개 멘트를 하나씩 쓰다 보면 <b>어느새 새벽</b></span></div>
      <div class="item"><span class="mk x">✕</span><span>포스터 · 순서지 · 입장권 · 상장을 <b>매번 새 파일</b>로 만들다 결국 외주</span></div>
      <div class="item"><span class="mk x">✕</span><span>참석 인원을 단톡방 답장으로 세다가 <b>좌석과 프로그램 부수</b>가 어긋남</span></div>
      <div class="item"><span class="mk x">✕</span><span>당일 아침 학생 30명 <b>리허설 시각</b>을 손으로 계산</span></div>
    </div>'''))

# 03 핵심 구조 ───────────────────────────────────────────────
S.append(slide(3, TOTAL, dark=True,
    eyebrow='이 프로그램의 구조',
    title='한 곳을 고치면<br>전부 따라 바뀝니다',
    body='''
    <div class="chain">
      <span class="seed">학생 명단 한 번 입력</span>
      <p class="arrow">▼</p>
      <div class="chips">
        <span class="chip">연주 순서</span><span class="chip">예상 시각</span><span class="chip">러닝타임</span>
        <span class="chip">곡 해설</span><span class="chip">사회자 멘트</span>
      </div>
      <p class="arrow">▼</p>
      <div class="chips">
        <span class="chip">포스터</span><span class="chip">표지</span><span class="chip">순서지</span>
        <span class="chip">입장권</span><span class="chip">초대장</span><span class="chip">SNS</span>
        <span class="chip">X배너</span><span class="chip">상장</span><span class="chip">이름표</span>
        <span class="chip">대기 순서판</span><span class="chip">포토존</span>
      </div>
      <p class="arrow">▼</p>
      <div class="chips">
        <span class="chip">리허설 소집</span><span class="chip">조별 문자</span><span class="chip">좌석 배치도</span>
        <span class="chip">진행표</span><span class="chip">참가비</span><span class="chip">안내문</span>
      </div>
      <p class="chain-note" style="color:#D9B95C">순서 하나를 바꾸면 — 위의 40종이 동시에 다시 만들어집니다</p>
    </div>'''))

# 04 곡 사전 ─────────────────────────────────────────────────
S.append(slide(4, TOTAL,
    eyebrow=f'기능 01 · 곡 사전 {CATALOG_COUNT}곡',
    title='곡 제목만 치면<br>나머지가 <span class="hi">따라옵니다</span>',
    body=f'''
    <div class="before-after">
      <div class="ba old">
        <p class="lbl">지금까지</p>
        <p class="v">직접 검색</p>
        <p class="s">작곡가 찾고<br>연주시간 재고<br>해설 밤새 쓰고</p>
      </div>
      <p class="ba-arrow">→</p>
      <div class="ba new">
        <p class="lbl" style="color:#D9B95C">이제</p>
        <p class="v" style="color:#fff">엘리제를 위하여</p>
        <p class="s">여섯 글자만 적으면<br><b>베토벤 · 중급 · 3분 30초</b><br>+ 곡 해설까지</p>
      </div>
    </div>
    <p class="lead" style="margin-top:44px">
      부르크뮐러 · 바흐 · 쇼팽부터 <b>히사이시 조 · 겨울왕국 · 캐리비안의 해적</b>까지,
      학원 연주회에 실제로 오르는 {CATALOG_COUNT}곡. 원장님이 적으신 값은 절대 덮어쓰지 않습니다.
    </p>'''))

# 05 순서 배치 ───────────────────────────────────────────────
S.append(slide(5, TOTAL,
    eyebrow='기능 02 · 연주 순서',
    title='흐름과 시각을<br>동시에 계산합니다',
    body='''
    <div class="chips" style="margin-bottom:38px">
      <span class="chip on">오프닝</span><span class="chip">→</span>
      <span class="chip on">기초 · 초급</span><span class="chip">→</span>
      <span class="chip on">중급</span><span class="chip">→</span>
      <span class="chip on">듀엣 · 앙상블</span><span class="chip">→</span>
      <span class="chip on">피날레</span>
    </div>
    <div class="list">
      <div class="item"><span class="mk">✓</span><span>곡 사이 <b>전환 시간</b>과 중간 휴식까지 넣어 <b>몇 시에 끝나는지</b> 알려 줍니다</span></div>
      <div class="item"><span class="mk">✓</span><span>마음에 안 드는 곳은 <b>▲▼ 버튼</b>으로 직접 옮깁니다 — 마우스로 끌 줄 몰라도 됩니다</span></div>
      <div class="item"><span class="mk">✓</span><span>옮기면 <b>연주 시각과 인쇄물 40종이 함께</b> 바뀝니다. 멘트는 그대로 남습니다</span></div>
    </div>'''))

# 06 사회자 대본 ─────────────────────────────────────────────
S.append(slide(6, TOTAL, dark=True,
    eyebrow='기능 03 · 사회자 대본',
    title='곡마다 멘트가<br>이미 쓰여 있습니다',
    body='''
    <div class="card">
      <p class="t">오프닝</p>
      <p class="d">안녕하십니까. 하모니 피아노학원 제12회 정기 연주회에 오신 학부모님과 내빈 여러분,
      진심으로 환영합니다. 오늘 무대에는 모두 12명의 연주자가 오르며, 약 43분 동안 함께합니다.</p>
    </div>
    <div class="card" style="margin-top:18px">
      <p class="t">1. 오수아 · 인벤션 1번</p>
      <p class="d">오늘 연주회의 문을 여는 첫 무대입니다. 연주곡은 바흐의 「인벤션 1번」입니다.
      두 개의 선율이 각자 걸어가면서도 하나의 음악이 되는, 바흐의 대화 같은 곡입니다.</p>
    </div>
    <p class="lead" style="margin-top:24px;color:#C9C3B4;max-width:none">
      곡 · 작곡가 · 학생 메모를 엮어 <b style="color:#fff">전원분이 한 번에</b>.
      무대 옆은 어두우니 <b style="color:#fff">큰 글씨로 인쇄</b>됩니다.</p>'''))

# 07 인쇄물 ─────────────────────────────────────────────────
S.append(slide(7, TOTAL,
    eyebrow=f'기능 04 · 인쇄물 {TEMPLATE_COUNT}종',
    title='포스터 한 장으로<br>끝나지 않습니다',
    body=f'''
    <div class="stats" style="grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:34px">
      <div class="stat" style="padding:22px 14px;text-align:center"><p class="v" style="font-size:44px">{CATEGORY_COUNT['poster']}</p><p class="k" style="font-size:18px">포스터</p></div>
      <div class="stat" style="padding:22px 14px;text-align:center"><p class="v" style="font-size:44px">{CATEGORY_COUNT['program']}</p><p class="k" style="font-size:18px">프로그램</p></div>
      <div class="stat" style="padding:22px 14px;text-align:center"><p class="v" style="font-size:44px">{CATEGORY_COUNT['invite']}</p><p class="k" style="font-size:18px">초대 · 홍보</p></div>
      <div class="stat" style="padding:22px 14px;text-align:center"><p class="v" style="font-size:44px">{CATEGORY_COUNT['stage']}</p><p class="k" style="font-size:18px">행사 당일</p></div>
      <div class="stat" style="padding:22px 14px;text-align:center"><p class="v" style="font-size:44px">{CATEGORY_COUNT['ops']}</p><p class="k" style="font-size:18px">진행 문서</p></div>
    </div>
    <div class="chips">
      <span class="chip">클래식 포스터</span><span class="chip">전면 사진 포스터</span><span class="chip">타이포 포스터</span>
      <span class="chip">프로그램 표지</span><span class="chip">곡 해설 순서지</span><span class="chip">3단 접지</span>
      <span class="chip">입장권 3매</span><span class="chip">초대장 카드</span><span class="chip">SNS 스토리</span>
      <span class="chip">X배너 시안</span><span class="chip">참가 상장</span><span class="chip">좌석 이름표</span>
      <span class="chip">좌석 배치도</span><span class="chip">대기 순서판</span><span class="chip">포토존 보드</span>
      <span class="chip">시상 명단</span><span class="chip">사회자 대본</span><span class="chip">리허설 시간표</span>
      <span class="chip">접수 확인표</span><span class="chip">예산 · 정산표</span><span class="chip">학부모 안내문</span>
      <span class="chip">학생 준비 안내문</span><span class="chip">당일 진행표</span><span class="chip">체크리스트</span>
      <span class="chip">무대 배치도</span><span class="chip">가로 현수막</span><span class="chip">안내 표지판</span>
      <span class="chip">연습 기록표</span><span class="chip">연주자 소개 카드</span><span class="chip">응원 메시지 카드</span>
      <span class="chip">감사장</span><span class="chip">종료 후 안내문</span>
    </div>
    <p class="lead" style="margin-top:24px;max-width:none">인쇄 · PDF 저장 모두 원장님 손에서.</p>'''))

# 08 테마 ───────────────────────────────────────────────────
sw_html = []
order = ['classic', 'lovely', 'season', 'modern', 'kids']
picked = []
for fam in order:
    picked += [t for t in THEMES if t['family'] == fam][:4]
for t in picked[:15]:
    sw_html.append(
        f'<div class="sw"><div class="bar">'
        f'<i style="background:{t["paper"]}"></i><i style="background:{t["band"]}"></i><i style="background:{t["accent"]}"></i>'
        f'</div><p>{t["name"]}</p></div>'
    )
S.append(slide(8, TOTAL,
    eyebrow=f'기능 05 · 디자인 테마 {THEME_COUNT}종',
    title='학원 분위기에 맞는<br>한 벌을 고르세요',
    body=f'''
    <div class="chips" style="margin-bottom:26px">
      {''.join(f'<span class="chip">{FAMILY_LABEL[f]} {len([t for t in THEMES if t["family"] == f])}</span>' for f in order)}
    </div>
    <div class="swatches">{''.join(sw_html)}</div>
    <p class="lead" style="margin-top:24px;max-width:none">
      하나를 고르면 <b>{TEMPLATE_COUNT}종 전부가 같은 색과 서체</b>를 입습니다.
    </p>'''))

# 09 초대장 ─────────────────────────────────────────────────
S.append(slide(9, TOTAL,
    eyebrow='기능 06 · 모바일 초대장',
    title='링크 하나로<br>참석 인원이 쌓입니다',
    body='''
    <div class="before-after">
      <div class="ba old">
        <p class="lbl">지금까지</p>
        <p class="v">답장 세기</p>
        <p class="s">단톡방 100개 답장을<br>손으로 세다가<br>좌석이 어긋남</p>
      </div>
      <p class="ba-arrow">→</p>
      <div class="ba new">
        <p class="lbl" style="color:#D9B95C">이제</p>
        <p class="v" style="color:#fff">저절로 집계</p>
        <p class="s">가정 수 · 총원<br>응원 메시지까지<br>모여서 좌석으로</p>
      </div>
    </div>
    <div class="list" style="margin-top:44px">
      <div class="item"><span class="mk">✓</span><span>학부모는 <b>링크를 눌러 이름과 인원만</b> 고르면 끝 — 앱 설치 없음</span></div>
      <div class="item"><span class="mk">✓</span><span>모인 인원이 그대로 <b>좌석 배치도와 프로그램 부수</b>로 넘어갑니다</span></div>
    </div>'''))

# 10 운영 계산 ───────────────────────────────────────────────
S.append(slide(10, TOTAL, dark=True,
    eyebrow='기능 07 · 원장님이 손으로 하던 계산',
    title='순서표가 나온 뒤에도<br>일은 남습니다',
    body='''
    <div class="card">
      <p class="t">리허설 조별 소집</p>
      <p class="d">5명씩 묶어 <b>조별 도착 시각</b>을 계산하고 조마다 보낼 <b>문자까지</b> 만듭니다.
      문자 30통이 6통이 됩니다.</p>
    </div>
    <div class="card" style="margin-top:20px">
      <p class="t">참가비 역산</p>
      <p class="d">항목 10가지 예산에서 <b>1인당 원가와 권장 참가비</b>를 역산하고,
      <b>안내 문구</b>까지 만듭니다.</p>
    </div>
    <div class="card" style="margin-top:20px">
      <p class="t">좌석 배치</p>
      <p class="d">가족은 붙여 앉히고 앞 두 줄은 연주자석으로 비웁니다.
      <b>&ldquo;3열 4~6번&rdquo;</b>처럼 그대로 보낼 수 있는 표기로 나옵니다.</p>
    </div>'''))

# 11 점검 ───────────────────────────────────────────────────
S.append(slide(11, TOTAL,
    eyebrow='기능 08 · 순서표 정밀 점검',
    title='당일 전화를 부르는 것들을<br><span class="hi">미리 잡습니다</span>',
    body='''
    <div class="list">
      <div class="item"><span class="mk">!</span><span>같은 곡을 두 명이 칩니다 <b>— 연탄곡은 빼고</b></span></div>
      <div class="item"><span class="mk">!</span><span>형제자매로 보이는 학생이 <b>멀리 떨어져</b> 학부모가 두 번 와야 합니다</span></div>
      <div class="item"><span class="mk">!</span><span>제일 어린 아이가 <b>맨 뒤</b>라 한 시간을 앉아 기다립니다</span></div>
      <div class="item"><span class="mk">!</span><span>같은 작곡가가 <b>세 곡 연속</b>입니다</span></div>
      <div class="item"><span class="mk">!</span><span><b>휴식 없이 70분</b>을 넘습니다 — 유아 동반 학부모가 나갈 수 없습니다</span></div>
      <div class="item"><span class="mk">!</span><span>사회자 <b>멘트가 빈 순서</b>가 있습니다</span></div>
    </div>
    <p class="lead" style="margin-top:36px">
      <b>반드시 확인 / 확인 권장 / 참고</b> 세 등급으로, <b>고치는 법 한 줄</b>과 함께 나옵니다.
    </p>'''))

# 12 이미지 보관함 ───────────────────────────────────────────
S.append(slide(12, TOTAL,
    eyebrow='기능 09 · 이미지 보관함',
    title='사진을 끌어다 놓으면<br>전부에 들어갑니다',
    body='''
    <div class="chain">
      <span class="seed">로고 · 학원 상징 · 사진을 끌어다 놓기</span>
      <p class="arrow">▼</p>
      <div class="chips">
        <span class="chip on">휴대폰 사진 5MB도 인쇄 크기로 자동 축소</span>
      </div>
      <p class="arrow">▼</p>
      <div class="chips">
        <span class="chip">포스터</span><span class="chip">프로그램 표지</span><span class="chip">초대장</span>
        <span class="chip">홍보물</span><span class="chip">행사 당일</span><span class="chip">진행 문서</span>
      </div>
      <p class="chain-note">테마마다 동그랗게 잘리거나 금테가 붙고, 아치형으로 잘립니다 — 모양은 알아서</p>
    </div>
    <p class="lead" style="margin-top:34px;max-width:none">
      포스터엔 단체사진, 표지엔 학원 전경처럼 <b>인쇄물마다 다르게</b> 쓸 수도 있습니다.
      사진 주소를 다시 찾을 일이 없습니다.
    </p>'''))

# 13 인터넷·AI 없이도 ────────────────────────────────────────
S.append(slide(13, TOTAL, dark=True,
    eyebrow='가장 많이 받는 질문',
    title='AI 키도 인터넷도<br><span class="hi" style="color:#D9B95C">필요 없습니다</span>',
    body='''
    <div class="card">
      <p class="t">이 컴퓨터 안에서 전부 만들어집니다</p>
      <p class="d">순서 배치 · 러닝타임 · 곡 사전 · 사회자 대본 · 순서표 점검 · 인쇄물 40종 ·
      리허설 · 참가비 · 좌석 · 안내 문자 — <b>전부 프로그램에 내장</b>돼 있습니다.
      별도 가입도, 월 구독도, API 키도 없습니다.</p>
    </div>
    <div class="list" style="margin-top:34px">
      <div class="item"><span class="mk">✓</span><span><b>AI 키를 넣으면</b> 사회자 멘트 표현이 조금 더 다양해질 뿐입니다</span></div>
      <div class="item"><span class="mk">✓</span><span>입력하신 <b>학생 정보는 이 컴퓨터에만</b> 저장됩니다</span></div>
      <div class="item"><span class="mk">✓</span><span>인터넷이 필요한 건 <b>학부모가 초대장을 여는 것</b>뿐입니다</span></div>
    </div>
    <p class="lead" style="margin-top:24px;color:#C9C3B4;max-width:none">
      설정 화면에 <b style="color:#fff">지금 이 컴퓨터에서 되는 것</b>이 그대로 표시됩니다.
    </p>'''))

# 14 비교 + CTA ──────────────────────────────────────────────
S.append(slide(14, TOTAL,
    eyebrow='왜 이것이어야 하는가',
    title='디자인 도구도 관리 프로그램도<br>연주회를 알지는 못합니다',
    body='''
    <table class="cmp">
      <thead>
        <tr><th></th><th>한글 · 엑셀</th><th>캔바</th><th>외주</th><th class="ours">피아노 이벤트</th></tr>
      </thead>
      <tbody>
        <tr><th>학생 이름 입력</th><td>양식마다 반복</td><td>양식마다 반복</td><td>파일 전달</td><td class="ours">한 번 → 40종</td></tr>
        <tr><th>순서가 바뀌면</th><td>전부 재계산</td><td>모든 장 수정</td><td>다시 연락 · 추가비</td><td class="ours">40종 즉시 변경</td></tr>
        <tr><th>곡 정보</th><td>직접 검색</td><td>직접 검색</td><td>직접 전달</td><td class="ours">곡 사전 자동</td></tr>
        <tr><th>리허설 · 좌석</th><td>손 계산</td><td>없음</td><td>없음</td><td class="ours">자동</td></tr>
        <tr><th>비용</th><td>시간 15~25h</td><td>월 구독</td><td>1장 5~15만원</td><td class="ours">연 1회 · 무제한</td></tr>
      </tbody>
    </table>
    <div class="cta-box" style="margin-top:30px">
      올해 연주회는 준비가 아니라 무대에 집중하세요
    </div>'''))

html = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>피아노 이벤트 솔루션 · 상품 캐러셀</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700;800&family=Noto+Sans+KR:wght@400;500;700;800&display=swap">
<style>{CSS}</style></head><body>
{''.join(S)}
</body></html>'''

out = ROOT / 'promo' / 'carousel.html'
out.write_text(html)
print(f'written {out} · {len(S)}장 · 테마 {THEME_COUNT} · 양식 {TEMPLATE_COUNT} · 곡 {CATALOG_COUNT}')
