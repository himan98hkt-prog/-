'use strict';
/* 반주 플레이어 — 지시서 모듈 ⑤. "여기가 실제 상품."
 *
 * 화면은 세 개뿐이다: 곡 고르기 / 연주 / 발표회 큐.
 * 원장님이 현장에서 누르는 것은 결국 재생과 페이드아웃 두 개다.
 */
import { Player, FADE_SECONDS } from './engine.js';
import { store } from './store.js';

const $ = (s) => document.querySelector(s);
const view = $('#view');
const player = new Player();

/* API 가 어디 붙어 있는지. 서버로 띄우면 `/`, 정적 꾸러미로 올리면 `./` 다.
 * 원장님은 도메인 루트에 올릴 수도 `/반주/` 같은 하위 폴더에 올릴 수도 있으므로
 * 절대경로를 박아 두면 안 된다. 번들이 준 주소가 절대경로면 그게 이긴다. */
const API_ROOT = new URL(document.documentElement.dataset.api || '/', document.baseURI);
const apiUrl = (u) => new URL(u, API_ROOT).href;

const state = {
  bundle: null,
  song: null,
  settings: null,
  student: store.lastStudent,
  queue: null,        // {program, at}
};

/* ---------- 유틸 ---------- */
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const mmss = (s) => (!isFinite(s) || s < 0) ? '0:00'
  : `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('on'), 2400);
}

function netBadge() {
  const el = $('#net');
  const on = navigator.onLine;
  el.textContent = on ? '' : '오프라인';
  el.classList.toggle('off', !on);
}
addEventListener('online', netBadge);
addEventListener('offline', netBadge);

/* ---------- 데이터 ---------- */
async function bundle() {
  if (state.bundle) return state.bundle;
  const r = await fetch(apiUrl('api/player/bundle'));
  if (!r.ok) throw new Error('곡 목록을 받지 못했습니다');
  state.bundle = await r.json();
  return state.bundle;
}
const songById = (id) => (state.bundle.songs || []).find((s) => s.id === id);

/* 반주 주소. **미리 받기와 재생이 반드시 같은 함수를 써야 한다.**
 * 하나라도 다르면 오프라인에서 캐시가 빗나가고, 그러면 화면은 「실내악」인데
 * 스피커에서는 기본 편성이 나온다 — 발표회장에서 제일 겪으면 안 되는 일이다.
 *
 * 정적 배포(서버 없이 파일만 올린 경우)에는 미리 구워 둔 편성밖에 없다. 게다가
 * 정적 호스트는 쿼리스트링을 무시하므로 없는 편성을 불러도 **같은 파일이 조용히
 * 돌아온다.** 그래서 번들이 알려 준 목록에서 고른다. */
function midiUrl(song, settings) {
  // 정적 꾸러미의 주소에는 만들 때 구운 바이트의 해시가 이미 붙어 있다.
  if (song.variants) {
    const hit = song.variants.find(
      (v) => v.style === settings.style && v.level === settings.level);
    return apiUrl((hit || song.variants[0]).url);
  }
  const q = new URLSearchParams({ style: settings.style, level: settings.level });
  // `rev` 는 반주가 바뀌면 같이 바뀐다. 이게 없으면 화성을 고쳐도 서비스워커가
  // 옛 반주를 영영 캐시에서 꺼내 준다 — 화면은 고친 화성, 소리는 옛것.
  if (song.rev) q.set('v', song.rev);
  return apiUrl(`${song.midi}?${q}`);
}

async function loadSong(song, settings) {
  const r = await fetch(midiUrl(song, settings));
  if (!r.ok) throw new Error('반주를 받지 못했습니다');
  // 서비스워커가 캐시의 다른 것을 대신 준 경우 (오프라인). 무엇이 다른지에
  // 따라 말이 달라야 한다 — 편성이 바뀐 것과 판이 옛것인 것은 전혀 다른 일이다.
  const fallback = r.headers.get('X-MR-Fallback');
  if (fallback === 'default') {
    toast('오프라인이라 기본 편성으로 재생합니다.');
  } else if (fallback === 'stale') {
    toast('오프라인이라 예전에 받아 둔 반주로 재생합니다.');
  }
  player.load(await r.arrayBuffer(), {
    bpm: settings.bpm,
    transpose: settings.transpose,
    countInBars: settings.countIn,
  });
  player.setVolume(settings.volume);
}

/* 정적 배포는 미리 구워 둔 편성만 들어 있다. 없는 걸 고른 상태로 두면
 * 화면엔 「실내악」인데 스피커에선 기본 편성이 나온다. */
function clampToPackage(song, settings) {
  if (!song.variants) return false;
  const has = song.variants.some(
    (v) => v.style === settings.style && v.level === settings.level);
  if (has) return false;
  const fallback = song.variants[0];
  settings.style = fallback.style;
  settings.level = fallback.level;
  return true;
}

function defaultsFor(song) {
  return { bpm: song.bpm, style: song.style, level: song.level_name,
           transpose: 0, volume: 0.85, countIn: store.countInBars };
}

/* ---------- 라우팅 ---------- */
function route() {
  const hash = location.hash.slice(1) || '/';
  const [path, qs] = hash.split('?');
  const q = new URLSearchParams(qs || '');
  player.pause();
  $('#back').hidden = path === '/';
  if (path === '/play') return screenPlay(q);
  if (path === '/program') return screenProgram(q);
  return screenHome();
}
addEventListener('hashchange', route);
$('#back').addEventListener('click', () => {
  if (state.queue) { state.queue = null; location.hash = '#/program?i=0'; }
  else location.hash = '#/';
});

/* ---------- 홈: 곡 고르기 ---------- */
async function screenHome() {
  $('#heading').textContent = '반주';
  view.innerHTML = '<div class="empty">불러오는 중…</div>';
  let b;
  try { b = await bundle(); }
  catch (e) {
    view.innerHTML = `<div class="empty">${esc(e.message)}<br>
      <span class="tiny">오프라인이면 한 번은 연결된 상태에서 열어야 합니다.</span></div>`;
    return;
  }

  const students = store.students();
  const byBook = new Map();
  for (const s of b.songs) {
    if (!byBook.has(s.book)) byBook.set(s.book, []);
    byBook.get(s.book).push(s);
  }

  view.innerHTML = `
    ${b.programs.length ? `<button class="row feature" id="toProgram">
      <div class="row__key">🎭</div>
      <div class="row__main">
        <div class="row__title">${esc(b.programs[0].event)}</div>
        <div class="row__sub">${b.programs[0].count}곡 · 약 ${b.programs[0].minutes}분 · 발표회 진행</div>
      </div><div class="row__go">→</div></button>` : ''}

    <div class="card">
      <div class="ctl" style="border:none;padding-top:0">
        <span class="ctl__label">아이</span>
        <select id="student">
          <option value="">(선택 안 함)</option>
          ${students.map((s) => `<option${s === state.student ? ' selected' : ''}>${esc(s)}</option>`).join('')}
        </select>
      </div>
      <div class="ctl" style="border:none;padding-bottom:0">
        <span class="ctl__label">새 이름</span>
        <input type="text" id="newStudent" placeholder="이름을 적으면 설정이 아이별로 저장됩니다">
      </div>
    </div>

    ${[...byBook.entries()].map(([book, songs]) => `
      <div class="book-head">
        <h2>${esc(book || '기타')}</h2><span class="n">${songs.length}곡</span>
      </div>
      <div class="rows">
        ${songs.map((s) => `
          <button class="row" data-song="${esc(s.id)}">
            <div class="row__key">${esc(keyBadge(s))}</div>
            <div class="row__main">
              <div class="row__title">${esc(s.title)}</div>
              <div class="row__sub">♩=${s.bpm} · ${esc(s.key_label || s.key)} ·
                ${esc(s.time || '')} · ${s.measures}마디</div>
            </div>
            ${s.verified ? '' : '<span class="chip warn">확인 전</span>'}
            <div class="row__go">→</div>
          </button>`).join('')}
      </div>`).join('')}`;

  const go = $('#toProgram');
  if (go) go.onclick = () => { location.hash = '#/program?i=0'; };
  $('#student').onchange = (e) => {
    state.student = e.target.value;
    store.lastStudent = state.student;
  };
  $('#newStudent').onchange = (e) => {
    const v = e.target.value.trim();
    if (!v) return;
    state.student = v;
    store.lastStudent = v;
    toast(`${v} 으로 설정을 저장합니다.`);
    e.target.value = '';
    screenHome();
  };
  view.querySelectorAll('[data-song]').forEach((el) => {
    el.onclick = () => { location.hash = `#/play?song=${encodeURIComponent(el.dataset.song)}`; };
  });
}

/* ---------- 연주 화면 ---------- */
async function screenPlay(q) {
  let b;
  try { b = await bundle(); } catch (e) { view.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  const song = songById(q.get('song'));
  if (!song) { view.innerHTML = '<div class="empty">없는 곡입니다.</div>'; return; }

  // 집 연습 링크로 들어왔으면 링크에 담긴 설정이 이긴다 (⑤-10)
  const student = q.get('student') || state.student;
  const fromLink = ['bpm', 'style', 'level', 'transpose', 'volume', 'countIn']
    .some((k) => q.has(k));
  const saved = store.settingsFor(student, song.id, defaultsFor(song));
  const settings = Object.assign({}, saved, fromLink ? {
    bpm: Number(q.get('bpm') || saved.bpm),
    style: q.get('style') || saved.style,
    level: q.get('level') || saved.level,
    transpose: Number(q.get('transpose') || 0),
    volume: Number(q.get('volume') || saved.volume),
    countIn: Number(q.get('countIn') === null ? saved.countIn : q.get('countIn')),
  } : {});

  // 꾸러미에 없는 편성이 저장돼 있거나 링크에 실려 왔으면 있는 것으로 맞춘다.
  // 화면과 소리가 어긋나는 것보다, 화면이 사실을 말하는 편이 낫다.
  clampToPackage(song, settings);

  state.song = song;
  state.settings = settings;
  state.student = student;
  $('#heading').textContent = student ? `${student} 연습` : '연주';

  view.innerHTML = `
    <div class="stage" id="stage">
     <div class="now">
      ${student ? `<div class="now__student">${esc(student)}</div>` : ''}
      <h2 class="now__title">${esc(song.title)}</h2>
      <div class="now__meta">
        ${song.book ? `<span>${esc(song.book)}</span>` : ''}
        ${song.composer ? `<span>${esc(song.composer)}</span>` : ''}
        <span><b>${esc(song.key_label || song.key)}</b></span>
        <span>${esc(song.time || '')}</span>
        <span><b>${song.measures}</b>마디</span>
      </div>
    </div>

      <!-- 마디 타임라인 — 아이가 멈췄을 때 「몇 마디」가 제일 먼저 보여야 한다.
           지금 울리는 화음도 같이 띄운다: 이 프로그램이 악보를 읽고 있다는 것이
           원장님에게 보이는 자리가 여기다 (화성 정확도 99.5%). -->
      <div class="track">
        <div class="track__chord">
          <span class="track__now" id="chordNow">${esc(chordAt(song, 0) || '—')}</span>
          <span class="track__next" id="chordNext"></span>
        </div>
        <div class="bar" id="bar" role="slider" aria-label="재생 위치"
             aria-valuemin="1" aria-valuemax="${song.measures || 1}" aria-valuenow="1">
          <div class="bar__ticks" id="ticks"></div>
          <i id="fill"></i>
          <div class="bar__head" id="head"></div>
        </div>
        <div class="times">
          <span id="pos">0:00</span>
          <span class="at"><b id="barno">1</b> / ${song.measures || 1}마디</span>
          <span id="dur">0:00</span>
        </div>
      </div>

      <div class="transport">
        <button class="round" id="rewind" title="처음으로" aria-label="처음으로">⏮</button>
        <button class="big" id="play" aria-label="재생">▶</button>
        <button class="round" id="loopBtn" title="구간 반복" aria-label="구간 반복">⟳</button>
      </div>

      <button class="fade" id="fade" disabled>반주 페이드아웃 (${FADE_SECONDS}초)</button>
    </div>

    <div class="card">
      <div class="ctl"><span class="ctl__label">템포</span>
        <input type="range" id="bpm" min="40" max="180" value="${settings.bpm}">
        <span class="ctl__val" id="bpmVal">♩=${settings.bpm}</span></div>
      <div class="ctl"><span class="ctl__label">조옮김</span>
        <input type="range" id="tr" min="-6" max="6" step="1" value="${settings.transpose}">
        <span class="ctl__val" id="trVal">${fmtTr(settings.transpose)}</span></div>
      <div class="ctl"><span class="ctl__label">볼륨</span>
        <input type="range" id="vol" min="0" max="100" value="${Math.round(settings.volume * 100)}">
        <span class="ctl__val" id="volVal">${Math.round(settings.volume * 100)}</span></div>
      <div class="ctl"><span class="ctl__label">카운트인</span>
        <div class="steps" id="countIn">
          ${[0, 1, 2, 4].map((n) => `<button data-n="${n}"${n === settings.countIn ? ' class="on"' : ''}>${n === 0 ? '없음' : n + '마디'}</button>`).join('')}
        </div></div>
      <div class="ctl"><span class="ctl__label">딸깍 소리</span>
        <button class="pick" id="cueOut">${esc(cueLabel())}</button></div>
      <div class="ctl"><span class="ctl__label">두께</span>
        <div class="steps" id="level">${levelSteps(settings.level, song)}</div></div>
      <div class="ctl ctl--stack"><span class="ctl__label">편성</span>
        <div class="styles" id="style" role="group" aria-label="편성">
          ${styleButtons(settings.style, song)}</div></div>
    </div>

    <div class="card" id="loopCard" hidden>
      <div class="muted" style="margin-bottom:10px">구간 반복 — 어려운 데만 돌려 친다</div>
      <div class="ctl"><span class="ctl__label">시작 마디</span>
        <input type="range" id="loopFrom" min="1" max="${player.totalBars || 1}" value="1">
        <span class="ctl__val" id="loopFromVal">1</span></div>
      <div class="ctl"><span class="ctl__label">끝 마디</span>
        <input type="range" id="loopTo" min="1" max="${player.totalBars || 1}" value="1">
        <span class="ctl__val" id="loopToVal">1</span></div>
      <button class="row" id="loopOff" style="justify-content:center">구간 반복 끄기</button>
    </div>

    <div class="card">
      <button class="row" id="share" style="justify-content:center">
        집 연습 링크 복사</button>
      <div class="tiny" style="margin-top:8px">
        카톡으로 보내면 설치·로그인 없이 이 설정 그대로 재생됩니다.</div>
    </div>`;

  try { await loadSong(song, settings); }
  catch (e) { toast(e.message); }

  wirePlay(song, settings, student);
}

const fmtTr = (n) => n === 0 ? '원조' : (n > 0 ? `+${n}` : `${n}`);

/** 목록에 붙는 작은 표지 — 조성 머리글자. 글자만 있으면 곡들이 다 같아 보인다. */
function keyBadge(song) {
  const k = String(song.key_label || song.key || '').trim();
  const m = k.match(/^([A-G][#b\u266f\u266d]?)/);
  return m ? m[1] : (k.slice(0, 2) || '♪');
}

/**
 * 그 박에서 울리는 화음.
 *
 * 번들의 `chords` 는 **바뀌는 지점만** 담고 있어(26곡 8.9KB), 지금 위치보다
 * 앞서지 않는 마지막 것을 찾으면 된다. 곡이 짧아 선형 탐색으로 충분하다.
 */
function chordAt(song, beat) {
  const t = song.chords;
  if (!t || !t.length) return '';
  let name = t[0][1];
  for (const [at, n] of t) {
    if (at > beat + 1e-6) break;
    name = n;
  }
  return name;
}

/** 다음 화음과 그때까지 남은 마디 — 무대에서 미리 보이면 마음이 놓인다. */
function chordNext(song, beat) {
  const t = song.chords;
  if (!t || !t.length) return null;
  for (const [at, n] of t) {
    if (at > beat + 1e-6) return { at, name: n };
  }
  return null;
}
const STYLE_LABEL = [['strings', '현악 앙상블'], ['chamber', '실내악'],
  ['orchestra', '풀 오케스트라'], ['fairytale', '동화풍'], ['warm', '따뜻한 소편성'],
  ['march', '행진곡풍'], ['pop', '팝·재즈풍']];
const LEVEL_LABEL = [['simple', '간단'], ['normal', '보통'], ['rich', '풍성']];

/* 편성 그림 — 일곱 개가 **코드 안에** 있다.
 *
 * 파일 일곱 개로 두면 `sw.js` 의 SHELL_FILES 에도 일곱 줄이 붙고, 그중 하나라도
 * 빠지면 `cache.addAll` 이 전부 거부해 **서비스워커 설치가 통째로 실패한다.**
 * 온라인에서는 멀쩡하고 비행기 모드에서만 무너지는 고장이다. 통째로 1.6KB 라
 * 파일로 나눌 이유가 없다.
 *
 * `currentColor` 로 그리므로 고른 단추에서는 금빛, 아닌 데서는 흐린 색이 된다 —
 * 상태별로 그림을 두 벌 두지 않아도 된다. */
const I = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"
  aria-hidden="true">${d}</svg>`;
const STYLE_ICON = {
  // 현악 — 몸통 두 덩이와 목. 처음엔 활까지 그렸더니 26px 에서 낙서로 보였다
  strings: I(`<circle cx="12" cy="16.8" r="4.3"/><circle cx="12" cy="11.3" r="3"/>
    <path d="M12 8.2V4.2"/><circle cx="12" cy="3" r="1.2"/>`),
  // 실내악 — 사람 셋. 「몇이서 같이」가 이 편성의 뜻이라 악기가 아니라 사람을 그렸다
  chamber: I(`<circle cx="5.6" cy="10" r="2.3"/><path d="M2.2 17.4a3.4 3.4 0 0 1 6.8 0"/>
    <circle cx="12" cy="7.6" r="2.3"/><path d="M8.6 15a3.4 3.4 0 0 1 6.8 0"/>
    <circle cx="18.4" cy="10" r="2.3"/><path d="M15 17.4a3.4 3.4 0 0 1 6.8 0"/>`),
  // 풀 오케스트라 — 두 줄 좌석과 지휘자. 줄을 **점선으로 끊어** 의자처럼 보이게 했다.
  // 이어진 호 두 개에 점 하나면 와이파이 표시와 구별이 안 된다
  orchestra: I(`<path d="M2.8 14.4a9.2 9.2 0 0 1 18.4 0" stroke-dasharray="2.9 2.5"/>
    <path d="M6.6 14.4a5.4 5.4 0 0 1 10.8 0" stroke-dasharray="2.6 2.3"/>
    <circle cx="12" cy="19" r="1.7"/>`),
  // 동화풍 — 별. 이 편성만 악기가 아니라 분위기의 이름이라 악기를 안 그렸다
  fairytale: I(`<path d="M11.2 3.4 13 7.2l4.1.6-3 2.9.7 4.1-3.6-1.9-3.7 1.9.7-4.1-3-2.9 4.1-.6z"/>
    <path d="M18.6 16.2l.5 1.2 1.2.5-1.2.5-.5 1.2-.5-1.2-1.2-.5 1.2-.5z"/>
    <path d="M5.4 18.4h.01"/>`),
  // 따뜻한 소편성 — 플루트. 눕혀 두면 알약으로 보여서 비스듬히 세웠다
  warm: I(`<g transform="rotate(-38 12 12)">
    <path d="M4.8 9.6h12.9a2.4 2.4 0 0 1 0 4.8H4.8a2.4 2.4 0 0 1 0-4.8z"/>
    <path d="M7.6 12h.01M10.8 12h.01M14 12h.01M16.8 12h.01"/></g>`),
  // 행진곡풍 — 작은북
  march: I(`<path d="M12 6.6c4.4 0 8 1.3 8 2.9s-3.6 2.9-8 2.9-8-1.3-8-2.9 3.6-2.9 8-2.9z"/>
    <path d="M4 9.5v5.2c0 1.6 3.6 2.9 8 2.9s8-1.3 8-2.9V9.5"/>
    <path d="M7.4 11.4 9.8 15M16.6 11.4 14.2 15M12 11.9v3.6"/>`),
  // 팝·재즈풍 — 건반
  pop: I(`<path d="M3.6 6.8h16.8v10.4H3.6z"/><path d="M9.2 6.8v10.4M14.8 6.8v10.4"/>
    <path d="M7.4 6.8h2.2v6H7.4zM13 6.8h2.2v6H13zM17.4 6.8h2.2v6h-2.2z"/>`),
};
/* 꾸러미에 없는 편성을 고르게 두지 않는다. 고를 수 있는데 안 바뀌는 것보다
 * 애초에 없는 편이 낫다 — 원장님이 "왜 안 바뀌지" 로 헤매지 않는다. */
const have = (song, key) => (song && song.variants
  ? new Set(song.variants.map((v) => v[key])) : null);

/** 고를 수 있는 것만 남긴다. 하나도 안 남으면 전부 보여 준다(필터가 곧 고장이다). */
const usable = (all, allowed) => {
  const list = allowed ? all.filter(([k]) => allowed.has(k)) : all;
  return list.length ? list : all;
};

/* 편성을 그림 단추로 — 「동화풍」이 무엇인지 **눌러 보기 전에** 보이게.
 * select 로는 그림을 못 넣는다. 그래서 단추다. */
const styleButtons = (cur, song) => usable(STYLE_LABEL, have(song, 'style'))
  .map(([k, v]) => `<button data-k="${k}" aria-pressed="${k === cur}"${
    k === cur ? ' class="on"' : ''}>${STYLE_ICON[k] || ''}<span>${v}</span></button>`)
  .join('');

/* 두께는 셋뿐이라 카운트인과 같은 단계 단추로. 그림 단추 옆에 select 하나만
 * 남아 있으면 그 줄만 덜 만든 것처럼 보인다. */
const levelSteps = (cur, song) => usable(LEVEL_LABEL, have(song, 'level'))
  .map(([k, v]) => `<button data-k="${k}" aria-pressed="${k === cur}"${
    k === cur ? ' class="on"' : ''}>${v}</button>`)
  .join('');

function wirePlay(song, settings, student) {
  const persist = () => store.saveSettings(student, song.id, settings);
  const refreshBars = () => {
    paintTicks();
    const n = player.totalBars || 1;
    ['loopFrom', 'loopTo'].forEach((id) => { $(`#${id}`).max = n; });
    $('#loopTo').value = n;
    $('#loopToVal').textContent = n;
  };
  refreshBars();
  $('#dur').textContent = mmss(player.totalSeconds);

  $('#play').onclick = () => {
    if (player.playing) { player.pause(); $('#play').textContent = '▶'; }
    else { player.play(); $('#play').textContent = '❚❚'; }
  };
  $('#rewind').onclick = () => { player.seek(0); paint(); };
  $('#fade').onclick = async () => {
    $('#fade').classList.add('active');
    await player.fadeOut();
    $('#fade').classList.remove('active');
    $('#play').textContent = '▶';
    toast('반주를 내렸습니다.');
  };
  $('#bar').onclick = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    player.seek(((e.clientX - r.left) / r.width) * player.totalBeats);
    paint();
  };

  $('#bpm').oninput = (e) => {
    settings.bpm = Number(e.target.value);
    player.setTempo(settings.bpm);
    $('#bpmVal').textContent = `♩=${settings.bpm}`;
    $('#dur').textContent = mmss(player.totalSeconds);
  };
  $('#bpm').onchange = persist;
  $('#tr').oninput = (e) => {
    settings.transpose = Number(e.target.value);
    player.setTranspose(settings.transpose);
    $('#trVal').textContent = fmtTr(settings.transpose);
  };
  $('#tr').onchange = persist;
  $('#vol').oninput = (e) => {
    settings.volume = Number(e.target.value) / 100;
    player.setVolume(settings.volume);
    $('#volVal').textContent = e.target.value;
  };
  $('#vol').onchange = persist;

  view.querySelectorAll('#countIn button').forEach((b) => {
    b.onclick = () => {
      settings.countIn = Number(b.dataset.n);
      player.countInBars = settings.countIn;
      store.countInBars = settings.countIn;
      view.querySelectorAll('#countIn button').forEach((x) => x.classList.remove('on'));
      b.classList.add('on');
      persist();
    };
  });

  $('#cueOut').onclick = pickCueOutput;
  // 저장해 둔 장치를 다시 붙인다. 이어폰을 뽑았으면 조용히 원래대로 (⑤-4).
  if (store.cueOutput.id) {
    player.setCueOutput(store.cueOutput.id).then((ok) => {
      if (!ok) { store.cueOutput = { id: '', label: '' }; }
      const el = $('#cueOut');
      if (el) el.textContent = cueLabel();
    });
  }

  const reload = async (key, value) => {
    settings[key] = value;
    persist();
    const wasPlaying = player.playing;
    player.pause();
    try {
      await loadSong(song, settings);
      refreshBars();
      $('#dur').textContent = mmss(player.totalSeconds);
      if (wasPlaying) player.play(0);
    } catch (e) { toast(e.message); }
  };
  // 고른 것을 또 고르면 소리만 끊기고 달라지는 게 없다. 그때는 아무것도 안 한다.
  const pickGroup = (sel, key) => view.querySelectorAll(`${sel} button`).forEach((b) => {
    b.onclick = () => {
      if (b.classList.contains('on')) return;
      view.querySelectorAll(`${sel} button`).forEach((x) => {
        x.classList.remove('on');
        x.setAttribute('aria-pressed', 'false');
      });
      b.classList.add('on');
      b.setAttribute('aria-pressed', 'true');
      reload(key, b.dataset.k);
    };
  });
  pickGroup('#style', 'style');
  pickGroup('#level', 'level');

  $('#loopBtn').onclick = () => {
    const card = $('#loopCard');
    card.hidden = !card.hidden;
    if (!card.hidden) applyLoop();
    else { player.setLoop(null, null); }
  };
  const applyLoop = () => {
    let a = Number($('#loopFrom').value);
    let b = Number($('#loopTo').value);
    if (b < a) { b = a; $('#loopTo').value = b; }
    $('#loopFromVal').textContent = a;
    $('#loopToVal').textContent = b;
    player.setLoopBars(a, b);
    player.seekBar(a);
  };
  $('#loopFrom').oninput = applyLoop;
  $('#loopTo').oninput = applyLoop;
  $('#loopOff').onclick = () => {
    player.setLoop(null, null);
    $('#loopCard').hidden = true;
    toast('구간 반복을 껐습니다.');
  };

  $('#share').onclick = async () => {
    const q = new URLSearchParams({
      song: song.id, bpm: settings.bpm, style: settings.style, level: settings.level,
      transpose: settings.transpose, volume: settings.volume.toFixed(2),
      countIn: settings.countIn,
    });
    if (student) q.set('student', student);
    const url = `${location.origin}${location.pathname}#/play?${q}`;
    try {
      if (navigator.share) await navigator.share({ title: song.title, url });
      else { await navigator.clipboard.writeText(url); toast('링크를 복사했습니다.'); }
    } catch (e) { prompt('이 주소를 보내세요', url); }
  };

  player.onTick = paint;
  player.onEnd = () => {
    $('#play').textContent = '▶';
    if (state.queue) nextInQueue();
  };
  paint();
}

function paint() {
  const total = player.totalBeats || 1;
  const at = Math.max(0, Math.min(total, player.positionBeat));
  const pct = (at / total) * 100;

  $('#fill').style.clipPath = `inset(0 ${(100 - pct).toFixed(2)}% 0 0)`;
  const head = $('#head');
  if (head) head.style.left = `${pct}%`;

  $('#pos').textContent = mmss(at * 60 / player.bpm);
  // 끝 화음이 한 마디 더 울려도 「9 / 8마디」라고 하지 않는다
  const lastBar = (state.song && state.song.measures) || player.totalBars || 1;
  $('#barno').textContent = Math.min(player.bar, lastBar);

  const bar = $('#bar');
  if (bar) {
    bar.setAttribute('aria-valuenow', Math.min(player.bar, lastBar));
    bar.setAttribute('aria-valuemax', lastBar);
  }

  // 지금 화음. 무대에서 눈이 제일 먼저 가는 글자라 바뀔 때만 건드린다.
  const song = state.song;
  const now = $('#chordNow');
  if (song && now) {
    const name = chordAt(song, at) || '—';
    if (now.textContent !== name) now.textContent = name;
    const nx = $('#chordNext');
    const next = chordNext(song, at);
    const bars = next
      ? Math.max(0, Math.round((next.at - at) / (player.beatsPerBar || 4)))
      : 0;
    const text = next ? `다음 <b>${next.name}</b>${bars ? ` · ${bars}마디 뒤` : ''}` : '';
    if (nx && nx.innerHTML !== text) nx.innerHTML = text;
  }

  $('#fade').disabled = !player.playing;
  const stage = $('#stage');
  if (stage) stage.classList.toggle('playing', player.playing);
}

/** 마디 눈금을 곡의 마디 수에 맞춰 그린다 (반복 그라데이션의 간격 하나만 준다). */
function paintTicks() {
  const el = $('#ticks');
  if (!el) return;
  // 눈금은 **악보의 마디 수**로 그린다.
  //
  // 엔진은 `ceil(전체박 / 마디당박)` 으로 세는데, 마지막 화음이 한 마디를 꽉 채워
  // 울리면 8마디 곡이 9로 세어진다. 머리말은 악보대로 「8마디」라고 말하고 있으니
  // 타임라인만 9라고 하면 **화면이 두 말을 하는 것**이다. 원장님께 맞는 답은
  // 악보 쪽이다. 진행 위치는 박으로 재니 마지막 칸이 꽉 차는 것으로 보일 뿐이다.
  const bars = (state.song && state.song.measures) || player.totalBars || 1;
  // 마디가 너무 많으면 눈금이 회색 덩어리가 된다 — 그때는 4마디마다.
  const step = bars > 48 ? 4 : 1;
  el.style.setProperty('--bar-w', `${(100 / bars) * step}%`);
}

/* ---------- 카운트인을 어디로 들을지 (⑤-4) ----------
 *
 * "스피커로 / 이어폰으로 원장님만 듣기 선택". 반주는 홀 스피커로 나가고 딸깍 소리만
 * 원장님 이어폰으로 빼려면 출력 장치를 둘로 나눠야 한다 — `AudioContext.setSinkId`.
 * 크로미움 110+ 에만 있다. 아이패드 사파리에는 없어서, 없으면 그렇다고 말해 준다.
 */
function cueLabel() {
  const c = store.cueOutput;
  return c.id ? `🎧 ${c.label || '이어폰'}` : '🔊 반주와 같이';
}

async function listOutputs() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return [];
  const all = await navigator.mediaDevices.enumerateDevices();
  return all.filter((d) => d.kind === 'audiooutput' && d.deviceId);
}

async function pickCueOutput() {
  if (store.cueOutput.id) {                       // 누르면 먼저 원래대로 되돌린다
    store.cueOutput = { id: '', label: '' };
    await player.setCueOutput('');
    $('#cueOut').textContent = cueLabel();
    toast('카운트인을 반주와 같은 곳으로 보냅니다.');
    return;
  }
  if (!Player.canRouteCue) {
    toast('이 브라우저는 소리를 두 곳으로 나눠 보내지 못합니다 (크롬에서 됩니다).');
    return;
  }
  let dev = null;
  try {
    if (navigator.mediaDevices.selectAudioOutput) {
      dev = await navigator.mediaDevices.selectAudioOutput();   // 브라우저 기본 선택창
    } else {
      const outs = await listOutputs();
      if (!outs.length) { toast('고를 수 있는 출력 장치가 없습니다.'); return; }
      const names = outs.map((d, i) => `${i + 1}. ${d.label || '장치 ' + (i + 1)}`);
      const pick = prompt(`카운트인을 들을 곳\n${names.join('\n')}`, '1');
      dev = outs[Number(pick) - 1];
    }
  } catch (e) { return; }                         // 선택창을 닫았다
  if (!dev) return;
  const ok = await player.setCueOutput(dev.deviceId);
  if (!ok) { toast('그 장치로는 보낼 수 없습니다.'); return; }
  store.cueOutput = { id: dev.deviceId, label: dev.label || '이어폰' };
  $('#cueOut').textContent = cueLabel();
  toast('카운트인은 이제 원장님에게만 들립니다.');
}

/* ---------- 발표회 큐 (⑤-3) ---------- */
async function screenProgram(q) {
  const b = await bundle();
  const idx = Number(q.get('i') || 0);
  const p = b.programs[idx];
  if (!p) { view.innerHTML = '<div class="empty">발표회 프로그램이 없습니다.</div>'; return; }
  $('#heading').textContent = p.event;
  state.queue = { program: p, at: state.queue ? state.queue.at : 0 };

  view.innerHTML = `
    <div class="card">
      <div class="muted">${esc(p.date || '')} ${esc(p.venue || '')}</div>
      <div class="tiny" style="margin-top:4px">${p.count}곡 · 약 ${p.minutes}분 ·
        순서를 누르면 그 곡으로 넘어갑니다</div>
    </div>
    <div class="rows queue">
      ${p.items.map((it, i) => `
        <button class="row ${i === state.queue.at ? 'current' : ''} ${i < state.queue.at ? 'done' : ''}"
                data-i="${i}">
          <div class="row__key">${it.order}</div>
          <div class="row__main">
            <div class="row__title">${esc(it.student)}</div>
            <div class="row__sub">${esc(it.title)} · ♩=${it.bpm} ·
              ${esc(it.style_label)} · ${esc(it.level_label)}</div>
          </div>
          ${it.missing ? '<span class="chip warn">곡 없음</span>' : ''}
          <div class="row__go">▶</div>
        </button>`).join('')}
    </div>`;

  view.querySelectorAll('[data-i]').forEach((el) => {
    el.onclick = () => openQueueItem(Number(el.dataset.i));
  });
}

function openQueueItem(i) {
  const p = state.queue.program;
  const it = p.items[i];
  if (!it || it.missing) { toast('카탈로그에 없는 곡입니다.'); return; }
  state.queue.at = i;
  const q = new URLSearchParams({ song: it.song_id, bpm: it.bpm, style: it.style,
                                  level: it.level, student: it.student });
  location.hash = `#/play?${q}`;
}

function nextInQueue() {
  const p = state.queue.program;
  if (state.queue.at + 1 >= p.items.length) { toast('마지막 순서였습니다.'); return; }
  state.queue.at += 1;
  toast(`다음: ${p.items[state.queue.at].student}`);
  location.hash = '#/program?i=0';   // 다음 곡은 원장님이 연다 (자동 재생하지 않는다)
}

/* ---------- 오프라인 준비 (⑤-1) ---------- */
$('#offline').onclick = async () => {
  if (!navigator.serviceWorker || !navigator.serviceWorker.controller) {
    toast('오프라인 준비를 쓸 수 없는 브라우저입니다.');
    return;
  }
  const b = await bundle();
  const urls = b.songs.map((s) => midiUrl(s, defaultsFor(s)));
  toast(`곡 ${urls.length}개를 내려받는 중…`);
  navigator.serviceWorker.controller.postMessage({
    type: 'precache', urls, data: [apiUrl('api/player/bundle')],
  });
};

if (navigator.serviceWorker) {
  navigator.serviceWorker.addEventListener('message', (e) => {
    if (e.data.type === 'precache-progress') toast(`${e.data.done}/${e.data.total} 내려받는 중…`);
    if (e.data.type === 'precache-done') {
      store.offlineReady = true;
      toast(`오프라인 준비 완료 — ${e.data.total}곡`);
    }
  });
  navigator.serviceWorker.register('sw.js').catch(() => { /* 파일 열기 등 */ });
  // 워커가 페이지를 잡은 뒤 목록을 한 번 더 받아 둔다. 첫 요청은 워커를 안 거쳐
  // 지나갔을 수 있어서, 이게 없으면 오프라인 목록이 브라우저 캐시 운에 달린다.
  navigator.serviceWorker.ready.then(() => {
    if (navigator.serviceWorker.controller) {
      fetch(apiUrl('api/player/bundle')).catch(() => {});
    }
  });
}

/* ---------- 시작 ---------- */
netBadge();
route();

// 스페이스=재생/정지, Esc=페이드아웃 — 현장에서 손이 바쁠 때
addEventListener('keydown', (e) => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
  const play = $('#play');
  if (e.code === 'Space' && play) { e.preventDefault(); play.click(); }
  if (e.code === 'Escape' && $('#fade') && !$('#fade').disabled) $('#fade').click();
});
