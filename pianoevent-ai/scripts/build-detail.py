import base64, pathlib, re

ROOT = pathlib.Path('/home/user/-/pianoevent-ai')
TPL = pathlib.Path('/root/.claude/skills/synced/accelssam-detail-page/template.html').read_text()

# 템플릿의 <style> 블록(디자인 시스템)을 그대로 가져온다
style = re.search(r'<style>(.*?)</style>', TPL, re.S).group(1)

def b64(name):
    data = (ROOT / 'promo' / name).read_bytes()
    return 'data:image/jpeg;base64,' + base64.b64encode(data).decode()

IMG = {k: b64(v) for k, v in {
    'LAPTOP_PROGRAM': 'laptop-program.jpg',
    'LAPTOP_DESIGN': 'laptop-design.jpg',
    'TABLET_PREP': 'tablet-prep.jpg',
    'MOBILE_INVITE': 'mobile-invite.jpg',
    'PRINT_POSTER': 'print-poster.jpg',
    'PRINT_PROGRAM': 'print-program.jpg',
    'PRINT_CUE': 'print-cue.jpg',
}.items()}

EXTRA_CSS = """
  /* ── 기능 격자 ───────────────────────────────────── */
  .feat-grid{display:grid;gap:1rem;margin-top:1.8rem;}
  @media (min-width:620px){.feat-grid{grid-template-columns:1fr 1fr;}}
  @media (min-width:960px){.feat-grid{grid-template-columns:repeat(3,1fr);}}
  .feat{border:1px solid rgba(120,100,70,.2);border-radius:12px;padding:1.15rem;background:#fff;
    display:flex;flex-direction:column;gap:.5rem;}
  .feat .n{font-size:.7rem;letter-spacing:.16em;font-weight:700;color:var(--gold,#B3892F);}
  .feat h4{margin:0;font-size:1.02rem;line-height:1.4;}
  .feat p{margin:0;font-size:.88rem;line-height:1.7;opacity:.85;}
  .feat .only{margin-top:auto;padding-top:.7rem;border-top:1px dashed rgba(120,100,70,.25);
    font-size:.8rem;font-weight:700;color:#8A5A1E;}

  /* ── 한 번 입력 → 전부 연쇄 ─────────────────────── */
  .chain{margin-top:1.8rem;border:1px solid rgba(120,100,70,.2);border-radius:14px;
    background:#fff;padding:1.5rem 1.2rem;text-align:center;}
  .chain .seed{display:inline-block;padding:.7em 1.6em;border-radius:999px;
    background:#2A2118;color:#F5EDDD;font-weight:700;font-size:.98rem;}
  .chain .arrow{font-size:1.3rem;color:var(--gold,#B3892F);line-height:1;margin:.7rem 0;}
  .chain-row{display:flex;flex-wrap:wrap;gap:.5rem;justify-content:center;}
  .chain-row span{padding:.45em 1em;border-radius:999px;border:1px solid rgba(120,100,70,.3);
    background:#FBF6EA;font-size:.86rem;}
  .chain .last{margin-top:1.2rem;font-size:.92rem;font-weight:700;}

  /* ── 숫자 띠 ─────────────────────────────────────── */
  .numbers{display:grid;gap:.9rem;margin-top:1.6rem;grid-template-columns:repeat(2,1fr);}
  @media (min-width:720px){.numbers{grid-template-columns:repeat(4,1fr);}}
  .numbers div{border:1px solid rgba(120,100,70,.2);border-radius:12px;padding:1rem .8rem;
    text-align:center;background:#fff;}
  .numbers .v{font-size:1.7rem;font-weight:800;color:var(--gold,#B3892F);line-height:1.1;margin:0;}
  .numbers .k{font-size:.8rem;line-height:1.5;opacity:.8;margin:.5em 0 0;}
  /* ── 체험 버튼 ───────────────────────────────────── */
  .try-btn{
    display:inline-flex;align-items:center;gap:.55em;
    padding:.85em 1.9em;border-radius:999px;
    border:2px solid var(--gold,#B3892F);
    background:transparent;color:var(--gold,#B3892F);
    font-weight:700;text-decoration:none;
    transition:background .2s,color .2s,transform .2s;
  }
  .try-btn:hover{background:var(--gold,#B3892F);color:#fff;transform:translateY(-2px);}
  .cta .try-btn{border-color:#F0D9A0;color:#F0D9A0;}
  .cta .try-btn:hover{background:#F0D9A0;color:#2A1F12;}
  .btn-row{display:flex;flex-wrap:wrap;gap:.9rem;align-items:center;margin-top:1.4rem;}
  .btn-note{font-size:.86rem;opacity:.75;flex-basis:100%;}

  /* ── 제공/미제공 두 칸 ───────────────────────────── */
  .scope-grid{display:grid;gap:1.2rem;margin-top:1.8rem;}
  @media (min-width:760px){.scope-grid{grid-template-columns:1fr 1fr;}}
  .scope-col{border:1px solid rgba(120,100,70,.22);border-radius:12px;padding:1.4rem;background:#fff;}
  .scope-col.no{background:#FBF7F1;}
  .scope-col h3{font-size:1.05rem;margin:0 0 .9em;}
  .scope-col ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.7em;}
  .scope-col li{display:flex;gap:.6em;align-items:flex-start;font-size:.94rem;line-height:1.65;}
  .scope-col li b{font-weight:700;}
  .scope-mark{flex-shrink:0;width:1.4em;height:1.4em;border-radius:50%;display:grid;place-items:center;
    font-size:.72em;font-weight:700;margin-top:.18em;}
  .scope-col.yes .scope-mark{background:#E6F0E8;color:#2F6B45;}
  .scope-col.no .scope-mark{background:#F1E3E3;color:#96413E;}
  .scope-why{margin-top:1.2rem;padding-top:1rem;border-top:1px dashed rgba(120,100,70,.28);
    font-size:.88rem;line-height:1.8;opacity:.85;}

  /* ── 비교표 ─────────────────────────────────────── */
  .cmp-wrap{overflow-x:auto;margin-top:1.6rem;}
  .cmp{width:100%;border-collapse:collapse;font-size:.92rem;min-width:640px;background:#fff;}
  .cmp th,.cmp td{padding:.85em .9em;border-bottom:1px solid rgba(120,100,70,.18);text-align:left;vertical-align:top;}
  .cmp thead th{font-size:.8rem;letter-spacing:.06em;background:#F6F1E7;border-bottom:2px solid rgba(120,100,70,.3);}
  .cmp tbody th{font-weight:700;width:9.5em;}
  .cmp .ours{background:#FBF6EA;font-weight:600;}
  .cmp thead .ours{background:#B3892F;color:#fff;}

  /* ── 3단 흐름 ───────────────────────────────────── */
  .flow{display:grid;gap:1rem;margin-top:1.6rem;}
  @media (min-width:720px){.flow{grid-template-columns:repeat(3,1fr);}}
  .flow-step{border:1px solid rgba(120,100,70,.22);border-radius:12px;padding:1.2rem;background:#fff;}
  .flow-step .t{font-size:.74rem;letter-spacing:.18em;color:var(--gold,#B3892F);font-weight:700;}
  .flow-step h4{margin:.6em 0 .4em;font-size:1rem;}
  .flow-step p{font-size:.89rem;line-height:1.7;opacity:.85;margin:0;}
  .flow-step .time{margin-top:.8em;display:inline-block;padding:.2em .7em;border-radius:999px;
    background:#F6F1E7;font-size:.78rem;font-weight:700;}
  /* ── 기기 목업 (노트북·태블릿·모바일) ───────────── */
  .device{margin:0 auto;width:100%;}
  .device img{display:block;width:100%;height:auto;}
  .device .bezel{
    background:#241F1A;
    border-radius:14px;
    padding:10px 10px 12px;
    box-shadow:0 18px 44px rgba(52,38,15,0.22);
  }
  .device.phone .bezel{border-radius:34px;padding:9px;max-width:290px;margin:0 auto;}
  .device.phone .screen{border-radius:26px;}
  .device.tablet .bezel{border-radius:22px;padding:11px;max-width:460px;margin:0 auto;}
  .device.tablet .screen{border-radius:14px;}
  .device .screen{overflow:hidden;border-radius:7px;background:#fff;}
  .device .stand{
    width:min(78%,520px);height:11px;margin:0 auto;
    background:linear-gradient(180deg,#3A322A,#1B1713);
    border-radius:0 0 12px 12px;
    box-shadow:0 10px 18px rgba(52,38,15,0.18);
  }
  .device-cap{
    margin-top:1em;text-align:center;
    font-size:clamp(1rem,0.95rem + 0.3vw,1.12rem);
    color:var(--ink-soft);
  }
  .device-cap b{color:var(--ink);font-weight:700;}

  .showcase{margin-top:clamp(2rem,4vw,3rem);}
  .showcase-2{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));
    gap:clamp(1.8rem,4vw,3rem);
    margin-top:clamp(2.2rem,4vw,3.2rem);
    align-items:end;
  }

  /* ── 인쇄물 3장 ─────────────────────────── */
  .sheets{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));
    gap:clamp(1.2rem,3vw,2rem);
    margin-top:clamp(2rem,4vw,3rem);
  }
  .sheet-item img{
    display:block;width:100%;height:auto;border-radius:6px;
    border:1px solid rgba(160,124,44,0.22);
    box-shadow:0 12px 30px rgba(52,38,15,0.14);
    background:#fff;
  }
  .sheet-item p{
    margin-top:0.9em;text-align:center;
    font-size:clamp(1rem,0.96rem + 0.25vw,1.1rem);
    color:var(--ink-soft);
  }
  .sheet-item p b{display:block;color:var(--ink);font-weight:700;margin-bottom:0.15em;}

  /* 히어로 우측 목업 */
  .hero-visual{flex:1 1 380px;min-width:min(100%,280px);align-self:center;}

  /* 숫자 요약 */
  .stat-row{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));
    gap:clamp(0.9rem,2vw,1.4rem);
    margin-top:clamp(1.8rem,3.5vw,2.6rem);
  }
  .stat{
    background:var(--white);
    border:1px solid rgba(160,124,44,0.14);
    border-radius:18px;
    padding:clamp(1.1rem,2.5vw,1.6rem) 1rem;
    text-align:center;
    box-shadow:0 6px 24px rgba(83,62,38,0.06);
  }
  .stat .v{
    font-family:'Noto Serif KR',serif;font-weight:900;
    font-size:clamp(1.5rem,1.2rem + 1.3vw,2.1rem);
    color:var(--burgundy);line-height:1.2;
  }
  .stat .k{
    margin-top:0.45em;
    font-size:clamp(1rem,0.96rem + 0.2vw,1.08rem);
    color:var(--ink-soft);
  }
"""

BODY = """
<!-- ── HERO ─────────────────────────────────────────── -->
<section class="hero">
  <div class="inner">
    <div class="hero-top">
      <div class="hero-title">
        <p class="eyebrow reveal">PIANOEVENT &nbsp;&middot;&nbsp; 피아노학원 연주회 올인원</p>
        <h1 class="reveal" style="--d:0.12s">연주회 준비에 쓰던 사흘,<br>이제 <span class="accent">30분</span>이면 끝납니다</h1>
      </div>
      <div class="hero-visual reveal" style="--d:0.25s">
        <div class="device laptop">
          <div class="bezel"><div class="screen"><img src="__LAPTOP_PROGRAM__" alt="연주 순서표와 사회자 대본이 자동으로 만들어진 화면"></div></div>
          <div class="stand"></div>
        </div>
        <p class="device-cap"><b>학생 명단만 넣으면</b> 순서표와 사회자 대본이 이렇게 나옵니다</p>
      </div>
    </div>
    <div class="card reveal" style="--d:0.35s">
      <p>정기 연주회 한 번에 원장님이 쓰시는 시간, 솔직히 얼마나 되시나요?<br>
      순서 짜고, 곡 해설 찾고, 멘트 쓰고, 포스터 만들고, 초대장 돌리고, 참석 인원 세고&#8230;
      <strong class="accent">보통 15~25시간</strong>입니다.</p>
      <p><strong>피아노 이벤트 솔루션</strong>은 그 과정을 통째로 대신합니다. 엑셀 명단을 붙여넣는 것으로 시작해서,
      인쇄해서 손에 쥐는 것까지 <strong>한 자리에서</strong> 끝납니다.</p>
      <div class="stat-row">
        <div class="stat"><p class="v">30초</p><p class="k">순서표 · 러닝타임<br>자동 계산</p></div>
        <div class="stat"><p class="v">32종</p><p class="k">인쇄물 양식</p></div>
        <div class="stat"><p class="v">40종</p><p class="k">디자인 테마</p></div>
        <div class="stat"><p class="v">0원</p><p class="k">디자인 외주비</p></div>
      </div>
      <div class="btn-row">
        <a class="try-btn" href="https://claude.ai/code/artifact/f2def9cb-d28e-4cb0-beee-a315c02828bb" target="_blank" rel="noopener">직접 눌러 보기 &nbsp;&rarr;</a>
        <span class="btn-note">설치도 회원가입도 없습니다. 예시 명단이 들어 있어 바로 만져 보실 수 있습니다.</span>
      </div>
    </div>
  </div>
</section>

<!-- ── 01 연주회 준비 현실 체크 ─────────────────────── -->
<section class="reality">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">01 /</span> 연주회 준비 현실 체크</p>
    <h2 class="reveal" style="--d:0.1s">연주회 시즌마다<br>이런 밤을 보내지 않으셨나요?</h2>
    <div class="pill-list">
      <div class="pill reveal"><span class="icon x">&#10005;</span><span>엑셀로 순서를 짜다가 <b>학생 한 명이 바뀌면</b> 러닝타임을 처음부터 다시 계산하는 상황</span></div>
      <div class="pill reveal" style="--d:0.12s"><span class="icon x">&#10005;</span><span>곡 해설을 검색해 옮기고 학생 소개 멘트를 하나씩 쓰다 보면 <b>어느새 새벽</b></span></div>
      <div class="pill reveal" style="--d:0.24s"><span class="icon x">&#10005;</span><span>포스터 &middot; 순서지 &middot; 입장권 &middot; 상장을 <b>매번 새 파일</b>로 만들다가 결국 외주를 맡기는 상황</span></div>
      <div class="pill reveal" style="--d:0.36s"><span class="icon x">&#10005;</span><span>참석 인원을 단톡방 답장으로 세다가 <b>좌석과 프로그램 부수</b>가 어긋나는 상황</span></div>
    </div>
  </div>
</section>

<!-- ── 02 핵심 4가지 ────────────────────────────────── -->
<section class="usp">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">02 /</span> 핵심 기능</p>
    <h2 class="reveal" style="--d:0.1s">원장님이 직접 하던 일을<br><span class="accent">4가지</span>가 대신합니다</h2>
    <p class="sub reveal" style="--d:0.18s">기능 자랑이 아니라, 실제로 시간을 가장 많이 먹던 네 곳을 그대로 없앴습니다.</p>

    <div class="usp-list">
      <div class="card usp-card reveal">
        <div class="usp-num">01</div>
        <div class="usp-body">
          <div class="usp-head">
            <p class="usp-title">엑셀 명단 붙여넣기 &#8594; 연주 순서와 종료 시각까지 자동</p>
            <span class="badge">30초 완성</span>
          </div>
          <p class="usp-desc">엑셀에서 표를 복사해 붙여넣기만 하면 됩니다. <strong>오프닝 &#8594; 초급 &#8594; 중급 &#8594; 듀엣 &#8594; 피날레</strong> 흐름으로 자동 배치하고, 곡 사이 전환 시간과 중간 휴식까지 넣어 <strong>몇 시에 끝나는지</strong>까지 계산합니다. 같은 작곡가나 같은 학생이 연달아 나오면 알아서 자리를 바꿉니다.</p>
        </div>
      </div>

      <div class="card usp-card reveal">
        <div class="usp-num">02</div>
        <div class="usp-body">
          <div class="usp-head">
            <p class="usp-title">곡마다 사회자 멘트가 완성된 채로 나옵니다</p>
            <span class="badge">대본 완성</span>
          </div>
          <p class="usp-desc">곡 해설 한두 줄에 학생 소개를 엮은 멘트가 <strong>곡마다</strong> 만들어집니다. 행사 오프닝과 클로징 멘트까지 포함이라, 인쇄해서 사회자에게 그대로 건네면 됩니다. 학생 특징을 한 줄만 적어 두시면 그 문장이 멘트에 자연스럽게 들어갑니다.</p>
        </div>
      </div>

      <div class="card usp-card reveal">
        <div class="usp-num">03</div>
        <div class="usp-body">
          <div class="usp-head">
            <p class="usp-title">포스터부터 상장까지, 테마 하나로 통일된 인쇄물</p>
            <span class="badge">인쇄물 20종</span>
          </div>
          <p class="usp-desc">포스터 5종 &middot; 프로그램 3종 &middot; 입장권 &middot; SNS 카드 &middot; 감사 카드 &middot; 참가 상장 &middot; 좌석 이름표 &middot; 진행표 &middot; 체크리스트. <strong>테마 하나를 고르면 전부 같은 옷</strong>을 입습니다. 학원 로고와 사진이 들어갈 자리도 이미 잡혀 있습니다. 상장은 인원수만큼, 이름표는 8개씩 알아서 이어 인쇄됩니다.</p>
        </div>
      </div>

      <div class="card usp-card reveal">
        <div class="usp-num">04</div>
        <div class="usp-body">
          <div class="usp-head">
            <p class="usp-title">카카오톡 초대장 &#8594; 참석 인원이 저절로 집계됩니다</p>
            <span class="badge">좌석 계산 끝</span>
          </div>
          <p class="usp-desc">링크 하나를 단톡방에 올리면 끝입니다. 학부모는 <strong>로그인 없이</strong> 열어 참석 여부와 인원을 남기고, 원장님 화면에는 <strong>참석 가정 수와 총 인원</strong>이 실시간으로 쌓입니다. 좌석과 프로그램 부수가 더 이상 어긋나지 않습니다.</p>
        </div>
      </div>
    </div>

    <div class="notice reveal">
      <p class="n-title">&#9888;&#65039; 이런 점이 편합니다</p>
      <p>설치 프로그램이 아닙니다. <strong>인터넷만 되면</strong> 학원 컴퓨터, 집 노트북, 태블릿 어디서든 같은 화면으로 이어서 작업하실 수 있습니다. PDF도 따로 프로그램 없이 <strong>인쇄 버튼 하나</strong>로 저장됩니다.</p>
    </div>
  </div>
</section>


<!-- ── 기능 전체 ────────────────────────────────────── -->
<section class="usp">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">03 /</span> 이 프로그램이 하는 일 전부</p>
    <h2 class="reveal" style="--d:0.1s">명단 하나를 넣으면<br><span class="accent">여기까지</span> 나옵니다</h2>

    <div class="numbers reveal" style="--d:0.15s">
      <div><p class="v">78곡</p><p class="k">곡 사전<br>작곡가 · 시간 · 해설</p></div>
      <div><p class="v">32종</p><p class="k">인쇄물 양식</p></div>
      <div><p class="v">40종</p><p class="k">디자인 테마</p></div>
      <div><p class="v">8가지</p><p class="k">순서표 자동 점검</p></div>
    </div>

    <div class="feat-grid">
      <div class="feat reveal">
        <p class="n">01 &nbsp;곡 사전</p>
        <h4>곡 제목만 치면 나머지가 따라옵니다</h4>
        <p>학원 연주회에 실제로 오르는 78곡 &mdash; 부르크뮐러부터 히사이시 조까지. 곡을 고르면
        <b>작곡가 &middot; 난이도 &middot; 연주시간</b>이 함께 들어가고, 사회자 멘트에 쓸 <b>곡 해설</b>까지 준비됩니다.</p>
        <p class="only">엑셀에도 캔바에도 없는 것</p>
      </div>
      <div class="feat reveal" style="--d:0.08s">
        <p class="n">02 &nbsp;순서 자동 배치</p>
        <h4>흐름과 시각을 동시에 계산합니다</h4>
        <p>오프닝 &rarr; 초급 &rarr; 중급 &rarr; 앙상블 &rarr; 피날레. 곡 사이 전환 시간과 중간 휴식까지 넣어
        <b>몇 시에 끝나는지</b>를 알려 줍니다. 마음에 안 드는 곳은 <b>위·아래 버튼으로 직접</b> 옮깁니다.</p>
        <p class="only">바꾸면 32종이 함께 바뀜</p>
      </div>
      <div class="feat reveal" style="--d:0.16s">
        <p class="n">03 &nbsp;사회자 대본</p>
        <h4>곡마다 멘트가 쓰여 있습니다</h4>
        <p>곡 &middot; 작곡가 &middot; 학생 메모를 엮어 오프닝부터 클로징까지. 무대 옆은 어두우니
        <b>큰 글씨 인쇄</b>로 나갑니다.</p>
        <p class="only">밤새 쓰던 그 문장</p>
      </div>
      <div class="feat reveal" style="--d:0.24s">
        <p class="n">04 &nbsp;순서표 점검</p>
        <h4>당일 전화를 부르는 것들을 미리 잡습니다</h4>
        <p>같은 곡 중복, 형제자매가 멀리 떨어짐, 어린 학생이 맨 뒤, 같은 작곡가 3연속,
        휴식 없이 70분 초과 &mdash; <b>8가지를 3등급으로</b> 알려 주고 고치는 법까지 적어 줍니다.</p>
        <p class="only">사람이 놓치는 것</p>
      </div>
      <div class="feat reveal" style="--d:0.32s">
        <p class="n">05 &nbsp;인쇄물</p>
        <h4>양식 32종 &times; 테마 40종</h4>
        <p>포스터 7 &middot; 프로그램 5 &middot; 초대·홍보 5 &middot; 행사 당일 7 &middot; 진행 문서 8.
        테마 하나를 고르면 <b>전부 같은 색과 서체</b>를 입습니다. 한 벌 인쇄로 여러 장을 한 번에.</p>
        <p class="only">외주비 0원</p>
      </div>
      <div class="feat reveal" style="--d:0.4s">
        <p class="n">06 &nbsp;모바일 초대장</p>
        <h4>링크 하나로 참석 인원이 쌓입니다</h4>
        <p>단톡방에 올리면 학부모가 눌러 회신하고, <b>가정 수 &middot; 총원 &middot; 응원 메시지</b>가 저절로
        모입니다. 그 인원이 그대로 좌석 배치로 넘어갑니다.</p>
        <p class="only">답장 세지 않아도 됨</p>
      </div>
      <div class="feat reveal" style="--d:0.48s">
        <p class="n">07 &nbsp;리허설 시간표</p>
        <h4>조 단위 소집 시각과 문자까지</h4>
        <p>전원을 한 번에 부르면 대기실이 터집니다. 5명씩 묶어 <b>조별 도착 시각</b>을 계산하고
        조마다 보낼 <b>문자를 만들어</b> 둡니다. 문자 30통이 6통이 됩니다.</p>
        <p class="only">당일 아침의 계산</p>
      </div>
      <div class="feat reveal" style="--d:0.56s">
        <p class="n">08 &nbsp;참가비 계산</p>
        <h4>대관료 확정 전에도 안내가 나갑니다</h4>
        <p>항목 10가지 예산에서 <b>1인당 원가와 권장 참가비</b>를 역산합니다. 선택 항목을 끄면 즉시
        다시 계산되고, <b>안내 문구</b>까지 복사해 보냅니다.</p>
        <p class="only">감으로 정하지 않음</p>
      </div>
      <div class="feat reveal" style="--d:0.64s">
        <p class="n">09 &nbsp;좌석 배치</p>
        <h4>가족은 붙여 앉히고 앞줄은 비웁니다</h4>
        <p>참석 회신을 <b>가정 단위</b>로 앉히고 앞 두 줄은 연주자석으로 둡니다.
        <b>&ldquo;3열 4~6번&rdquo;</b>처럼 학부모에게 그대로 보낼 수 있는 표기로 나옵니다.</p>
        <p class="only">접수처에 붙이면 끝</p>
      </div>
      <div class="feat reveal" style="--d:0.72s">
        <p class="n">10 &nbsp;이미지 보관함</p>
        <h4>사진을 끌어다 놓으면 전부에 들어갑니다</h4>
        <p>로고 &middot; 학원 상징 &middot; 사진을 한 번만 올리면 됩니다. 휴대폰 사진도 <b>인쇄 크기로 자동 축소</b>,
        테마마다 <b>모양은 알아서</b> 맞춰집니다. 포스터엔 단체사진, 표지엔 학원 전경처럼 따로 지정도 됩니다.</p>
        <p class="only">주소 다시 찾을 일 없음</p>
      </div>
      <div class="feat reveal" style="--d:0.8s">
        <p class="n">11 &nbsp;준비 체크리스트</p>
        <h4>D-30부터 종료 후까지</h4>
        <p>30가지 할 일이 <b>행사 날짜에 맞춰</b> 날짜와 함께 나옵니다. 학부모 안내 문자 4종도
        시기별로 준비돼 있습니다.</p>
        <p class="only">빠뜨릴 수가 없음</p>
      </div>
      <div class="feat reveal" style="--d:0.88s">
        <p class="n">12 &nbsp;시즌 특강</p>
        <h4>할로윈 &middot; 크리스마스 &middot; 방학</h4>
        <p>테마를 고르면 <b>4주 커리큘럼과 인쇄용 활동지</b>가 나옵니다. 연주회가 없는 달에도
        학원이 돌아갑니다.</p>
        <p class="only">자료 사서 짜깁기 안 함</p>
      </div>
    </div>
  </div>
</section>

<!-- ── 한 번 입력 → 전부 연쇄 ──────────────────────── -->
<section class="guide">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">04 /</span> 왜 이게 다른가</p>
    <h2 class="reveal" style="--d:0.1s">한 곳을 고치면<br><span class="accent">전부 따라 바뀝니다</span></h2>
    <p class="sub reveal" style="--d:0.16s">다른 도구들은 각 결과물이 따로 놉니다. 순서 하나가 바뀌면 전부 손으로 다시 고쳐야 합니다.</p>
    <div class="chain reveal" style="--d:0.22s">
      <span class="seed">학생 명단 한 번 입력</span>
      <p class="arrow">&#9660;</p>
      <div class="chain-row">
        <span>연주 순서</span><span>예상 시각</span><span>러닝타임</span><span>곡 해설</span><span>사회자 멘트</span>
      </div>
      <p class="arrow">&#9660;</p>
      <div class="chain-row">
        <span>포스터</span><span>프로그램 표지</span><span>순서지</span><span>곡 해설 순서지</span><span>3단 접지</span>
        <span>입장권</span><span>초대장 카드</span><span>SNS 스토리</span><span>X배너</span>
        <span>상장</span><span>이름표</span><span>대기 순서판</span><span>포토존</span><span>시상 명단</span>
      </div>
      <p class="arrow">&#9660;</p>
      <div class="chain-row">
        <span>리허설 소집 시각</span><span>조별 문자</span><span>좌석 배치도</span><span>접수 확인표</span>
        <span>당일 진행표</span><span>참가비</span><span>예산표</span><span>학부모 안내문</span>
      </div>
      <p class="last">순서 하나를 바꾸면 &mdash; 위의 <b>32종이 동시에</b> 다시 만들어집니다</p>
    </div>
  </div>
</section>

<!-- ── 03 화면 미리보기 ─────────────────────────────── -->
<section class="guide">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">05 /</span> 실제 화면</p>
    <h2 class="reveal" style="--d:0.1s">노트북에서도, 태블릿에서도,<br><span class="accent">휴대폰에서도</span> 그대로입니다</h2>
    <p class="sub reveal" style="--d:0.18s" style="font-size:var(--fs-body);color:var(--ink-soft);margin-top:1em;">학원에서 노트북으로 만들고, 집에서 태블릿으로 고치고, 학부모는 휴대폰으로 엽니다.</p>

    <div class="showcase reveal">
      <div class="device laptop">
        <div class="bezel"><div class="screen"><img src="__LAPTOP_DESIGN__" alt="인쇄물 디자인 화면 - 양식과 테마를 고르면 오른쪽에 미리보기가 바뀐다"></div></div>
        <div class="stand"></div>
      </div>
      <p class="device-cap"><b>노트북 &middot; 인쇄물 디자인</b> — 왼쪽에서 양식과 테마를 고르면 오른쪽 미리보기가 즉시 바뀝니다</p>
    </div>

    <div class="showcase-2">
      <div class="reveal">
        <div class="device tablet">
          <div class="bezel"><div class="screen"><img src="__TABLET_PREP__" alt="태블릿에서 본 진행 준비 화면 - 준비 체크리스트와 학부모 안내 문구"></div></div>
        </div>
        <p class="device-cap"><b>태블릿 &middot; 진행 준비</b> — 준비 체크리스트와<br>학부모 안내 문구를 손에 들고 확인</p>
      </div>
      <div class="reveal" style="--d:0.15s">
        <div class="device phone">
          <div class="bezel"><div class="screen"><img src="__MOBILE_INVITE__" alt="학부모 휴대폰에서 열리는 모바일 초대장"></div></div>
        </div>
        <p class="device-cap"><b>휴대폰 &middot; 학부모 초대장</b> — 링크만 누르면<br>열리고, 그 자리에서 참석 회신</p>
      </div>
    </div>
  </div>
</section>

<!-- ── 04 인쇄물 ────────────────────────────────────── -->
<section class="usp">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">06 /</span> 인쇄물 미리보기</p>
    <h2 class="reveal" style="--d:0.1s">A4 용지에 그대로,<br><span class="accent">디자인 외주 없이</span></h2>
    <p class="sub reveal" style="--d:0.18s">아래는 실제로 출력되는 모습입니다. 학원 이름과 로고, 학생 이름이 모두 자동으로 들어갑니다.</p>

    <div class="sheets">
      <div class="sheet-item reveal">
        <img src="__PRINT_POSTER__" alt="연주회 포스터 인쇄 견본">
        <p><b>포스터</b>현관 &middot; 엘리베이터 게시용</p>
      </div>
      <div class="sheet-item reveal" style="--d:0.12s">
        <img src="__PRINT_PROGRAM__" alt="연주 순서지 인쇄 견본">
        <p><b>프로그램 순서지</b>관객 배부용, 예상 시각 포함</p>
      </div>
      <div class="sheet-item reveal" style="--d:0.24s">
        <img src="__PRINT_CUE__" alt="당일 진행표 인쇄 견본">
        <p><b>당일 진행표</b>사회자 &middot; 스태프용 큐시트</p>
      </div>
    </div>

    <div class="notice reveal">
      <p class="n-title">&#9989; 한 벌 인쇄</p>
      <p>양식을 하나씩 고르실 필요 없습니다. <strong>관객용 한 벌</strong>(포스터 &middot; 표지 &middot; 순서지 &middot; 입장권)과 <strong>당일 운영 한 벌</strong>(진행표 &middot; 체크리스트 &middot; 이름표)을 버튼 하나로 한 번에 뽑습니다.</p>
    </div>
  </div>
</section>

<!-- ── 05 이용 안내 ─────────────────────────────────── -->
<section class="guide">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">07 /</span> 이용 안내</p>
    <h2 class="reveal" style="--d:0.1s">피아노 이벤트 솔루션 이용 안내</h2>
    <div class="info-cards">
      <div class="info-card red reveal">
        <p class="label">이용 기간</p>
        <p class="big">결제 후 1년</p>
        <p class="desc">정기 연주회 &middot; 시즌 특강<br>행사 수 제한 없이 무제한</p>
      </div>
      <div class="info-card blue reveal" style="--d:0.15s">
        <p class="label">제공 범위</p>
        <p class="big">인쇄물 20종</p>
        <p class="desc">디자인 테마 20종 &middot; 사회자 대본<br>모바일 초대장 &middot; 참석 집계</p>
      </div>
    </div>
    <div class="notice reveal">
      <p class="n-title">&#128221; 함께 드리는 것</p>
      <p><strong>원장님용 사용설명서</strong>(화면 순서 그대로 따라 하는 안내서)와 <strong>준비 체크리스트</strong>(D-30부터 종료 후까지)를 함께 드립니다. 컴퓨터가 익숙하지 않으셔도 누르는 곳만 따라오시면 됩니다.</p>
    </div>
  </div>
</section>


<!-- ── 서비스 범위 ──────────────────────────────────── -->
<section class="usp">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">08 /</span> 무엇을 드리고, 무엇은 드리지 않는가</p>
    <h2 class="reveal" style="--d:0.1s">사시기 전에<br><span class="accent">이것부터</span> 확인해 주세요</h2>
    <div class="scope-grid">
      <div class="scope-col yes reveal">
        <h3>드리는 것</h3>
        <ul>
          <li><span class="scope-mark">&#10003;</span><span><b>연주 순서 배치</b> &middot; 오프닝부터 피날레까지 흐름, 곡 사이 전환 시간, 중간 휴식, 종료 시각 계산</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>사회자 대본</b> &middot; 곡과 작곡가, 학생 메모를 엮은 곡별 멘트</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>인쇄물 32종 &times; 테마 40종</b> &middot; 포스터부터 좌석 배치도, 진행 문서까지</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>모바일 초대장과 참석 집계</b> &middot; 링크 하나로 인원이 저절로 쌓입니다</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>리허설 소집 &middot; 참가비 &middot; 좌석</b> 계산과 안내 문자</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>시즌 특강 기획</b> &middot; 할로윈 &middot; 크리스마스 &middot; 방학 4주 커리큘럼과 활동지</span></li>
        </ul>
      </div>
      <div class="scope-col no reveal" style="--d:0.15s">
        <h3>드리지 않는 것</h3>
        <ul>
          <li><span class="scope-mark">&#10005;</span><span><b>악보</b> &middot; 교재와 편곡본은 저작권이 있습니다. <b>학원에서 쓰시던 악보를 그대로</b> 쓰십니다</span></li>
          <li><span class="scope-mark">&#10005;</span><span><b>음원 &middot; 반주</b> &middot; 같은 이유입니다</span></li>
          <li><span class="scope-mark">&#10005;</span><span><b>곡 선정</b> &middot; 어떤 아이가 어떤 곡을 칠지는 원장님이 정하십니다</span></li>
          <li><span class="scope-mark">&#10005;</span><span><b>대관 &middot; 인쇄 대행</b> &middot; 지역마다 다르고 직접 하시는 편이 쌉니다. 대신 <b>예산표에 통상 단가</b>를 넣어 두었습니다</span></li>
          <li><span class="scope-mark">&#10005;</span><span><b>원비 &middot; 출결 관리</b> &middot; 쓰시던 학원 프로그램과 겹치지 않습니다</span></li>
        </ul>
        <p class="scope-why">이 프로그램은 <b>정해진 곡을 받아서</b> 순서 &middot; 시간 &middot; 멘트 &middot; 인쇄물을 만드는 도구입니다.
        곡 제목과 작곡가만 글자로 넣으시면, 곡 해설은 알아서 붙습니다.</p>
      </div>
    </div>
  </div>
</section>

<!-- ── 명단은 어떻게 넣는가 ─────────────────────────── -->
<section class="guide">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">09 /</span> 학생 명단은 어떻게 넣나요</p>
    <h2 class="reveal" style="--d:0.1s">이미 가지고 계신 것을<br>그대로 씁니다</h2>
    <div class="flow">
      <div class="flow-step reveal">
        <p class="t">CASE 1</p>
        <h4>엑셀에 명단이 있다</h4>
        <p>표를 통째로 복사해 붙여넣습니다. 열 순서가 달라도, 시간이 <b>3:30</b>이든 <b>3분 30초</b>든 알아서 읽습니다.</p>
        <span class="time">30초</span>
      </div>
      <div class="flow-step reveal" style="--d:0.12s">
        <p class="t">CASE 2</p>
        <h4>작년에도 이걸로 했다</h4>
        <p><b>[지난 행사에서 명단 가져오기]</b> 한 번이면 이름과 난이도가 그대로 옵니다. 곡만 채우시면 됩니다.</p>
        <span class="time">1분</span>
      </div>
      <div class="flow-step reveal" style="--d:0.24s">
        <p class="t">CASE 3</p>
        <h4>종이에만 있다</h4>
        <p>화면에서 한 명씩 추가합니다. 소요시간이나 작곡가를 비워도 됩니다 &mdash; 난이도로 추정합니다.</p>
        <span class="time">12명 5분</span>
      </div>
    </div>
    <div class="notice reveal" style="--d:0.36s">
      <p class="n-title">&#128247; 학원 사진과 로고는 끌어다 놓기만 하면 됩니다</p>
      <p>설정 화면의 <strong>이미지 보관함</strong>에 로고 &middot; 학원 상징 &middot; 사진을 한 번만 올려 두시면,
      포스터 &middot; 순서지 &middot; 초대장 &middot; 홍보물 &middot; 행사 당일 인쇄물 &middot; 진행 문서 <strong>어디에서든 클릭 한 번으로</strong> 들어갑니다.
      휴대폰으로 찍은 큰 사진도 인쇄에 맞는 크기로 자동으로 줄여 줍니다.
      테마마다 로고가 동그랗게 잘리거나 금테가 붙고, 사진이 아치형으로 잘리는 등 <strong>모양은 알아서 맞춰집니다.</strong>
      사진 주소를 다시 찾을 일이 없습니다.</p>
    </div>
  </div>
</section>

<!-- ── 다른 방법과 비교 ─────────────────────────────── -->
<section class="usp">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">10 /</span> 지금 쓰시는 방법과 비교하면</p>
    <h2 class="reveal" style="--d:0.1s">디자인 도구도, 관리 프로그램도<br><span class="accent">연주회를 알지는 못합니다</span></h2>
    <div class="cmp-wrap reveal" style="--d:0.2s">
      <table class="cmp">
        <thead>
          <tr>
            <th></th>
            <th>한글 &middot; 엑셀</th>
            <th>캔바 &middot; 미리캔버스</th>
            <th>디자인 외주</th>
            <th class="ours">피아노 이벤트</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th>순서 배치</th>
            <td>손으로 끌어 옮기며 고민</td>
            <td>기능 없음</td>
            <td>원장님이 정해서 전달</td>
            <td class="ours">난이도 기준 자동 배치</td>
          </tr>
          <tr>
            <th>러닝타임</th>
            <td>계산기로 더하기</td>
            <td>기능 없음</td>
            <td>기능 없음</td>
            <td class="ours">전환 &middot; 휴식 포함 자동</td>
          </tr>
          <tr>
            <th>순서가 바뀌면</th>
            <td>시각을 전부 다시 계산</td>
            <td>모든 장을 다시 수정</td>
            <td>다시 연락 &middot; 추가 비용</td>
            <td class="ours">32종이 함께 즉시 변경</td>
          </tr>
          <tr>
            <th>학생 이름 입력</th>
            <td>양식마다 반복</td>
            <td>양식마다 반복 타이핑</td>
            <td>파일로 전달</td>
            <td class="ours">한 번 &rarr; 32종에 자동</td>
          </tr>
          <tr>
            <th>사회자 대본</th>
            <td>밤새 타이핑</td>
            <td>기능 없음</td>
            <td>별도</td>
            <td class="ours">곡별 자동 생성</td>
          </tr>
          <tr>
            <th>참석 집계</th>
            <td>단톡방 답장 세기</td>
            <td>기능 없음</td>
            <td>기능 없음</td>
            <td class="ours">링크 회신으로 자동</td>
          </tr>
          <tr>
            <th>리허설 &middot; 좌석</th>
            <td>손으로 계산</td>
            <td>기능 없음</td>
            <td>기능 없음</td>
            <td class="ours">조별 시각 &middot; 좌석 자동</td>
          </tr>
          <tr>
            <th>비용</th>
            <td>무료 (시간 15~25시간)</td>
            <td>월 구독</td>
            <td>포스터 1장 5~15만원</td>
            <td class="ours">연 1회 결제 &middot; 행사 무제한</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="notice reveal" style="--d:0.3s">
      <p class="n-title">&#127911; 진짜 차이는 한 가지입니다</p>
      <p>다른 도구들은 <strong>디자인 도구</strong>이거나 <strong>관리 도구</strong>입니다.
      이것은 <strong>연주회 하나를 처음부터 끝까지 아는 도구</strong>입니다.
      명단 하나가 순서 &rarr; 시각 &rarr; 멘트 &rarr; 인쇄물 &rarr; 리허설 &rarr; 좌석 &rarr; 참가비로 전부 흘러가고,
      <strong>한 곳을 고치면 전부 따라 바뀝니다.</strong></p>
    </div>
  </div>
</section>

<!-- ── 06 이런 원장님께 ─────────────────────────────── -->
<section class="recommend">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">11 /</span> 이런 원장님께 추천합니다</p>
    <h2 class="reveal" style="--d:0.1s">올해 연주회는<br><span class="accent">준비가 아니라 무대</span>에 집중하세요</h2>
    <div class="pill-list">
      <div class="pill reveal"><span class="icon check">&#10003;</span><span>연주회 시즌마다 순서표와 대본 때문에 밤을 새우는 원장님</span></div>
      <div class="pill reveal" style="--d:0.12s"><span class="icon check">&#10003;</span><span>포스터 &middot; 순서지 디자인을 매번 외주로 맡기고 계신 원장님</span></div>
      <div class="pill reveal" style="--d:0.24s"><span class="icon check">&#10003;</span><span>참석 인원을 단톡방 답장으로 세다 좌석이 어긋난 적 있는 원장님</span></div>
      <div class="pill reveal" style="--d:0.36s"><span class="icon check">&#10003;</span><span>컴퓨터가 어려워 지금까지 손과 종이로 준비해 오신 원장님</span></div>
    </div>
  </div>
</section>

<!-- ── 최종 CTA ─────────────────────────────────────── -->
<section class="cta">
  <span class="note-deco n1">&#9834;</span>
  <span class="note-deco n2">&#9835;</span>
  <div class="inner">
    <p class="eyebrow reveal">ACCELSSAM &nbsp;&middot;&nbsp; 피아노 이벤트 솔루션</p>
    <h2 class="reveal" style="--d:0.1s">사흘 걸리던 준비를<br><span class="gold">30분</span>으로 끝내세요</h2>
    <p class="sub reveal" style="--d:0.2s">순서표 &middot; 사회자 대본 &middot; 인쇄물 &middot; 초대장 &middot; 참석 집계 &middot; 당일 진행표까지 한 자리에서.</p>
    <div class="reveal" style="--d:0.3s">
      <a class="cta-btn" href="https://accelssam.com/cart/?add-to-cart=2089" target="_top">피아노 이벤트 솔루션 시작하기</a>
      <div class="btn-row" style="justify-content:center">
        <a class="try-btn" href="https://claude.ai/code/artifact/f2def9cb-d28e-4cb0-beee-a315c02828bb" target="_blank" rel="noopener">먼저 눌러 보고 결정하기 &nbsp;&rarr;</a>
      </div>
    </div>
    <p class="period reveal" style="--d:0.4s">이용 기간: 결제 후 1년간 &middot; 행사 수 제한 없음</p>
  </div>
</section>
"""

SCRIPT = """
<script>
/* 스크롤 등장 애니메이션 (JS 미지원 환경에서는 애니메이션 없이 모두 표시됨) */
document.documentElement.classList.add('js');
(function(){
  var els = document.querySelectorAll('.reveal');
  if(!('IntersectionObserver' in window)){
    Array.prototype.forEach.call(els, function(el){el.classList.add('in');});
    return;
  }
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting){
        e.target.classList.add('in');
        io.unobserve(e.target);
      }
    });
  }, {threshold:0.12, rootMargin:'0px 0px -6% 0px'});
  Array.prototype.forEach.call(els, function(el){io.observe(el);});
  /* 어떤 이유로든 관찰이 걸리지 않은 요소가 남으면 3초 뒤 그냥 보여 준다 */
  setTimeout(function(){
    Array.prototype.forEach.call(document.querySelectorAll('.reveal:not(.in)'), function(el){el.classList.add('in');});
  }, 3000);
})();

/* 상품 설명 iframe 높이 자동 조절 */
(function(){
  function send(){
    var h = Math.max(
      document.body.scrollHeight, document.documentElement.scrollHeight,
      document.body.offsetHeight, document.documentElement.offsetHeight
    );
    if(window.parent !== window){
      window.parent.postMessage({type:'accel-piano-event-height', height:h}, '*');
    }
  }
  window.addEventListener('load', function(){ send(); setTimeout(send, 400); setTimeout(send, 1200); });
  window.addEventListener('resize', send);
  if('ResizeObserver' in window){ new ResizeObserver(send).observe(document.body); }
  setInterval(send, 1500);
})();
</script>
</body>
</html>
"""

html = (
    '<!DOCTYPE html>\n<html lang="ko">\n<head>\n'
    '<meta charset="UTF-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    '<title>피아노 이벤트 솔루션 | 연주회 준비 30분 컷 · 아첼쌤</title>\n'
    '<meta name="description" content="학생 명단만 넣으면 연주 순서표·사회자 대본·포스터·초대장·참석 집계·당일 진행표까지. 피아노학원 연주회 올인원 솔루션.">\n'
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=Noto+Serif+KR:wght@600;700;900&display=swap" rel="stylesheet">\n'
    '<style>' + style + EXTRA_CSS + '</style>\n'
    '</head>\n<body>\n' + BODY + SCRIPT
)

for key, uri in IMG.items():
    html = html.replace('__' + key + '__', uri)

out = ROOT / 'detail' / 'piano-event-detail.html'
out.write_text(html)
print('written', out, round(out.stat().st_size / 1024), 'KB')
