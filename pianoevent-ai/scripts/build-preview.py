import base64, pathlib

ROOT = pathlib.Path('/home/user/-/pianoevent-ai')
SRC = ROOT / 'promo' / 'preview'

def img(name):
    return 'data:image/jpeg;base64,' + base64.b64encode((SRC / name).read_bytes()).decode()

APP = [
    ('app-home.jpg', '첫 화면', '진행 중인 행사가 한눈에. 여기서 바로 시작합니다.'),
    ('app-roster.jpg', '학생 명단', '엑셀에서 표를 복사해 붙여넣기만 하면 됩니다. 시간 표기가 제각각이어도 읽습니다.'),
    ('app-program.jpg', '순서표 · 사회자 대본', '버튼 한 번에 연주 순서, 예상 시각, 곡별 사회자 멘트까지 만들어집니다.'),
    ('app-design.jpg', '인쇄물 디자인', '양식 59종 × 테마 108종. 고르는 즉시 오른쪽 미리보기가 바뀝니다.'),
    ('app-prep.jpg', '진행 준비', '준비 체크리스트, 학부모 안내 문구 4종, 당일 진행표가 날짜에 맞춰 계산됩니다.'),
    ('app-invite-admin.jpg', '초대장 · 참석 집계', '링크를 단톡방에 올리면 참석 인원이 저절로 쌓입니다.'),
    ('app-seasons.jpg', '시즌 특강', '할로윈·크리스마스·방학 테마로 4주 커리큘럼과 활동지를 만듭니다.'),
]

SHEETS = [
    ('sheet-poster-sunlit.jpg', '포스터', '햇살 아이보리'),
    ('sheet-poster-noir.jpg', '포스터', '느와르 골드'),
    ('sheet-poster-blossom.jpg', '전면 사진 포스터', '블라썸 화이트'),
    ('sheet-cover.jpg', '프로그램 표지', '문릿 블루'),
    ('sheet-program.jpg', '연주 순서지', '햇살 아이보리'),
    ('sheet-ticket.jpg', '입장권 3매', '펄 민트'),
    ('sheet-nametag.jpg', '좌석 이름표', '파스텔 키즈'),
    ('sheet-certificate.jpg', '참가 상장', '클래식 네이비'),
    ('sheet-cue.jpg', '당일 진행표', '데이라이트 스튜디오'),
    ('sheet-checklist.jpg', '준비 체크리스트', '햇살 아이보리'),
]

CSS = """
:root{
  --paper:#fbfaf6; --paper2:#f3efe4; --ink:#141d33; --muted:#5d6478;
  --gold:#b3892f; --line:#e2dbc9; --white:#fff;
  --fs-body:clamp(1rem,0.96rem + 0.3vw,1.12rem);
  --fs-h1:clamp(1.7rem,1.2rem + 2.4vw,3rem);
  --fs-h2:clamp(1.35rem,1.1rem + 1.4vw,2rem);
}
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  font-family:'Pretendard','Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif;
  background:var(--paper); color:var(--ink); line-height:1.75;
  word-break:keep-all; overflow-wrap:break-word;
}
.wrap{max-width:1080px;margin:0 auto;padding:0 clamp(1.1rem,4vw,2rem)}
section{padding:clamp(2.6rem,5vw,4.5rem) 0}
h1,h2{font-family:'Nanum Myeongjo','Apple SD Gothic Neo',serif;font-weight:800;line-height:1.4}
h1{font-size:var(--fs-h1)}
h2{font-size:var(--fs-h2)}
.eyebrow{font-size:clamp(0.9rem,0.86rem + 0.2vw,1rem);letter-spacing:0.24em;color:var(--gold);font-weight:700}
.lead{font-size:var(--fs-body);color:var(--muted);margin-top:1em}
.cover{
  background:radial-gradient(ellipse 70% 50% at 15% 0%, rgba(179,137,47,.14), transparent 70%), var(--paper);
  text-align:center; padding-top:clamp(3rem,7vw,5.5rem);
}
.cover .badge{
  display:inline-block;margin-top:1.6em;padding:.5em 1.2em;border-radius:999px;
  background:var(--white);border:1px solid var(--line);font-size:clamp(.95rem,.9rem + .2vw,1.05rem);color:var(--muted)
}
.grid-4{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:clamp(.9rem,2vw,1.4rem);margin-top:clamp(1.8rem,3vw,2.6rem)}
.tile{background:var(--white);border:1px solid var(--line);border-radius:16px;padding:clamp(1.1rem,2.5vw,1.6rem)}
.tile .k{font-family:'Nanum Myeongjo',serif;font-size:clamp(1.15rem,1rem + .6vw,1.4rem);font-weight:800}
.tile .d{margin-top:.5em;font-size:clamp(.95rem,.92rem + .2vw,1.05rem);color:var(--muted)}
.shot{margin-top:clamp(2rem,4vw,3rem)}
.shot img{display:block;width:100%;height:auto;border-radius:12px;border:1px solid var(--line);box-shadow:0 14px 36px rgba(20,20,43,.10);background:#fff}
.shot .cap{margin-top:.9em}
.shot .cap b{display:block;font-family:'Nanum Myeongjo',serif;font-size:clamp(1.1rem,1rem + .5vw,1.3rem);font-weight:800}
.shot .cap span{display:block;margin-top:.25em;font-size:var(--fs-body);color:var(--muted)}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:clamp(1.6rem,3vw,2.6rem);align-items:start;margin-top:clamp(2rem,4vw,3rem)}
.phone{max-width:330px;margin:0 auto}
.phone .frame{background:#241f1a;border-radius:34px;padding:9px}
.phone img{display:block;width:100%;border-radius:26px}
.sheets{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr));gap:clamp(1.1rem,2.5vw,1.8rem);margin-top:clamp(2rem,4vw,3rem)}
.sheets figure img{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:6px;box-shadow:0 10px 26px rgba(20,20,43,.10);background:#fff}
.sheets figcaption{margin-top:.7em;text-align:center;font-size:clamp(.95rem,.92rem + .2vw,1.02rem)}
.sheets figcaption b{display:block;font-weight:700}
.sheets figcaption span{color:var(--muted);font-size:.95em}
.alt{background:var(--paper2)}
.steps{counter-reset:s;margin-top:clamp(1.6rem,3vw,2.4rem);display:grid;gap:1rem}
.step{background:var(--white);border:1px solid var(--line);border-radius:14px;padding:clamp(1rem,2.5vw,1.4rem);display:flex;gap:1rem;align-items:flex-start}
.step .n{flex:0 0 auto;width:2rem;height:2rem;border-radius:50%;background:var(--ink);color:var(--paper);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.95rem}
.step p{font-size:var(--fs-body)}
.step code{background:var(--paper2);padding:.15em .5em;border-radius:5px;font-size:.95em}
footer{padding:clamp(2rem,4vw,3rem) 0;text-align:center;color:var(--muted);font-size:clamp(.92rem,.9rem + .2vw,1rem);border-top:1px solid var(--line)}
"""

def shot(name, title, desc):
    return f'''<div class="shot"><img src="{img(name)}" alt="{title}">
      <p class="cap"><b>{title}</b><span>{desc}</span></p></div>'''

def sheet(name, title, theme):
    return f'''<figure><img src="{img(name)}" alt="{title}">
      <figcaption><b>{title}</b><span>{theme}</span></figcaption></figure>'''

html = f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>피아노 이벤트 솔루션 — 미리보기</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@700;800&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head><body>

<section class="cover">
  <div class="wrap">
    <p class="eyebrow">PIANOEVENT AI</p>
    <h1 style="margin-top:.6em">연주회 준비에 쓰던 사흘,<br>이제 30분이면 끝납니다</h1>
    <p class="lead" style="max-width:640px;margin-left:auto;margin-right:auto">
      피아노학원 정기 연주회와 시즌 특강을 위한 올인원 프로그램입니다.<br>
      학생 명단만 넣으면 순서표 · 사회자 대본 · 인쇄물 · 초대장 · 참석 집계까지 한 자리에서 끝납니다.
    </p>
    <p class="badge">이 파일은 <b>구경용 미리보기</b>입니다 · 설치 없이 이대로 보시면 됩니다</p>
  </div>
</section>

<section>
  <div class="wrap">
    <p class="eyebrow">무엇을 대신해 주나요</p>
    <h2 style="margin-top:.5em">원장님이 직접 하던 네 가지</h2>
    <div class="grid-4">
      <div class="tile"><p class="k">순서표</p><p class="d">난이도와 곡 길이를 보고 자동 배치. 몇 시에 끝나는지까지 계산합니다.</p></div>
      <div class="tile"><p class="k">사회자 대본</p><p class="d">곡 해설 + 학생 소개를 엮은 멘트가 곡마다 나옵니다.</p></div>
      <div class="tile"><p class="k">인쇄물</p><p class="d">포스터부터 상장까지 59종. 테마 하나로 전부 통일됩니다.</p></div>
      <div class="tile"><p class="k">초대장 · 집계</p><p class="d">카톡 링크 하나로 초대하고 참석 인원이 저절로 쌓입니다.</p></div>
    </div>
  </div>
</section>

<section class="alt">
  <div class="wrap">
    <p class="eyebrow">원장님 화면</p>
    <h2 style="margin-top:.5em">실제로 이렇게 생겼습니다</h2>
    {''.join(shot(*a) for a in APP)}
  </div>
</section>

<section>
  <div class="wrap">
    <p class="eyebrow">학부모 화면</p>
    <h2 style="margin-top:.5em">휴대폰으로 열리는 초대장</h2>
    <div class="two">
      <div class="phone"><div class="frame"><img src="{img('mobile-invite.jpg')}" alt="모바일 초대장"></div></div>
      <div>
        <p class="lead" style="margin-top:0">학부모는 <b>로그인 없이</b> 링크만 누르면 됩니다.
        행사 정보와 인사말, 연주 순서를 보고 그 자리에서 참석 여부와 인원을 남깁니다.
        남긴 응원 메시지는 초대장 아래에 함께 쌓입니다.</p>
        <p class="lead">원장님 화면에는 참석 가정 수와 총 인원이 실시간으로 집계돼,
        좌석과 프로그램 부수를 정확히 맞출 수 있습니다.</p>
      </div>
    </div>
  </div>
</section>

<section class="alt">
  <div class="wrap">
    <p class="eyebrow">인쇄물</p>
    <h2 style="margin-top:.5em">A4 용지에 그대로 나옵니다</h2>
    <p class="lead">테마를 바꾸면 모든 인쇄물의 색과 서체가 함께 바뀝니다. 아래는 서로 다른 테마로 뽑은 실제 출력 모습입니다.</p>
    <div class="sheets">{''.join(sheet(*s) for s in SHEETS)}</div>
  </div>
</section>

<section>
  <div class="wrap">
    <p class="eyebrow">직접 눌러 보시려면</p>
    <h2 style="margin-top:.5em">두 번 클릭하면 끝입니다</h2>
    <p class="lead">명령어를 칠 일은 없습니다. 받으신 폴더 맨 위의 파일을 두 번 누르기만 하면 됩니다.
      데모 학원과 학생 12명이 이미 들어 있어 바로 눌러 보실 수 있습니다.</p>
    <div class="steps">
      <div class="step"><span class="n">1</span><p>받으신 ZIP 파일을 오른쪽 클릭 &rarr; <b>압축 풀기</b></p></div>
      <div class="step"><span class="n">2</span><p>풀린 폴더의 <b>시작하기.bat</b> 을 두 번 클릭
        <br><small>맥이라면 <b>시작하기-맥용.command</b></small></p></div>
      <div class="step"><span class="n">3</span><p>처음 한 번만 2~4분 기다리면 브라우저가 저절로 열립니다.
        필요한 프로그램은 알아서 설치됩니다.</p></div>
    </div>
    <p class="lead">휴대폰으로 보시려면 <b>휴대폰으로-보기.bat</b> 을 누르세요. QR 코드가 뜹니다.
      자세한 사용법은 함께 드린 <b>docs/MANUAL.md</b> 에 있습니다.</p>
  </div>
</section>

<footer>
  <div class="wrap">피아노 이벤트 솔루션 · PianoEvent AI</div>
</footer>

</body></html>
"""

out = ROOT / '배포' / '피아노이벤트-미리보기.html'
out.write_text(html)
print('written', out, round(out.stat().st_size / 1024), 'KB')
