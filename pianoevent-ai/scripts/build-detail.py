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
        <div class="stat"><p class="v">20종</p><p class="k">인쇄물 양식</p></div>
        <div class="stat"><p class="v">20종</p><p class="k">디자인 테마</p></div>
        <div class="stat"><p class="v">0원</p><p class="k">디자인 외주비</p></div>
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

<!-- ── 03 화면 미리보기 ─────────────────────────────── -->
<section class="guide">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">03 /</span> 실제 화면</p>
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
    <p class="eyebrow reveal"><span class="num">04 /</span> 인쇄물 미리보기</p>
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
    <p class="eyebrow reveal"><span class="num">05 /</span> 이용 안내</p>
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

<!-- ── 06 이런 원장님께 ─────────────────────────────── -->
<section class="recommend">
  <div class="inner">
    <p class="eyebrow reveal"><span class="num">06 /</span> 이런 원장님께 추천합니다</p>
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
