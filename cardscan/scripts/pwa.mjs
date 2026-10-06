// 웹 빌드(dist)를 아이폰 "홈 화면에 추가" 용 웹앱으로 마무리한다.
//   node scripts/pwa.mjs <dist 폴더> <기본 경로, 예: /-
// - iOS 홈 화면 아이콘·전체화면 메타 태그, 웹앱 manifest
// - 404.html: GitHub Pages 에서 /card/xxx 같은 주소로 바로 들어와도 앱이 열리게
// - .nojekyll: GitHub Pages 가 _expo 폴더를 숨기지 않게
// - tesseract/: 무료 문자 인식 엔진·언어 데이터 (같은 사이트에서 제공)
import fs from 'node:fs';
import path from 'node:path';

const [dist = 'dist', base = ''] = process.argv.slice(2);
const root = base.replace(/\/$/, '');
const app = JSON.parse(fs.readFileSync('app.json', 'utf8')).expo;
const web = app.web ?? {};

fs.copyFileSync('assets/icon.png', path.join(dist, 'icon-1024.png'));

// 앱과 같은 Pretendard 글꼴 (안드로이드는 앱에 내장, 웹은 같은 사이트에서 제공)
const FONT_WEIGHTS = { Regular: 400, SemiBold: 600, Bold: 700, ExtraBold: 800 };
fs.mkdirSync(path.join(dist, 'fonts'), { recursive: true });
for (const w of Object.keys(FONT_WEIGHTS)) fs.copyFileSync(`assets/fonts/Pretendard-${w}.otf`, path.join(dist, 'fonts', `Pretendard-${w}.otf`));
const fontFaces = Object.entries(FONT_WEIGHTS)
  .map(([w, n]) => `@font-face{font-family:Pretendard;font-weight:${n};font-display:swap;src:url(${root}/fonts/Pretendard-${w}.otf) format("opentype")}`)
  .join('');

// 무료 문자 인식(Tesseract) 엔진·한국어/영어 데이터를 같은 사이트에 둔다 — 외부 CDN 의존 없음
const ocrDir = path.join(dist, 'tesseract');
for (const sub of ['core', 'lang']) fs.mkdirSync(path.join(ocrDir, sub), { recursive: true });
fs.copyFileSync('node_modules/tesseract.js/dist/worker.min.js', path.join(ocrDir, 'worker.min.js'));
for (const f of ['tesseract-core-lstm.wasm.js', 'tesseract-core-simd-lstm.wasm.js', 'tesseract-core-relaxedsimd-lstm.wasm.js']) {
  fs.copyFileSync(path.join('node_modules/tesseract.js-core', f), path.join(ocrDir, 'core', f));
}
for (const lang of ['kor', 'eng']) {
  fs.copyFileSync(
    path.join(`node_modules/@tesseract.js-data/${lang}/4.0.0_best_int`, `${lang}.traineddata.gz`),
    path.join(ocrDir, 'lang', `${lang}.traineddata.gz`),
  );
}
fs.writeFileSync(
  path.join(dist, 'manifest.webmanifest'),
  JSON.stringify(
    {
      name: web.name ?? app.name,
      short_name: web.shortName ?? app.name,
      description: web.description ?? '',
      lang: web.lang ?? 'ko',
      start_url: `${root}/`,
      scope: `${root}/`,
      display: 'standalone',
      orientation: 'portrait',
      background_color: web.backgroundColor ?? '#ffffff',
      theme_color: web.themeColor ?? '#000000',
      icons: [{ src: `${root}/icon-1024.png`, sizes: '1024x1024', type: 'image/png', purpose: 'any maskable' }],
    },
    null,
    2,
  ),
);

const indexPath = path.join(dist, 'index.html');
let html = fs.readFileSync(indexPath, 'utf8');
html = html
  .replace('<html lang="en">', `<html lang="${web.lang ?? 'ko'}">`)
  .replace('href="/favicon.ico"', `href="${root}/favicon.ico"`)
  .replace(
    /<meta name="viewport"[^>]*>/,
    '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover" />',
  )
  .replace(
    '</head>',
    [
      `<link rel="manifest" href="${root}/manifest.webmanifest" />`,
      `<link rel="apple-touch-icon" href="${root}/icon-1024.png" />`,
      '<meta name="apple-mobile-web-app-capable" content="yes" />',
      '<meta name="mobile-web-app-capable" content="yes" />',
      `<meta name="apple-mobile-web-app-title" content="${web.shortName ?? app.name}" />`,
      '<meta name="apple-mobile-web-app-status-bar-style" content="default" />',
      `<meta name="theme-color" content="${web.themeColor ?? '#000000'}" />`,
      `<meta name="description" content="${web.description ?? ''}" />`,
      // iOS 에서 입력칸을 누를 때 화면이 확대되지 않게 (16px 미만 글꼴에서 자동 확대됨)
      `<style>${fontFaces}input,textarea{font-size:16px}</style>`,
      '</head>',
    ].join('\n    '),
  );
fs.writeFileSync(indexPath, html);
fs.copyFileSync(indexPath, path.join(dist, '404.html'));
fs.writeFileSync(path.join(dist, '.nojekyll'), '');
console.log(`PWA 마무리 완료: ${dist} (기본 경로 "${root || '/'}")`);
