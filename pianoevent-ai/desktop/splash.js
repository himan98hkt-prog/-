/**
 * 첫 화면의 생김새.
 *
 * `main.js` 에서 떼어 둔 것은 **눈으로 확인할 수 있게** 하기 위해서다.
 * 여기 있으면 검사 스크립트가 그대로 불러다 브라우저에 띄워 사진을 찍을 수 있다.
 * 설치본을 뽑아 깔아 보기 전에는 알 수 없는 화면이 하나 줄었다.
 */

/** @param img 무대 사진(data: URL). 없으면 검은 바탕만 나온다 */
function splashHtml(img) {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
    * { margin: 0; box-sizing: border-box; -webkit-user-select: none; cursor: default }
    body { width: 100vw; height: 100vh; overflow: hidden; background: #08080a; color: #f6f1e6;
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", system-ui, sans-serif; }
    .art { position: absolute; inset: 0; background: ${img ? `url("${img}") center/cover no-repeat` : '#08080a'} }
    .veil { position: absolute; inset: 0;
      background: linear-gradient(to right, rgba(8,8,10,0.92) 0%, rgba(8,8,10,0.72) 46%, rgba(8,8,10,0.25) 100%) }
    .box { position: absolute; inset: 0; padding: 38px 40px; display: flex; flex-direction: column; justify-content: flex-end }
    .mark { font-size: 11px; letter-spacing: 0.42em; color: #c9a253 }
    h1 { margin-top: 12px; font-size: 27px; font-weight: 700; letter-spacing: -0.01em }
    .say { margin-top: 9px; font-size: 13px; color: rgba(246,241,230,0.72) }
    .bar { margin-top: 20px; height: 2px; background: rgba(246,241,230,0.16); overflow: hidden }
    .bar i { display: block; height: 100%; width: 38%; background: linear-gradient(90deg, transparent, #c9a253, transparent);
      animation: slide 1.5s ease-in-out infinite }
    @keyframes slide { 0% { transform: translateX(-110%) } 100% { transform: translateX(320%) } }
    @media (prefers-reduced-motion: reduce) { .bar i { animation: none; width: 100% } }
  </style></head><body>
    <div class="art"></div><div class="veil"></div>
    <div class="box">
      <p class="mark">PIANOEVENT</p>
      <h1>피아노이벤트</h1>
      <p class="say" id="say">프로그램을 준비하고 있습니다…</p>
      <div class="bar"><i></i></div>
    </div>
    <script>
      setTimeout(function () {
        document.getElementById('say').textContent = '처음 여실 때는 조금 더 걸립니다. 그대로 두세요.'
      }, 9000)
    </script>
  </body></html>`
}

module.exports = { splashHtml }
