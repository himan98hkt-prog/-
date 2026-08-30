/**
 * 첫 화면의 생김새.
 *
 * `main.js` 에서 떼어 둔 것은 **눈으로 확인할 수 있게** 하기 위해서다.
 * 여기 있으면 검사 스크립트가 그대로 불러다 브라우저에 띄워 사진을 찍을 수 있다
 * (`npm run shots:splash`). 설치본을 뽑아 깔아 보기 전에는 알 수 없던 화면이 하나 줄었다.
 *
 * 로고는 **검은 바탕에 흰 선**으로 그려진 그림이다. 색을 그대로 쓰지 않고
 * 모양(마스크)으로 써서 금색으로 칠한다 — 가장자리가 부드럽게 남고, 어두운 사진 위에서
 * 오려 낸 티가 나지 않는다.
 */
const BRAND = require('./brand.js')

/**
 * @param img  무대 사진(data: URL). 없으면 검은 바탕만 나온다
 * @param logo 로고 표식(data: URL). 없으면 글자만 나온다
 */
function splashHtml(img, logo) {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
    * { margin: 0; box-sizing: border-box; -webkit-user-select: none; cursor: default }
    body { width: 100vw; height: 100vh; overflow: hidden; background: #08080a; color: #f6f1e6;
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", system-ui, sans-serif; }
    .art { position: absolute; inset: 0; background: ${img ? `url("${img}") center/cover no-repeat` : '#08080a'} }
    .veil { position: absolute; inset: 0;
      background: radial-gradient(120% 90% at 50% 45%, rgba(8,8,10,0.62) 0%, rgba(8,8,10,0.88) 62%, rgba(8,8,10,0.96) 100%) }
    .box { position: absolute; inset: 0; display: flex; flex-direction: column;
      align-items: center; justify-content: center; padding: 30px 40px }
    .logo { width: 92px; height: 92px; background: linear-gradient(160deg, #f0d9a0 0%, #c9a253 52%, #8f6c26 100%);
      -webkit-mask: ${logo ? `url("${logo}") center/contain no-repeat` : 'none'};
      mask: ${logo ? `url("${logo}") center/contain no-repeat` : 'none'};
      -webkit-mask-mode: luminance; mask-mode: luminance; opacity: ${logo ? 1 : 0} }
    h1 { margin-top: 15px; font-size: 26px; font-weight: 700; letter-spacing: 0.02em }
    .en { margin-top: 7px; font-size: 10px; letter-spacing: 0.46em; color: #c9a253; text-indent: 0.46em }
    .rule { margin-top: 16px; width: 46px; height: 1px; background: rgba(201,162,83,0.55) }
    .maker { margin-top: 13px; font-size: 11.5px; letter-spacing: 0.12em; color: rgba(246,241,230,0.62) }
    .say { position: absolute; left: 0; right: 0; bottom: 40px; text-align: center;
      font-size: 12.5px; color: rgba(246,241,230,0.7) }
    .bar { position: absolute; left: 40px; right: 40px; bottom: 26px; height: 2px;
      background: rgba(246,241,230,0.14); overflow: hidden }
    .bar i { display: block; height: 100%; width: 34%;
      background: linear-gradient(90deg, transparent, #c9a253, transparent);
      animation: slide 1.5s ease-in-out infinite }
    @keyframes slide { 0% { transform: translateX(-110%) } 100% { transform: translateX(330%) } }
    @media (prefers-reduced-motion: reduce) { .bar i { animation: none; width: 100% } }
  </style></head><body>
    <div class="art"></div><div class="veil"></div>
    <div class="box">
      <div class="logo"></div>
      <h1>${BRAND.name}</h1>
      <p class="en">${BRAND.nameEn}</p>
      <div class="rule"></div>
      <p class="maker">${BRAND.maker}</p>
    </div>
    <p class="say" id="say">프로그램을 준비하고 있습니다…</p>
    <div class="bar"><i></i></div>
    <script>
      setTimeout(function () {
        document.getElementById('say').textContent = '처음 여실 때는 조금 더 걸립니다. 그대로 두세요.'
      }, 9000)
    </script>
  </body></html>`
}

module.exports = { splashHtml }
