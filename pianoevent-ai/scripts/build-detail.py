#!/usr/bin/env python3
"""
상세페이지를 만든다 — 아첼쌤 상세페이지 규칙(스킬)의 template.html 에 내용만 갈아 끼운다.

    python3 scripts/build-detail.py

나오는 것: web/download/recital-manager-detail.html (사진까지 전부 담긴 파일 하나)

사진을 파일 안에 담는 이유 — 올릴 파일이 하나면 빠뜨릴 자리가 없다.
사진 원본은 detail/assets/ 에 두고, `node scripts/_gallery.mjs` 로 다시 찍을 수 있다.
"""
import base64, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'detail' / 'assets'
TPL = pathlib.Path(
    '/root/.claude/skills/synced/a5ef04ec-abc0-4086-922c-8a6bbd97c4e8_4bfbb704-11e5-4e2a-ae5d-c2faf05bc59c'
    '/accelssam-detail-page/template.html'
)
OUT = ROOT / 'web' / 'download' / 'recital-manager-detail.html'

if not TPL.exists():
    print('상세페이지 서식을 찾지 못했습니다:', TPL)
    sys.exit(1)


def data(name: str) -> str:
    at = ASSETS / name
    mime = 'image/png' if name.endswith('.png') else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(at.read_bytes()).decode()


IMG = {n.stem.replace('-', '_'): data(n.name) for n in sorted(ASSETS.iterdir()) if n.is_file()}

EXTRA_CSS = """
  /* ── 이 상품에만 쓰는 것 ─────────────
     프로그램(소프트웨어) 상품이라 강의 상세페이지에 없던 것이 더 필요하다 —
     **실제로 뽑히는 종이**를 보여 주는 자리, 화면 미리보기, 준비 일정표.
     색과 글자는 위 규칙을 그대로 쓴다. */
  .profile-photo.mark{padding:12%;background:transparent;}

  .gal{display:grid;gap:clamp(.9rem,2.2vw,1.5rem);margin-top:clamp(1.6rem,3.5vw,2.4rem);
    grid-template-columns:repeat(auto-fit,minmax(min(100%,168px),1fr));}
  .gal.two{grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));}
  .gal figure{margin:0;}
  .gal img{display:block;width:100%;height:auto;border-radius:12px;background:#fff;
    box-shadow:0 10px 30px rgba(52,38,15,.15);}
  .gal figcaption{margin-top:.6em;font-size:clamp(.92rem,.88rem + .2vw,1rem);
    color:var(--ink-soft);text-align:center;}
  .gal figcaption b{display:block;color:var(--ink);font-weight:700;margin-bottom:.1em;}
  .gal-note{margin-top:clamp(1.4rem,3vw,2rem);font-size:var(--fs-body);color:var(--ink-soft);
    text-align:center;}
  .gal-note b{color:var(--burgundy);}

  .shot-grid{display:grid;gap:clamp(1rem,2.4vw,1.6rem);margin-top:clamp(1.6rem,3.5vw,2.4rem);
    grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));}
  .shot{background:var(--white);border-radius:20px;overflow:hidden;
    box-shadow:0 6px 24px rgba(83,62,38,.08);border:1px solid rgba(160,124,44,.14);}
  .shot img{display:block;width:100%;height:auto;}
  .shot p{font-size:clamp(.92rem,.88rem + .25vw,1rem);color:var(--ink-soft);
    padding:.95em clamp(.9rem,2vw,1.3rem) 1.15em;}
  .shot p b{color:var(--ink);font-weight:700;}

  .steps{margin-top:clamp(1.8rem,4vw,2.8rem);display:flex;flex-direction:column;
    gap:clamp(.9rem,2vw,1.3rem);}
  .step{display:flex;gap:clamp(.9rem,2vw,1.4rem);align-items:flex-start;
    background:var(--white);border-radius:20px;padding:clamp(1.1rem,2.6vw,1.7rem);
    box-shadow:0 6px 24px rgba(83,62,38,.06);border:1px solid rgba(160,124,44,.12);}
  .step .when{flex:0 0 auto;min-width:5.4em;text-align:center;
    font-family:'Noto Serif KR',serif;font-weight:900;color:var(--burgundy);
    font-size:clamp(1rem,.95rem + .35vw,1.2rem);line-height:1.3;
    border-right:1px solid rgba(160,124,44,.22);padding-right:clamp(.7rem,1.6vw,1.1rem);}
  .step .when small{display:block;font-family:'Noto Sans KR',sans-serif;font-weight:500;
    color:var(--gold);font-size:.72em;letter-spacing:.06em;margin-top:.2em;}
  .step .what{flex:1 1 auto;}
  .step .what b{display:block;font-size:var(--fs-card-t);color:var(--ink);margin-bottom:.35em;}
  .step .what span{display:block;font-size:var(--fs-body);color:var(--ink-soft);}
  .step .out{display:inline-block;margin-top:.6em;padding:.35em .8em;border-radius:999px;
    background:var(--cream);color:var(--gold);font-size:.88rem;font-weight:700;
    border:1px solid rgba(160,124,44,.28);}
  @media (max-width:520px){
    .step{flex-direction:column;gap:.7rem;}
    .step .when{text-align:left;border-right:0;border-bottom:1px solid rgba(160,124,44,.22);
      padding-right:0;padding-bottom:.5rem;min-width:0;}
    .step .when small{display:inline;margin-left:.6em;}
  }

  .spec{margin-top:clamp(1.6rem,3.5vw,2.4rem);width:100%;border-collapse:collapse;
    background:var(--white);border-radius:20px;overflow:hidden;
    box-shadow:0 6px 24px rgba(83,62,38,.06);}
  .spec th,.spec td{padding:clamp(.8rem,2vw,1.15rem) clamp(.9rem,2.2vw,1.4rem);
    font-size:var(--fs-body);text-align:left;border-bottom:1px solid rgba(160,124,44,.14);}
  .spec th{width:38%;color:var(--gold);font-weight:700;background:rgba(242,233,216,.5);white-space:nowrap;}
  .spec td{color:var(--ink-soft);}
  .spec tr:last-child th,.spec tr:last-child td{border-bottom:0;}
  @media (max-width:520px){
    .spec th,.spec td{display:block;width:100%;}
    .spec th{border-bottom:0;padding-bottom:.2rem;}
  }

  .count{display:grid;gap:clamp(.8rem,2vw,1.2rem);margin-top:clamp(1.6rem,3.5vw,2.2rem);
    grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));}
  .count div{background:var(--white);border-radius:18px;padding:clamp(1rem,2.4vw,1.4rem);
    text-align:center;border:1px solid rgba(160,124,44,.14);
    box-shadow:0 6px 20px rgba(83,62,38,.05);}
  .count b{display:block;font-family:'Noto Serif KR',serif;font-weight:900;color:var(--burgundy);
    font-size:clamp(1.6rem,1.3rem + 1.4vw,2.3rem);line-height:1.2;}
  .count span{display:block;margin-top:.35em;font-size:clamp(.9rem,.86rem + .2vw,1rem);color:var(--ink-soft);}
"""

BODY = """<body>

<!-- ── HERO ─────────────────────────────────────────── -->
<section class="hero">
  <div class="inner">
    <div class="hero-top">
      <div class="hero-title">
        <p class="eyebrow reveal">PIANO ACADEMY &nbsp;·&nbsp; 연주회 매니저</p>
        <h1 class="reveal" style="--d:0.12s">연주회 준비에 밤새우는 원장님께,<br>이제 <span class="accent">딱 3분</span>이면 됩니다</h1>
      </div>
      <div class="profile-wrap reveal" style="--d:0.25s">
        <div class="profile-circle">
          <div class="ring">
            <img class="profile-photo mark" src="{logo_gold}" alt="연주회 매니저 로고">
          </div>
        </div>
        <p class="profile-caption"><span class="kr">아첼쌤</span> &middot; <span class="en">accelssam</span></p>
      </div>
    </div>
    <div class="card reveal" style="--d:0.35s">
      <p>연주회 한 번에 원장님이 만드시는 것 &mdash; <strong>연주 순서표, 사회자 대본, 포스터, 프로그램 책자, 입장권, 상장, 좌석 이름표, 학부모 안내문, 무대 스크린 슬라이드, 초대장&hellip;</strong></p>
      <p><strong class="accent">연주회 매니저</strong>는 이 전부를 <strong>학생 명단 한 장</strong>에서 만들어 냅니다. 명단을 붙여넣으시면 연주 순서와 시간이 잡히고, 인쇄물 83종이 같은 옷을 입고 한 번에 나옵니다.</p>
      <p>설치해서 쓰는 <strong>프로그램</strong>입니다. 인터넷이 없어도 열리고, <strong>아이 명단과 사진은 원장님 컴퓨터를 벗어나지 않습니다.</strong></p>
    </div>
    <div class="count">
      <div class="reveal"><b>83종</b><span>인쇄물</span></div>
      <div class="reveal" style="--d:.08s"><b>108종</b><span>테마</span></div>
      <div class="reveal" style="--d:.16s"><b>3분</b><span>명단 → 순서표</span></div>
      <div class="reveal" style="--d:.24s"><b>0원</b><span>인터넷 없이 작동</span></div>
    </div>
  </div>
</section>

<!-- ── 01 준비 현실 체크 ────────────────────────────── -->
<section class="reality">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">01 /</span> 연주회 준비 현실 체크</p>
    <h2 class="reveal" style="--d:0.1s">해마다 이맘때,<br>이렇게 하고 계시지 않으셨나요?</h2>
    <div class="pill-list">
      <div class="pill reveal"><span class="icon x">&#10005;</span><span>한글·엑셀로 순서표를 만들다가 아이 한 명이 빠져서 <strong>처음부터 다시</strong> 짠 밤</span></div>
      <div class="pill reveal" style="--d:0.12s"><span class="icon x">&#10005;</span><span>포스터는 결국 <strong>작년 것에 날짜만 고쳐서</strong> 붙이고, 매년 조금씩 부끄러운 마음</span></div>
      <div class="pill reveal" style="--d:0.24s"><span class="icon x">&#10005;</span><span>학부모 참석 인원을 <strong>단톡방에서 손으로 세다가</strong> 의자를 몇 개 놓을지 끝까지 몰랐던 당일</span></div>
    </div>
  </div>
</section>

<!-- ── 02 실제 결과물 ───────────────────────────────── -->
<section class="usp">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">02 /</span> 실제로 이렇게 나옵니다</p>
    <h2 class="reveal" style="--d:0.1s">아래는 <span class="accent">전부 프로그램이 만든 것</span>입니다</h2>
    <p class="sub reveal" style="--d:0.18s">따로 그리거나 편집한 것이 하나도 없습니다. 명단을 넣고 테마 하나를 고른 결과입니다.</p>

    <p class="eyebrow reveal" style="margin-top:2.4em">포스터 &mdash; 31종 가운데 넷</p>
    <div class="gal">
      <figure class="reveal"><img src="{poster_gala}" alt="무대 위 피아노 포스터"><figcaption><b>무대 위 피아노</b>정기 연주회</figcaption></figure>
      <figure class="reveal" style="--d:.08s"><img src="{poster_bright}" alt="흰 홀 포스터"><figcaption><b>흰 홀</b>잉크가 적게 듭니다</figcaption></figure>
      <figure class="reveal" style="--d:.16s"><img src="{poster_kids}" alt="아이 테마 포스터"><figcaption><b>꽃길이 되는 건반</b>유아·저학년</figcaption></figure>
      <figure class="reveal" style="--d:.24s"><img src="{poster_deco}" alt="아르데코 포스터"><figcaption><b>아르데코</b>예술회관 느낌</figcaption></figure>
    </div>

    <p class="eyebrow reveal" style="margin-top:2.6em">관객에게 나가는 것</p>
    <div class="gal">
      <figure class="reveal"><img src="{program_cover}" alt="프로그램 표지"><figcaption><b>프로그램 표지</b>같은 테마로 맞춰집니다</figcaption></figure>
      <figure class="reveal" style="--d:.08s"><img src="{program_inner}" alt="연주 순서지"><figcaption><b>연주 순서지</b>이름·곡·시각 자동</figcaption></figure>
      <figure class="reveal" style="--d:.16s"><img src="{ticket}" alt="입장권"><figcaption><b>입장권</b>한 장에 여러 매</figcaption></figure>
      <figure class="reveal" style="--d:.24s"><img src="{nametag}" alt="좌석 이름표"><figcaption><b>좌석 이름표</b>오려서 붙이면 끝</figcaption></figure>
    </div>

    <p class="eyebrow reveal" style="margin-top:2.6em">원장님과 스태프가 쓰는 것</p>
    <div class="gal">
      <figure class="reveal"><img src="{mc_script}" alt="사회자 대본"><figcaption><b>사회자 대본</b>곡 소개까지 채워져 나옵니다</figcaption></figure>
      <figure class="reveal" style="--d:.08s"><img src="{cue_sheet}" alt="당일 진행표"><figcaption><b>당일 진행표</b>분 단위 시각</figcaption></figure>
      <figure class="reveal" style="--d:.16s"><img src="{certificate}" alt="상장"><figcaption><b>상장</b>아이 수만큼 자동</figcaption></figure>
      <figure class="reveal" style="--d:.24s"><img src="{seating}" alt="좌석 배치도"><figcaption><b>좌석 배치도</b>회신 인원으로 계산</figcaption></figure>
    </div>

    <p class="eyebrow reveal" style="margin-top:2.6em">화면으로 나가는 것</p>
    <div class="gal two">
      <figure class="reveal"><img src="{stage}" alt="무대 화면"><figcaption><b>무대 스크린</b>빔프로젝터에 그대로 · 파워포인트 저장</figcaption></figure>
      <figure class="reveal" style="--d:.1s"><img src="{video}" alt="감동영상 편집기"><figcaption><b>감동영상</b>아이들 사진으로 · 마지막 순서에</figcaption></figure>
    </div>

    <p class="eyebrow reveal" style="margin-top:2.6em">학부모 휴대폰에 가는 것</p>
    <div class="gal">
      <figure class="reveal"><img src="{invite}" alt="모바일 초대장"><figcaption><b>모바일 초대장</b>링크 하나 · 로그인 없이</figcaption></figure>
    </div>

    <p class="gal-note reveal"><b>여기 보이는 것이 전부가 아닙니다.</b> 인쇄물은 83종, 테마는 108종입니다.<br>
    테마를 바꾸면 위의 종이가 <strong>전부 같이</strong> 바뀝니다.</p>
  </div>
</section>

<!-- ── 03 핵심 USP ──────────────────────────────────── -->
<section class="reality">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">03 /</span> 핵심 USP</p>
    <h2 class="reveal" style="--d:0.1s">연주회 준비를 통째로 바꾸는<br><span class="accent">4가지</span></h2>
    <p class="sub reveal" style="--d:0.18s">고르실 것을 늘린 프로그램이 아니라, <strong>고르지 않으셔도 되게</strong> 만든 프로그램입니다.</p>

    <div class="usp-list">
      <div class="card usp-card reveal">
        <div class="usp-num">01</div>
        <div class="usp-body">
          <div class="usp-head">
            <p class="usp-title">명단 한 장이면 순서표까지 &mdash; 3분</p>
            <span class="badge">자동 순서 배치</span>
          </div>
          <p class="usp-desc">엑셀을 그대로 붙여넣으시면 됩니다. 저학년&middot;고학년, 곡 길이, 형제자매까지 헤아려 <strong>연주 순서와 시각</strong>이 잡힙니다. 아이 한 명이 늦게 들어와도 순서만 바꾸면 인쇄물 전부가 함께 바뀝니다. 곡 사전 70여 곡이 들어 있어 곡명만 적으시면 작곡가&middot;연주 시간이 따라옵니다.</p>
        </div>
      </div>

      <div class="card usp-card reveal">
        <div class="usp-num">02</div>
        <div class="usp-body">
          <div class="usp-head">
            <p class="usp-title">인쇄물 83종 &times; 테마 108종</p>
            <span class="badge">예술회관 품질</span>
          </div>
          <p class="usp-desc">포스터&middot;프로그램 책자&middot;순서지&middot;입장권&middot;상장&middot;좌석 이름표&middot;무대 뒤 순서 카드&middot;학부모 안내문&hellip; <strong>테마 하나를 고르면 83종이 같은 옷을 입습니다.</strong> 포스터 31종은 예술회관 연주회 포스터처럼 그림 한 장이 지면을 채웁니다. 「한 벌 인쇄」를 누르시면 필요한 것이 한 번에 나옵니다.</p>
        </div>
      </div>

      <div class="card usp-card reveal">
        <div class="usp-num">03</div>
        <div class="usp-body">
          <div class="usp-head">
            <p class="usp-title">무대 스크린과 감동영상까지</p>
            <span class="badge">당일 진행</span>
          </div>
          <p class="usp-desc">연주회장 빔프로젝터에 띄우는 <strong>연주 순서 슬라이드</strong>가 명단에서 그대로 만들어집니다(파워포인트로도 저장). 아이들 사진을 넣으면 <strong>감동영상</strong>이 만들어져 마지막 순서에 틀 수 있습니다. 당일에는 태블릿을 들고 다니시며 순서를 넘기고 출석을 확인하십니다.</p>
        </div>
      </div>

      <div class="card usp-card reveal">
        <div class="usp-num">04</div>
        <div class="usp-body">
          <div class="usp-head">
            <p class="usp-title">모바일 초대장과 참석 집계</p>
            <span class="badge">의자 개수까지</span>
          </div>
          <p class="usp-desc">학부모께 <strong>링크 하나</strong>를 보내시면 로그인 없이 초대장이 열리고, 참석 여부를 눌러 회신합니다. 몇 가정 몇 명인지 <strong>자동으로 세어</strong> 보여 드립니다. 종이 초대장에는 QR이 함께 찍혀, 휴대폰으로 비추면 바로 열립니다.</p>
        </div>
      </div>
    </div>

    <div class="notice reveal">
      <p class="n-title">&#9888;&#65039; 꼭 확인해 주세요!</p>
      <p><strong>악보와 음원(반주 음악)은 들어 있지 않습니다.</strong> 저작권이 있는 자료라 학원에서 준비하셔야 합니다. 이 프로그램은 <strong>연주회 준비와 진행</strong>을 맡습니다.<br>
      아이 명단과 사진은 <strong>원장님 컴퓨터 안에만</strong> 있습니다. 저희 서버로 올라가지 않습니다. 인터넷이 필요한 것은 학부모께 보내는 초대장 링크 하나뿐입니다.</p>
    </div>
  </div>
</section>

<!-- ── 04 화면 미리보기 ─────────────────────────────── -->
<section class="usp">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">04 /</span> 프로그램은 이렇게 생겼습니다</p>
    <h2 class="reveal" style="--d:0.1s">설치하면 바로 이 화면입니다</h2>
    <div class="shot-grid">
      <div class="shot reveal"><img src="{s3}" alt="연주회 매니저 시작 화면"><p><b>켜는 순간</b> &mdash; 검은 명령창도, 주소창도 없습니다. 다른 프로그램과 똑같이 창 하나로 뜹니다.</p></div>
      <div class="shot reveal" style="--d:0.12s"><img src="{s1}" alt="인쇄물 디자인 화면"><p><b>인쇄물 만들기</b> &mdash; 왼쪽에서 고르고 오른쪽에서 바로 보십니다. 화면이 곧 종이입니다.</p></div>
      <div class="shot reveal" style="--d:0.24s"><img src="{s2}" alt="당일 진행 화면"><p><b>연주회 당일</b> &mdash; 지금 몇 번째인지, 다음이 누구인지. 태블릿으로도 여십니다.</p></div>
    </div>
  </div>
</section>

<!-- ── 05 커리큘럼 : 준비 일정 ──────────────────────── -->
<section class="reality">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">05 /</span> 커리큘럼 &mdash; 연주회 D-30</p>
    <h2 class="reveal" style="--d:0.1s">이 순서대로만 하시면 됩니다</h2>
    <p class="sub reveal" style="--d:0.18s">프로그램이 <strong>다음에 하실 일 하나</strong>만 화면 맨 위에 띄워 드립니다. 순서를 외우실 필요가 없습니다.</p>
    <div class="steps">
      <div class="step reveal"><div class="when">D-30<small>1단계</small></div><div class="what"><b>학생 명단 넣기</b><span>엑셀을 붙여넣거나 파일을 끌어다 놓으시면 끝입니다. 기본 양식도 내려받으실 수 있고, 잘못 적힌 칸(빈 이름·이상한 곡명)은 프로그램이 짚어 드립니다. 형제자매는 묶어서 알려 줍니다.</span><span class="out">나오는 것 &middot; 학생 명단 표</span></div></div>
      <div class="step reveal" style="--d:0.08s"><div class="when">D-21<small>2단계</small></div><div class="what"><b>연주 순서 &middot; 사회자 대본</b><span>저학년부터 고학년으로, 곡 길이를 헤아려 순서와 시각이 자동으로 잡힙니다. 마음에 안 드시면 끌어서 자리만 바꾸시면 되고, 바꾸는 즉시 모든 인쇄물이 따라옵니다. 사회자 대본에는 아이 이름과 곡 소개가 채워져 나옵니다.</span><span class="out">나오는 것 &middot; 순서표 · 사회자 대본 · 당일 진행표</span></div></div>
      <div class="step reveal" style="--d:0.16s"><div class="when">D-14<small>3단계</small></div><div class="what"><b>인쇄물 만들기</b><span>테마 하나를 고르시면 83종이 같은 옷을 입습니다. 「관객용 한 벌」을 누르시면 포스터·프로그램 표지·순서지·입장권이 한 번에 나옵니다. 종이가 몇 장 드는지 뽑기 전에 알려 드립니다.</span><span class="out">나오는 것 &middot; 포스터 · 프로그램 · 입장권 · 상장 · 이름표</span></div></div>
      <div class="step reveal" style="--d:0.24s"><div class="when">D-7<small>4단계</small></div><div class="what"><b>초대장 &middot; 참석 집계</b><span>링크 하나를 단톡방에 보내시면 학부모가 로그인 없이 열고 참석 여부를 누릅니다. 몇 가정 몇 명인지 자동으로 세어 주고, 그 인원으로 좌석 배치도가 그려집니다.</span><span class="out">나오는 것 &middot; 모바일 초대장 · 참석 집계표 · 좌석 배치도</span></div></div>
      <div class="step reveal" style="--d:0.32s"><div class="when">D-1<small>5단계</small></div><div class="what"><b>리허설 &middot; 무대 화면 &middot; 감동영상</b><span>리허설 시간표가 나오고, 빔프로젝터에 띄울 순서 슬라이드가 준비됩니다(파워포인트로도 저장). 아이들 사진을 넣으면 감동영상이 만들어집니다. 빔프로젝터 연결 카드도 함께 뽑아 두세요.</span><span class="out">나오는 것 &middot; 리허설 시간표 · 무대 슬라이드 · 감동영상</span></div></div>
      <div class="step reveal" style="--d:0.4s"><div class="when">당일<small>6단계</small></div><div class="what"><b>진행</b><span>지금 몇 번째, 다음은 누구. 태블릿으로 넘기시면 무대 화면도 함께 넘어갑니다. 출석 확인, 갑작스러운 순서 변경, 지연 시간까지 이 화면 하나에서 처리하십니다.</span><span class="out">쓰는 것 &middot; 당일 진행 화면 · 무대 뒤 순서 카드</span></div></div>
      <div class="step reveal" style="--d:0.48s"><div class="when">D+1<small>7단계</small></div><div class="what"><b>마무리</b><span>감사 문구와 상장이 나옵니다. 올해 자료는 그대로 남아, 내년에는 <strong>이름만 바꿔</strong> 다시 쓰십니다. 두 번째 해부터가 진짜로 편해집니다.</span><span class="out">나오는 것 &middot; 감사 안내문 · 상장 · 내년용 자료</span></div></div>
    </div>
  </div>
</section>

<!-- ── 06 이용 안내 ─────────────────────────────────── -->
<section class="guide">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">06 /</span> 이용 안내</p>
    <h2 class="reveal" style="--d:0.1s">받으시고, 까시고, 키 한 번</h2>
    <div class="info-cards">
      <div class="info-card red reveal">
        <p class="label">설치</p>
        <p class="big">두 번 클릭</p>
        <p class="desc">결제하시면 받는 주소를 보내 드립니다<br>다음 &middot; 다음 &middot; 설치로 끝</p>
      </div>
      <div class="info-card blue reveal" style="--d:0.15s">
        <p class="label">인증키</p>
        <p class="big">한 번만 입력</p>
        <p class="desc">문자로 보내 드리는 스무 글자<br>인터넷 없이 확인됩니다</p>
      </div>
    </div>

    <table class="spec reveal" style="--d:0.25s">
      <tr><th>쓰는 곳</th><td>윈도우 10&middot;11 (맥은 dmg 제공) &middot; 태블릿&middot;휴대폰은 같은 와이파이에서 함께 열람</td></tr>
      <tr><th>인터넷</th><td><strong>없어도 됩니다.</strong> 학부모 초대장 링크를 여실 때만 필요합니다</td></tr>
      <tr><th>자료가 있는 곳</th><td>원장님 컴퓨터 안. 아이 명단&middot;사진은 저희 서버로 올라가지 않습니다</td></tr>
      <tr><th>들어 있는 것</th><td>인쇄물 83종 &middot; 테마 108종 &middot; 곡 사전 70여 곡 &middot; 무대 화면 &middot; 감동영상 &middot; 모바일 초대장 &middot; 사용설명서</td></tr>
      <tr><th>들어 있지 않은 것</th><td>악보 &middot; 반주 음원 &middot; 배경 음악 (저작권 자료라 학원에서 준비하십니다)</td></tr>
      <tr><th>컴퓨터를 바꾸면</th><td>새 컴퓨터에 설치하고 <strong>같은 키</strong>를 넣으시면 됩니다</td></tr>
    </table>
  </div>
</section>

<!-- ── 07 이런 분께 추천합니다 ──────────────────────── -->
<section class="recommend">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">07 /</span> 이런 분께 추천합니다</p>
    <h2 class="reveal" style="--d:0.1s">올해 연주회부터<br><span class="accent">밤새우지 않으셔도</span> 됩니다</h2>
    <div class="pill-list">
      <div class="pill reveal"><span class="icon check">&#10003;</span><span>해마다 연주회를 여시지만, 준비하는 2주가 늘 버거우셨던 원장님</span></div>
      <div class="pill reveal" style="--d:0.12s"><span class="icon check">&#10003;</span><span>컴퓨터가 어려워 포스터&middot;순서지를 남에게 맡기거나 작년 것을 고쳐 쓰셨던 원장님</span></div>
      <div class="pill reveal" style="--d:0.24s"><span class="icon check">&#10003;</span><span>학원 연주회를 <strong>예술회관 연주회처럼</strong> 보이게 하고 싶으신 원장님</span></div>
    </div>
  </div>
</section>

<!-- ── 최종 CTA ─────────────────────────────────────── -->
<section class="cta">
  <span class="note-deco n1">&#9834;</span>
  <span class="note-deco n2">&#9835;</span>
  <div class="inner">
    <p class="eyebrow reveal">ACCELSSAM &nbsp;·&nbsp; 연주회 매니저</p>
    <h2 class="reveal" style="--d:0.1s">올해 연주회는<br><span class="gold">명단 한 장</span>에서 시작하세요</h2>
    <p class="sub reveal" style="--d:0.2s">결제하시면 받는 주소와 인증키를 바로 보내 드립니다.</p>
    <div class="reveal" style="--d:0.3s">
      <a class="cta-btn" href="https://accelssam.com/cart/?add-to-cart=2089" target="_top">연주회 매니저 받기</a>
    </div>
    <p class="period reveal" style="--d:0.4s">설치형 프로그램 &middot; 윈도우&middot;맥 &middot; 인터넷 없이 작동</p>
  </div>
</section>
"""

tpl = TPL.read_text(encoding='utf-8')
out = tpl.replace(
    '<title>A. Martin Cuellar – Toccata(쿠엘라 토카타) | 아첼쌤 콩쿨곡 코칭</title>',
    '<title>연주회 매니저 | 피아노학원 연주회 준비 프로그램 · 아첼쌤</title>',
)
out = out.replace('</style>', EXTRA_CSS + '</style>', 1)
start, end = out.index('<body>'), out.index('<script>')
out = out[:start] + BODY.format(**IMG) + '\n' + out[end:]
out = out.replace('accel-toccata-height', 'accel-recital-height')

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(out, encoding='utf-8')
print(f'{OUT} · {len(out.encode())/1024:.0f}KB')
