import base64, pathlib, re

ROOT = pathlib.Path('/home/user/-/pianoevent-ai')
# 스킬이 동기화되는 경로는 계정마다 다르고 가끔 바뀐다 — 찾아서 쓴다
def _template():
    roots = [pathlib.Path.home() / '.claude/skills', pathlib.Path('/root/.claude/skills')]
    for root in roots:
        for found in sorted(root.glob('**/accelssam-detail-page/template.html')):
            if '.trash' in str(found):
                continue
            return found.read_text()
    raise SystemExit('accelssam-detail-page 스킬의 template.html 을 찾지 못했습니다.')


TPL = _template()

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
    'STAGE_SCREEN': 'stage-screen.jpg',
    'STAGE_PERFORMANCE': 'stage-performance.jpg',
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
    /* 진행표처럼 한 장을 넘치는 문서는 그림이 더 길다 — 위쪽 기준으로 맞춘다 */
    align-items:start;
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

  /* ── 무대 화면 ─────────────────────────── */
  .stage-shots{
    display:grid;gap:clamp(1rem,2.5vw,1.6rem);
    margin-top:clamp(1.8rem,4vw,2.6rem);
  }
  @media (min-width:760px){.stage-shots{grid-template-columns:1fr 1fr;}}
  .stage-shot img{
    display:block;width:100%;height:auto;border-radius:8px;
    border:1px solid rgba(160,124,44,0.28);
    box-shadow:0 14px 34px rgba(30,20,8,0.28);
    background:#2A2118;
  }
  .stage-shot p{
    margin-top:0.75em;text-align:center;
    font-size:clamp(0.94rem,0.9rem + 0.2vw,1.04rem);
    color:var(--ink-soft);
  }
  .stage-shot p b{display:block;color:var(--ink);font-weight:700;margin-bottom:0.15em;}
  .stage-keys{
    display:flex;flex-wrap:wrap;gap:.5rem;justify-content:center;
    margin-top:1.4rem;
  }
  .stage-keys span{
    padding:.45em 1em;border-radius:999px;
    border:1px solid rgba(120,100,70,.3);background:#FBF6EA;
    font-size:.86rem;
  }

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
        <div class="stat"><p class="v">59종</p><p class="k">인쇄물 양식</p></div>
        <div class="stat"><p class="v">108종</p><p class="k">디자인 테마</p></div>
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
      <div><p class="v">59종</p><p class="k">인쇄물 양식</p></div>
      <div><p class="v">108종</p><p class="k">디자인 테마</p></div>
      <div><p class="v">3곳</p><p class="k">아이 사진 한 번 →<br>화면 · PPT · 영상</p></div>
    </div>

    <div class="feat-grid">
      <div class="feat reveal">
        <p class="n">01 &nbsp;곡 사전</p>
        <h4>곡 제목만 치면 나머지가 따라옵니다</h4>
        <p>학원 연주회에 실제로 오르는 78곡 &mdash; 부르크뮐러부터 히사이시 조까지. 곡을 고르면
        <b>작곡가 &middot; 난이도 &middot; 연주시간</b>이 함께 들어가고, 사회자 멘트에 쓸 <b>곡 해설</b>까지 준비됩니다.</p>
        <p class="only">엑셀에도 캔바에도 없는 것</p>
      </div>
      <div class="feat reveal" style="--d:0.07s">
        <p class="n">02 &nbsp;순서 자동 배치</p>
        <h4>흐름과 시각을 동시에 계산합니다</h4>
        <p>오프닝 &rarr; 초급 &rarr; 중급 &rarr; 앙상블 &rarr; 피날레. 곡 사이 전환 시간과 중간 휴식까지 넣어
        <b>몇 시에 끝나는지</b>를 알려 줍니다. 마음에 안 드는 곳은 <b>위·아래 버튼으로 직접</b> 옮깁니다.</p>
        <p class="only">바꾸면 59종이 함께 바뀜</p>
      </div>
      <div class="feat reveal" style="--d:0.14s">
        <p class="n">03 &nbsp;사회자 대본</p>
        <h4>곡마다 멘트가 쓰여 있습니다</h4>
        <p>곡 &middot; 작곡가 &middot; 학생 메모를 엮어 오프닝부터 클로징까지. 무대 옆은 어두우니
        <b>큰 글씨 인쇄</b>로 나갑니다.</p>
        <p class="only">밤새 쓰던 그 문장</p>
      </div>
      <div class="feat reveal" style="--d:0.21s">
        <p class="n">04 &nbsp;순서표 점검</p>
        <h4>당일 전화를 부르는 것들을 미리 잡습니다</h4>
        <p>같은 곡 중복, 형제자매가 멀리 떨어짐, 어린 학생이 맨 뒤, 같은 작곡가 3연속,
        휴식 없이 70분 초과 &mdash; <b>8가지를 3등급으로</b> 알려 주고 고치는 법까지 적어 줍니다.</p>
        <p class="only">사람이 놓치는 것</p>
      </div>
      <div class="feat reveal" style="--d:0.28s">
        <p class="n">05 &nbsp;인쇄물</p>
        <h4>양식 59종 &times; 테마 108종</h4>
        <p>포스터 7 &middot; 프로그램 5 &middot; 초대·홍보 6 &middot; 행사 당일 12 &middot; 진행 문서 10.
        테마 하나를 고르면 <b>전부 같은 색과 서체</b>를 입습니다. 한 벌 인쇄로 여러 장을 한 번에.</p>
        <p class="only">외주비 0원</p>
      </div>
      <div class="feat reveal" style="--d:0.35s">
        <p class="n">06 &nbsp;모바일 초대장</p>
        <h4>링크 하나로 참석 인원이 쌓입니다</h4>
        <p>단톡방에 올리면 학부모가 눌러 회신하고, <b>가정 수 &middot; 총원 &middot; 응원 메시지</b>가 저절로
        모입니다. 그 인원이 그대로 좌석 배치로 넘어갑니다.</p>
        <p class="only">답장 세지 않아도 됨</p>
      </div>
      <div class="feat reveal" style="--d:0.42s">
        <p class="n">07 &nbsp;무대 화면</p>
        <h4>명단만 넣으면 연주회 PPT가 나옵니다</h4>
        <p>해마다 파워포인트로 다시 만들던 그 화면입니다. 명단을 넣으면 <b>16:9 슬라이드가 통째로</b> 만들어져
        대기 화면 &middot; 오늘의 순서 &middot; 연주자별 화면 &middot; 폐회 인사까지 이어집니다.
        <b>테마 108종</b>을 그 자리에서 바꿔 보고, <b>진짜 .pptx 파일</b>로 받으면 파워포인트에서 바로 고칩니다.</p>
        <p class="only">순서를 바꾸면 PPT도 바뀜</p>
      </div>
      <div class="feat reveal" style="--d:0.49s">
        <p class="n">08 &nbsp;아이 사진</p>
        <h4>한 번 넣으면 세 곳에 들어갑니다</h4>
        <p>명단에 사진을 넣으면 <b>무대 화면 &middot; 파워포인트 &middot; 감동영상</b>에 함께 올라갑니다.
        30명이라도 <b>파일 이름으로 한꺼번에</b> 짝지어 줍니다. 사진이 없는 아이는 이름만 크게 나옵니다.</p>
        <p class="only">빈 상자를 찍지 않음</p>
      </div>
      <div class="feat reveal" style="--d:0.56s">
        <p class="n">09 &nbsp;감동영상</p>
        <h4>무비메이커를 열지 않습니다</h4>
        <p>연습 사진 &middot; 동영상 &middot; 배경음악을 고르면 한 편이 만들어집니다. 장면 순서와 이름 자막은
        <b>명단에서 이미 알고 있으므로</b> 짜 드립니다. 브라우저 안에서 만들어 바로 내려받습니다.</p>
        <p class="only">사진이 컴퓨터 밖으로 안 나감</p>
      </div>
      <div class="feat reveal" style="--d:0.63s">
        <p class="n">10 &nbsp;리허설 시간표</p>
        <h4>조 단위 소집 시각과 문자까지</h4>
        <p>전원을 한 번에 부르면 대기실이 터집니다. 5명씩 묶어 <b>조별 도착 시각</b>을 계산하고
        조마다 보낼 <b>문자를 만들어</b> 둡니다. 문자 30통이 6통이 됩니다.</p>
        <p class="only">당일 아침의 계산</p>
      </div>
      <div class="feat reveal" style="--d:0.70s">
        <p class="n">11 &nbsp;참가비 계산</p>
        <h4>대관료 확정 전에도 안내가 나갑니다</h4>
        <p>항목 10가지 예산에서 <b>1인당 원가와 권장 참가비</b>를 역산합니다. 선택 항목을 끄면 즉시
        다시 계산되고, <b>안내 문구</b>까지 복사해 보냅니다.</p>
        <p class="only">감으로 정하지 않음</p>
      </div>
      <div class="feat reveal" style="--d:0.77s">
        <p class="n">12 &nbsp;좌석 배치</p>
        <h4>가족은 붙여 앉히고 앞줄은 비웁니다</h4>
        <p>참석 회신을 <b>가정 단위</b>로 앉히고 앞 두 줄은 연주자석으로 둡니다.
        <b>&ldquo;3열 4~6번&rdquo;</b>처럼 학부모에게 그대로 보낼 수 있는 표기로 나옵니다.</p>
        <p class="only">접수처에 붙이면 끝</p>
      </div>
      <div class="feat reveal" style="--d:0.84s">
        <p class="n">13 &nbsp;이미지 보관함</p>
        <h4>사진을 끌어다 놓으면 전부에 들어갑니다</h4>
        <p>로고 &middot; 학원 상징 &middot; 사진을 한 번만 올리면 됩니다. 휴대폰 사진도 <b>인쇄 크기로 자동 축소</b>,
        테마마다 <b>모양은 알아서</b> 맞춰집니다. 포스터엔 단체사진, 표지엔 학원 전경처럼 따로 지정도 됩니다.</p>
        <p class="only">주소 다시 찾을 일 없음</p>
      </div>
      <div class="feat reveal" style="--d:0.91s">
        <p class="n">14 &nbsp;준비 체크리스트</p>
        <h4>D-30부터 종료 후까지</h4>
        <p>30가지 할 일이 <b>행사 날짜에 맞춰</b> 날짜와 함께 나옵니다. 학부모 안내 문자 4종도
        시기별로 준비돼 있습니다.</p>
        <p class="only">빠뜨릴 수가 없음</p>
      </div>
      <div class="feat reveal" style="--d:0.98s">
        <p class="n">15 &nbsp;시즌 특강</p>
        <h4>할로윈 &middot; 크리스마스 &middot; 방학</h4>
        <p>테마를 고르면 <b>4주 커리큘럼과 인쇄용 활동지</b>가 나옵니다. 연주회가 없는 달에도
        학원이 돌아갑니다.</p>
        <p class="only">자료 사서 짜깁기 안 함</p>
      </div>
      <div class="feat reveal" style="--d:1.05s">
        <p class="n">16 &nbsp;지난 행사에서 가져오기</p>
        <h4>작년 명단을 1분 만에 되살립니다</h4>
        <p>학원은 학생이 그대로입니다. <b>이름과 난이도는 그대로</b> 가져오고 곡만 비워 줍니다.
        해마다 20~30명을 다시 치던 일이 클릭 한 번이 됩니다.</p>
        <p class="only">두 번째 연주회부터가 진짜</p>
      </div>
      <div class="feat reveal" style="--d:1.12s">
        <p class="n">17 &nbsp;당일 진행 화면</p>
        <h4>휴대폰에 &ldquo;지금 몇 번째, 다음은 누구&rdquo;</h4>
        <p>무대 옆에 선 사람이 종이 순서표를 손가락으로 짚지 않아도 됩니다. <b>지금 &middot; 다음 &middot; 그다음</b>이
        크게 뜨고, 한 곡이 끝나면 단추 하나로 넘깁니다. <b>예정보다 몇 분 밀렸는지</b>도 함께 —
        많이 밀리면 화면이 붉어집니다. 새로고침해도 자리를 잃지 않습니다.</p>
        <p class="only">그때 멘트를 줄이면 됨</p>
      </div>
      <div class="feat reveal" style="--d:1.19s">
        <p class="n">18 &nbsp;스태프와 함께 보기</p>
        <h4>무대 옆에서 넘기면 대기실 화면도 넘어갑니다</h4>
        <p>무전기로 &ldquo;지금 몇 번째냐&rdquo; 묻지 않아도 됩니다. 넘기시는 분이 <b>[함께 보기]</b>를 켜면
        대기실 &middot; 접수처 스태프는 <b>로그인 없이</b> 링크 하나로 같은 화면을 봅니다. 넘기는 사람은 한 명이고,
        연결이 끊겨도 넘기시는 분 화면은 그대로 돌아갑니다.</p>
        <p class="only">인터넷 끊겨도 진행은 계속</p>
      </div>
      <div class="feat reveal" style="--d:1.26s">
        <p class="n">19 &nbsp;실제 시간 되먹임</p>
        <h4>다음 해 종료 시각이 정확해집니다</h4>
        <p>예상 연주 시간은 책에 적힌 평균입니다. 그런데 그 학원 아이들은 그보다 빠르거나 느립니다.
        당일에 넘기신 시각이 쌓여 <b>곡마다 실제로 몇 분 걸렸는지</b>가 남고, 단추 하나로 명단에 반영됩니다.
        <b>리허설에서 한 번 돌려 두시면</b> 당일 전에 이미 정확해집니다.</p>
        <p class="only">두 번째 해부터 진짜</p>
      </div>
      <div class="feat reveal" style="--d:1.33s">
        <p class="n">20 &nbsp;당일 사진 모으기</p>
        <h4>리허설에서 찍어 그날 저녁 영상에</h4>
        <p>사진은 컴퓨터 앞에 앉아야 넣을 수 있었습니다. 이제 <b>휴대폰으로</b> 아이 이름을 누르고
        찍으면 바로 들어갑니다. 맨 위에 <b>&ldquo;12명 중 8명&rdquo;</b> 처럼 떠서 리허설이 끝날 때쯤
        누가 빠졌는지 보입니다.</p>
        <p class="only">사진은 휴대폰 밖으로 안 나감</p>
      </div>
      <div class="feat reveal" style="--d:1.40s">
        <p class="n">21 &nbsp;프로그램 안 사용설명서</p>
        <h4>막히면 위쪽 &ldquo;사용설명서&rdquo;</h4>
        <p>설명서가 프로그램 밖에 있으면 못 찾습니다. <b>머리띠에서 한 번</b>이면 열립니다.
        찾는 칸에 &ldquo;명단&rdquo; 한 낱말만 치면 그 대목만 남고, <b>한 부 인쇄</b>해 두시면 컴퓨터를
        켜지 않고도 보십니다. 명단 <b>양식 파일</b>도 여기서 받습니다.</p>
        <p class="only">첫 화면에서 막히지 않게</p>
      </div>
      <div class="feat reveal" style="--d:1.47s">
        <p class="n">22 &nbsp;인터넷 &middot; AI 키 없이</p>
        <h4>이 컴퓨터 안에서 전부 만들어집니다</h4>
        <p>AI 키를 넣지 않아도 순서표 &middot; 대본 &middot; 인쇄물 &middot; 무대 화면이 전부 나옵니다.
        학생 이름과 사진은 <b>학원 컴퓨터 밖으로 나가지 않습니다.</b>
        인터넷이 필요한 것은 <b>학부모가 초대장 링크를 여는 것</b>뿐입니다.</p>
        <p class="only">설정 화면에서 지금 상태를 보여 줌</p>
      </div>
    </div>
  </div>
</section>

<!-- ── 명단 넣기는 이렇게 ────────────────────────────── -->
<section class="usp">
  <div class="inner">
    <p class="eyebrow reveal">시작 &middot; 명단 넣기</p>
    <h2 class="reveal" style="--d:0.1s">양식 파일에<br><span class="accent">이름만 바꿔</span> 넣으시면 됩니다</h2>
    <p class="lead reveal" style="--d:0.15s">
      가장 많이 막히시는 자리라 세 가지를 한자리에 두었습니다 &mdash;
      <b>예시가 채워진 엑셀 파일</b>, 칸마다 무엇을 적는지, 자주 하는 실수까지.
    </p>
    <div class="list reveal" style="--d:0.2s">
      <div class="item"><span class="mk">✓</span><span><b>[명단 양식 내려받기]</b> &mdash; 엑셀에서 바로 열립니다 (한글 안 깨집니다)</span></div>
      <div class="item"><span class="mk">✓</span><span>예시 줄을 <b>우리 아이들 이름으로</b> 바꾸고 표를 통째로 복사</span></div>
      <div class="item"><span class="mk">✓</span><span>프로그램에 붙여넣고 <b>[명단에 추가]</b> &mdash; 끝입니다</span></div>
      <div class="item"><span class="mk">✓</span><span><b>이름 한 칸</b>만 있으면 됩니다. 나머지는 비워 두셔도 됩니다</span></div>
      <div class="item"><span class="mk">✓</span><span>작곡가 &middot; 연주시간을 비우면 <b>곡 사전이 알아서</b> 채웁니다</span></div>
      <div class="item"><span class="mk">✓</span><span>머리글이 없어도, 사이에 빈 줄이 있어도 <b>알아서 읽습니다</b></span></div>
    </div>
    <p class="lead reveal" style="--d:0.25s">
      두 번째 해부터는 <b>[지난 행사에서 명단 가져오기]</b> 한 번이면 됩니다 &mdash;
      이름 &middot; 난이도 &middot; <b>아이 사진</b>까지 그대로 따라옵니다.
    </p>
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
        <span>당일 진행표</span><span>무대 화면</span><span>참가비</span><span>예산표</span><span>학부모 안내문</span>
      </div>
      <p class="last">순서 하나를 바꾸면 &mdash; 위의 <b>59종이 동시에</b> 다시 만들어집니다</p>
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
        <p><b>당일 진행표</b>도착 &middot; 리허설 &middot; 객석 개방 &middot; 연주 &middot; 시상까지 분 단위로. 내용이 길면 다음 장으로 이어집니다</p>
      </div>
    </div>

    <div class="notice reveal">
      <p class="n-title">&#9989; 한 벌 인쇄</p>
      <p>양식을 하나씩 고르실 필요 없습니다. <strong>관객용 한 벌</strong>(포스터 &middot; 표지 &middot; 순서지 &middot; 입장권)과 <strong>당일 운영 한 벌</strong>(진행표 &middot; 체크리스트 &middot; 이름표)을 버튼 하나로 한 번에 뽑습니다.</p>
    </div>
  </div>
</section>

<!-- ── 07 무대 화면 ─────────────────────────────────── -->
<section class="guide">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">07 /</span> 연주회 당일 스크린</p>
    <h2 class="reveal" style="--d:0.1s">해마다 만들던 파워포인트,<br><span class="accent">이제 안 만드셔도 됩니다</span></h2>
    <p class="sub reveal" style="--d:0.18s"><strong>학생 명단을 넣는 순간</strong> 그 명단으로 된
    <strong>16:9 슬라이드</strong>가 통째로 만들어집니다. 노트북을 빔프로젝터나 TV에 연결하고 [전체화면]을 누르면 끝이고,
    <strong>진짜 파워포인트 파일(.pptx)</strong>로 받아 직접 고칠 수도 있습니다.</p>

    <div class="stage-shots">
      <div class="stage-shot reveal">
        <img src="__STAGE_SCREEN__" alt="연주회장 스크린 대기 화면 - 학원 로고와 행사 제목">
        <p><b>입장 대기 화면</b>개회 전까지 띄워 두는 화면. 학원 로고와 안내 문구가 들어갑니다</p>
      </div>
      <div class="stage-shot reveal" style="--d:0.12s">
        <img src="__STAGE_PERFORMANCE__" alt="연주자 소개 화면 - 이름, 곡, 작곡가, 곡 해설">
        <p><b>연주자 화면</b>이름 &middot; 곡 &middot; 작곡가 &middot; 곡 해설이 뒷줄에서도 읽히는 크기로</p>
      </div>
    </div>

    <div class="stage-keys reveal" style="--d:0.2s">
      <span>&rarr; &larr; 화살표로 넘기기</span>
      <span>스페이스 &middot; 화면 클릭</span>
      <span>프레젠터(리모컨) 그대로</span>
      <span>F 전체화면</span>
      <span>어두운 공연장용 검은 화면</span>
      <span>테마 108종 즉시 변경</span>
      <span>.pptx 내려받기</span>
      <span>연주자 화면 모양 8종</span>
      <span>사진 창 모양 8종</span>
      <span>무대 배경 10종</span>
    </div>

    <div class="notice reveal" style="--d:0.24s">
      <p class="n-title">&#127929; 이름이 피아노에 가리지 않습니다</p>
      <p>연주회장에서 늘 겪는 두 가지를 규칙으로 박았습니다.
      <strong>아이 이름을 화면 아래에 두면 그랜드피아노 뚜껑에 가려</strong> 객석에서 읽히지 않습니다.
      그래서 모든 화면이 글자를 <strong>위쪽이나 오른쪽에만</strong> 놓습니다.
      그리고 <strong>사진은 화면을 꽉 채웁니다</strong> &mdash; 둘레에 빈 자리를 남기지 않습니다.</p>
      <p style="margin-top:.7em">모양은 <strong>8종</strong>입니다 &mdash;
      배경 위 사진 액자 &middot;
      사진 반쪽 &middot; 사진 전체+오른쪽 판 &middot; 사진 전체+위쪽 띠 &middot; 사진 전체+큰 번호 &middot;
      <strong>사진 없이</strong> 이름만 크게 &middot; 큰 번호+이름 &middot; 이름·곡·해설 카드.
      <strong>사진을 넣지 않은 아이는 글자 모양으로 알아서 내려갑니다</strong> &mdash; 빈 상자가 뜨지 않습니다.</p>
    </div>

    <div class="notice reveal" style="--d:0.26s">
      <p class="n-title">&#127900; 단색 배경만 있는 게 아닙니다</p>
      <p>아이 사진을 담는 창을 <strong>8가지 모양</strong>에서 고릅니다 &mdash;
      원형 &middot; 둥근 사각 &middot; 사각 &middot; 아치 &middot; 타원 &middot; 육각 &middot; 나뭇잎 &middot; 마름모.</p>
      <p style="margin-top:.7em">배경도 <strong>10가지</strong>입니다 &mdash; 단색 &middot; <strong>피아노 건반</strong> &middot;
      <strong>무대 커튼</strong> &middot; 무대 조명 &middot; 악보 &middot; 조명 방울 &middot;
      <strong>그랜드피아노</strong> &middot; 별밤 &middot; 리본 띠 &middot; 아치 무대.
      배경은 사진이 아니라 <strong>그려 넣는 그림</strong>이라 인터넷 없이 뜨고, 크게 띄워도 흐려지지 않으며,
      <strong>고른 테마의 색을 그대로</strong> 입습니다. 파워포인트로 받아도 배경이 함께 갑니다.</p>
    </div>

    <div class="notice reveal" style="--d:0.28s">
      <p class="n-title">&#9989; 명단이 곧 PPT입니다</p>
      <p>슬라이드를 한 장씩 만들지 않습니다. <strong>학생 12명을 넣으면 슬라이드 20장</strong>이 그 자리에서 나옵니다.
      순서를 바꾸면 대기 화면 &middot; 오늘의 순서 &middot; 연주자별 화면 &middot; 휴식 안내 &middot; 폐회 인사가
      <strong>전부 다시 만들어집니다.</strong> 파워포인트라면 20장을 손으로 옮겨야 하는 일입니다.</p>
    </div>

    <div class="notice reveal" style="--d:0.32s">
      <p class="n-title">&#127912; 테마 108종, 그 자리에서 바꿉니다</p>
      <p>인쇄물에 쓰던 <strong>테마 108종이 그대로</strong> 나옵니다. 행사 달에 어울리는 테마를 먼저 보여 주고,
      <strong>&ldquo;봄&rdquo; &ldquo;금색&rdquo; &ldquo;아이&rdquo;</strong> 처럼 이름으로 찾을 수도 있습니다.
      고르는 즉시 화면이 바뀌고, 포스터 &middot; 순서지 &middot; 스크린의 색과 서체가 어긋나지 않습니다.
      곡 해설 &middot; 오늘의 순서 &middot; 부 전환 화면은 <strong>켜고 끌 수 있습니다.</strong></p>
    </div>

    <div class="notice reveal" style="--d:0.36s">
      <p class="n-title">&#128190; 진짜 파워포인트 파일로 받습니다</p>
      <p>[파워포인트로 받기]를 누르면 <strong>.pptx 파일</strong>이 내려옵니다. 슬라이드가 그림이 아니라
      <strong>글상자</strong>라, 공연장에서 이름 하나를 고쳐야 해도 파워포인트에서 바로 고칩니다.
      고른 테마의 색과 서체가 그대로 들어가고, 글꼴은 윈도우에 늘 있는
      <strong>바탕 &middot; 맑은 고딕 &middot; 궁서</strong>로 맞춰 나가 깨지지 않습니다.
      그냥 넘기기만 할 거라면 <strong>PDF</strong>로 받으십시오. 둘 다 <strong>인터넷 없이</strong> 이 컴퓨터에서 만들어집니다.</p>
    </div>
  </div>
</section>

<!-- ── 08 아이 사진 · 감동영상 ──────────────────────── -->
<section class="usp">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">08 /</span> 아이 사진과 감동영상</p>
    <h2 class="reveal" style="--d:0.1s">이름만 뜨는 화면과<br><span class="accent">아이 얼굴이 뜨는 화면</span>은 다릅니다</h2>
    <p class="sub reveal" style="--d:0.18s">웃는 사진 한 장이 객석을 조용하게 만듭니다.
    사진은 <strong>명단에 한 번만</strong> 넣으면 무대 화면 &middot; 파워포인트 &middot; 감동영상에 <strong>전부</strong> 들어갑니다.</p>

    <div class="feat-grid">
      <div class="feat reveal">
        <p class="n">사진 넣기</p>
        <h4>파일 이름만 맞으면 한꺼번에</h4>
        <p>30명 사진을 한 장씩 고르실 필요 없습니다. <b>[사진 한꺼번에 올리기]</b> 를 누르고 폴더를 통째로 고르면,
        <b>파일 이름에 아이 이름이 들어 있는 것끼리 알아서 짝지어</b> 줍니다.
        <code>김서연.jpg</code>, <code>2026 윤채원 연습.jpg</code> 둘 다 걸립니다.</p>
        <p class="only">휴대폰 사진도 자동 축소</p>
      </div>
      <div class="feat reveal" style="--d:0.08s">
        <p class="n">무대 화면 &middot; PPT</p>
        <h4>연주자 화면이 얼굴과 함께 뜹니다</h4>
        <p>사진을 넣으면 <b>왼쪽에 얼굴, 오른쪽에 이름 &middot; 곡 &middot; 해설</b> 로 바뀝니다.
        내려받는 <b>.pptx 파일 안에도 그 사진이 실제 그림으로</b> 들어가, 파워포인트에서 바로 옮기고 키울 수 있습니다.
        사진이 없는 아이는 이름만 크게 나옵니다 &mdash; 빈 상자가 뜨지 않습니다.</p>
        <p class="only">넣고 빼기 한 번으로</p>
      </div>
      <div class="feat reveal" style="--d:0.16s">
        <p class="n">감동영상</p>
        <h4>무비메이커를 열지 않습니다</h4>
        <p><b>템플릿 10종</b>에서 고릅니다 &mdash; 사진이 화면을 꽉 채우는 것, 건반 &middot; 커튼 &middot; 조명 배경 위에
        액자로 얹는 것. 제목 화면으로 시작해 아이들 얼굴이 이어지고 끝인사로 닫힙니다.
        <b>문구 &middot; 순서 &middot; 시간 &middot; 글자 자리를 원장님이 직접 고칩니다.</b></p>
        <p class="only">사진 한 장씩 끌어다 놓지 않음</p>
      </div>
    </div>

    <div class="chain reveal" style="--d:0.2s">
      <span class="seed">아이 사진 한 장</span>
      <p class="arrow">&#9660;</p>
      <div class="chain-row">
        <span>무대 화면 연주자 슬라이드</span><span>파워포인트 .pptx</span><span>감동영상 장면</span>
      </div>
      <p class="last">한 번 넣으면 세 곳에 함께 들어갑니다</p>
    </div>

    <div class="notice reveal" style="--d:0.18s">
      <p class="n-title">&#9989; 고르실 것이 없습니다</p>
      <p>화면의 설정은 <strong>그대로 두셔도</strong> 좋은 영상이 나오게 맞춰 두었습니다.
      감동영상 화면을 여시면 <strong>&ldquo;이대로 만드셔도 됩니다&rdquo;</strong> 와 함께 이미 짜인
      장면이 그림으로 깔려 있고, 왼쪽 <strong>[영상 만들기]</strong> 하나만 누르시면 됩니다.
      테마 &middot; 길이 &middot; 로고 &middot; 구간 같은 것은 <strong>접혀 있습니다</strong> &mdash;
      바꾸고 싶으실 때만 펴시면 됩니다.</p>
    </div>

    <div class="notice reveal" style="--d:0.2s">
      <p class="n-title">&#127916; 영상 템플릿 10종</p>
      <p><strong>사진을 꽉 채우는 것 5종</strong> &mdash; 꽉 찬 사진 &middot; 위 자막 &middot; 극장 조명 &middot; 별밤 &middot; 감동 문구<br>
      <strong>배경 위에 액자로 얹는 것 5종</strong> &mdash; 건반 무대 &middot; 무대 커튼 &middot; 아치 무대 &middot;
      악보 위 사진 &middot; 조명 방울 반쪽</p>
      <p style="margin-top:.7em">무대 화면(스크린 &middot; PPT)에 쓰던 <strong>배경이 영상에도 그대로</strong> 나옵니다.
      템플릿마다 사진이 움직이는 방향도 다릅니다 &mdash; 다가가기 &middot; 물러나기 &middot; 옆으로 흐르기 &middot; 가만히.
      다만 원장님이 올린 <strong>동영상은 언제나 화면을 꽉</strong> 채웁니다 &mdash; 액자에 담으면 찍어 오신 영상이 작아지니까요.</p>
    </div>

    <div class="notice reveal" style="--d:0.22s">
      <p class="n-title">&#9998; 원장님이 직접 고치는 영상 편집기입니다</p>
      <p>자동으로 짜 드리는 것은 <strong>시작점</strong>일 뿐입니다. 콘티에서 장면을 누르면 바로 고칩니다.</p>
      <p style="margin-top:.7em"><strong>&middot; 문구</strong> &mdash; 아이 이름 대신 감동 문구를 넣으세요.
      큰 글씨 &middot; 작은 글씨 &middot; 맨 위 작은 글씨를 각각 씁니다<br>
      <strong>&middot; 순서</strong> &mdash; 화살표로 앞뒤로 옮깁니다<br>
      <strong>&middot; 머무는 시간</strong> &mdash; 중요한 장면은 길게<br>
      <strong>&middot; 글자 자리</strong> &mdash; 아래 &middot; 위 &middot; <strong>가운데 크게</strong> &middot; 글자 없이.
      아이 얼굴이 가려지면 옮기고, 감동 문구는 한가운데 크게</p>
      <p style="margin-top:.7em">사진과 동영상은 <strong>파일 이름 앞에 번호</strong>를 붙여 두면 그 차례대로 들어갑니다 &mdash;
      <code>01 입장.jpg</code> <code>02 리허설.jpg</code> <code>03 무대.mp4</code></p>
    </div>

    <div class="notice reveal" style="--d:0.24s">
      <p class="n-title">&#128065; 만들기 전에 전부 보여 드립니다</p>
      <p>몇 분을 기다린 뒤에 &ldquo;이게 아닌데&rdquo; 하는 일이 없도록, <strong>장면 하나하나를 그림으로 먼저</strong> 깔아 둡니다.
      표지부터 마무리까지 <strong>실제로 나올 그 화면</strong>이 그대로 뜹니다.
      사진을 넣지 않은 아이는 <strong>&ldquo;사진 없음&rdquo;</strong> 이라고 표시되니, 누가 빠졌는지 만들기 전에 아십니다.
      장면을 누르면 그 자리를 크게 보여 줍니다.</p>
    </div>

    <div class="notice reveal" style="--d:0.26s">
      <p class="n-title">&#9201; 확인은 빠르게, 영상은 학원 것으로</p>
      <p><strong>&middot; 빠른 미리보기</strong> &mdash; 3분짜리를 확인하려고 3분을 기다리지 않으셔도 됩니다.
      <strong>2배 &middot; 4배</strong> 로 돌려 전체를 훑고, 만들 때만 제 속도로 담습니다<br>
      <strong>&middot; 학원 로고</strong> &mdash; 네 귀퉁이 중 한 곳에 작게 넣습니다. 영상은 학부모 휴대폰을 돌아다니니까요<br>
      <strong>&middot; 설정 저장</strong> &mdash; 고른 템플릿 &middot; 테마 &middot; 길이 &middot; 문구를 행사에 저장해 두면
      다음 해에 <strong>&ldquo;작년 것 불러오기&rdquo;</strong> 한 번으로 그 화면이 그대로 열립니다.
      무대 화면(PPT)도 같습니다<br>
      <strong>&middot; 초대장에 붙이기</strong> &mdash; 만든 영상을 유튜브 일부공개에 올리고 주소를 붙여넣으면
      <strong>초대장 안에서 바로 재생</strong>됩니다. 단톡방에 링크 하나면 순서표도 영상도 함께 봅니다</p>
    </div>

    <div class="notice reveal" style="--d:0.27s">
      <p class="n-title">&#128248; 아이당 사진 여러 장 &middot; 학부모 응원 메시지</p>
      <p>한 아이가 3~4초 머무는데 사진이 한 장이면 정지 화면에 가깝습니다.
      명단에서 <strong>여러 장을 고르면</strong> 그 몇 초 동안 넘겨 가며 나옵니다 &mdash;
      한 장에 최소 1.4초는 머물도록 장면이 저절로 길어집니다.
      맨 앞 &#9312; 이 대표 사진이라 무대 화면과 파워포인트에는 그 한 장이 들어갑니다.</p>
      <p style="margin-top:.7em">초대장으로 참석 회신을 받으실 때 학부모님들이 남기신 <strong>응원 한 줄</strong>이
      회신함에만 쌓여 있었습니다. 이제 <strong>영상 마지막, 끝인사 앞에</strong> 흘러갑니다.
      시상식 전에 이 대목에서 객석이 조용해집니다.</p>
    </div>

    <div class="notice reveal" style="--d:0.285s">
      <p class="n-title">&#128100; 응원에 그 아이 얼굴이 함께</p>
      <p>학부모님이 회신에 적어 주신 <strong>아이 이름</strong>으로 그 아이 얼굴을 찾아
      응원 글 위에 동그랗게 띄웁니다. 누구 부모님 말인지 객석이 알아봅니다.</p>
      <p style="margin-top:.7em">사진은 <strong>한꺼번에</strong> 올리셔도 됩니다 &mdash;
      <code>김서연-1.jpg</code> <code>김서연-2.jpg</code> 처럼 번호를 붙이면 한 아이에 여러 장이
      그 차례대로 들어갑니다.</p>
    </div>

    <div class="notice reveal" style="--d:0.29s">
      <p class="n-title">&#9986; 끊겨도 처음부터 다시 만들지 않습니다</p>
      <p>8분짜리를 7분째에 창을 잘못 누르면 예전에는 다시 8분이었습니다.
      이제 <strong>[여기까지 만들고 멈추기]</strong>를 누르면 <strong>담긴 데까지 파일로</strong> 나옵니다.
      긴 영상은 <strong>몇 번째 장면부터 몇 번째까지</strong>를 골라 두세 토막으로 만들고
      <strong>[한 편으로 잇기]</strong>를 누르면 하나의 파일이 됩니다.</p>
      <p style="margin-top:.7em"><strong>솔직히 말씀드릴 것</strong> &mdash; 영상 파일은 그냥 이어 붙일 수
      없습니다. 앞머리에 전체 길이와 자리표가 들어 있어 바이트로 붙이면 재생기마다 다르게 굽니다.
      그래서 토막을 차례로 틀면서 <strong>다시 한 번 담습니다</strong> &mdash; 토막 길이의 합만큼
      걸리는 대신 나오는 것은 진짜 한 편입니다.</p>
    </div>

    <div class="notice reveal" style="--d:0.28s">
      <p class="n-title">&#128274; 아이들 사진은 컴퓨터 밖으로 나가지 않습니다</p>
      <p>사진을 어디에 올리는 것이 아닙니다. <strong>이 컴퓨터 안에서</strong> 크기를 줄여 보관하고,
      영상도 <strong>브라우저 안에서</strong> 만듭니다. 올리는 곳도, 기다리는 줄도, 계정도 없습니다.
      감동영상에 더한 연습 사진 &middot; 동영상 &middot; 음악은 <strong>아예 저장하지도 않습니다</strong> &mdash;
      영상을 만들 때만 쓰입니다. 그래서 <strong>만든 영상 파일도 저희가 보관하지 않습니다</strong> &mdash;
      초대장에 붙이실 때 어디에 올릴지는 원장님이 정하십니다.</p>
    </div>

    <div class="notice reveal" style="--d:0.32s">
      <p class="n-title">&#9200; 솔직히 말씀드릴 것</p>
      <p>영상은 화면을 그리면서 담기 때문에 <strong>영상 길이만큼 시간이 걸립니다</strong> &mdash; 3분짜리는 3분.
      (누르기 전에 화면에 <strong>&ldquo;만드는 데 약 ○분&rdquo;</strong> 이라고 적혀 있습니다.)
      만드는 동안 창을 그대로 두셔야 합니다. 대신 프로그램을 따로 깔 필요가 없고 인터넷도 필요 없습니다.
      크롬 &middot; 엣지 최신판이면 <strong>MP4</strong> 로 나와 파워포인트에 넣거나 카카오톡으로 보낼 수 있고,
      아니면 WebM 으로 나오며 <strong>화면에 무엇으로 만들어졌는지 그대로 적어 드립니다.</strong>
      배경음악은 원장님이 준비하십시오 &mdash; 음원은 제공하지 않습니다.</p>
    </div>
  </div>
</section>

<!-- ── 05 이용 안내 ─────────────────────────────────── -->
<section class="guide">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">09 /</span> 이용 안내</p>
    <h2 class="reveal" style="--d:0.1s">피아노 이벤트 솔루션 이용 안내</h2>
    <div class="info-cards">
      <div class="info-card red reveal">
        <p class="label">이용 기간</p>
        <p class="big">결제 후 1년</p>
        <p class="desc">정기 연주회 &middot; 시즌 특강<br>행사 수 제한 없이 무제한</p>
      </div>
      <div class="info-card blue reveal" style="--d:0.15s">
        <p class="label">제공 범위</p>
        <p class="big">인쇄물 59종</p>
        <p class="desc">디자인 테마 108종 &middot; 사회자 대본<br>무대 화면 &middot; 모바일 초대장 &middot; 참석 집계</p>
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
    <p class="eyebrow reveal"><span class="num">10 /</span> 무엇을 드리고, 무엇은 드리지 않는가</p>
    <h2 class="reveal" style="--d:0.1s">사시기 전에<br><span class="accent">이것부터</span> 확인해 주세요</h2>
    <div class="scope-grid">
      <div class="scope-col yes reveal">
        <h3>드리는 것</h3>
        <ul>
          <li><span class="scope-mark">&#10003;</span><span><b>연주 순서 배치</b> &middot; 오프닝부터 피날레까지 흐름, 곡 사이 전환 시간, 중간 휴식, 종료 시각 계산</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>사회자 대본</b> &middot; 곡과 작곡가, 학생 메모를 엮은 곡별 멘트</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>인쇄물 59종 &times; 테마 108종</b> &middot; 포스터부터 좌석 배치도, 진행 문서까지</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>연주회장 무대 화면(PPT)</b> &middot; 명단에서 만들어지는 16:9 슬라이드. 테마 108종 적용, 전체화면 진행, <b>.pptx</b> 또는 PDF로 저장</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>감동영상 편집기</b> &middot; 사진 &middot; 동영상 &middot; 음악을 얹어 한 편으로. 템플릿 10종, 장면마다 문구 &middot; 순서 &middot; 시간을 직접 고침. 이 컴퓨터 안에서 MP4 로 나옵니다</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>모바일 초대장과 참석 집계</b> &middot; 링크 하나로 인원이 저절로 쌓입니다. 감동영상 주소를 붙이면 초대장 안에서 재생됩니다</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>당일 진행 화면</b> &middot; 무대 옆에서 휴대폰으로 보는 &ldquo;지금 &middot; 다음 &middot; 그다음&rdquo; 과 밀린 시간. <b>함께 보기</b>로 대기실 &middot; 접수처 화면도 함께 넘어감</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>실제 시간 되먹임</b> &middot; 당일에 넘긴 시각에서 곡마다 실제로 걸린 시간을 뽑아 명단에 반영. 학원에 최근 다섯 번까지 쌓여 <b>평균</b>으로 쓰입니다</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>당일 사진 모으기</b> &middot; 리허설에서 찍은 사진을 휴대폰으로 그 자리에서 &mdash; 넣는 즉시 무대 화면 &middot; 감동영상에</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>리허설 소집 &middot; 참가비 &middot; 좌석</b> 계산과 안내 문자</span></li>
          <li><span class="scope-mark">&#10003;</span><span><b>시즌 특강 기획</b> &middot; 할로윈 &middot; 크리스마스 &middot; 방학 4주 커리큘럼과 활동지</span></li>
        </ul>
      </div>
      <div class="scope-col no reveal" style="--d:0.15s">
        <h3>드리지 않는 것</h3>
        <ul>
          <li><span class="scope-mark">&#10005;</span><span><b>악보</b> &middot; 교재와 편곡본은 저작권이 있습니다. <b>학원에서 쓰시던 악보를 그대로</b> 쓰십니다</span></li>
          <li><span class="scope-mark">&#10005;</span><span><b>음원 &middot; 반주 &middot; 영상 소재</b> &middot; 같은 이유(저작권)입니다. 감동영상을 <b>만드는 도구는 드리지만</b> 배경음악과 영상 소재는 원장님이 준비하십니다</span></li>
          <li><span class="scope-mark">&#10005;</span><span><b>영상 보관 &middot; 배포</b> &middot; 만든 영상 파일은 저희가 보관하지 않습니다. 아이들 얼굴을 서버에 올리지 않으려는 것입니다</span></li>
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
    <p class="eyebrow reveal"><span class="num">11 /</span> 학생 명단은 어떻게 넣나요</p>
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
    <p class="eyebrow reveal"><span class="num">12 /</span> 지금 쓰시는 방법과 비교하면</p>
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
            <td class="ours">59종이 함께 즉시 변경</td>
          </tr>
          <tr>
            <th>학생 이름 입력</th>
            <td>양식마다 반복</td>
            <td>양식마다 반복 타이핑</td>
            <td>파일로 전달</td>
            <td class="ours">한 번 &rarr; 59종에 자동</td>
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
            <th>연주회장 스크린</th>
            <td>PPT를 해마다 한 장씩 다시 제작</td>
            <td>슬라이드를 한 장씩 직접 제작</td>
            <td>영상 제작 별도 견적</td>
            <td class="ours">명단 넣으면 16:9 자동 &middot; .pptx 로 받아 수정</td>
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
      명단 하나가 순서 &rarr; 시각 &rarr; 멘트 &rarr; 인쇄물 &rarr; 무대 화면 &rarr; 리허설 &rarr; 좌석 &rarr; 참가비로 전부 흘러가고,
      <strong>한 곳을 고치면 전부 따라 바뀝니다.</strong></p>
    </div>
  </div>
</section>

<!-- ── 06 이런 원장님께 ─────────────────────────────── -->
<section class="recommend">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">13 /</span> 이런 원장님께 추천합니다</p>
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
    <p class="sub reveal" style="--d:0.2s">순서표 &middot; 사회자 대본 &middot; 인쇄물 &middot; 초대장 &middot; 참석 집계 &middot; 당일 진행표 &middot; 무대 화면까지 한 자리에서.</p>
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
    '<meta name="description" content="학생 명단만 넣으면 연주 순서표·사회자 대본·포스터·초대장·참석 집계·당일 진행표·연주회장 스크린 화면까지. 피아노학원 연주회 올인원 솔루션.">\n'
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
