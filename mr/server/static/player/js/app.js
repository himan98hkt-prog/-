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
  if (song.variants) {
    const hit = song.variants.find(
      (v) => v.style === settings.style && v.level === settings.level);
    return apiUrl((hit || song.variants[0]).url);
  }
  const q = new URLSearchParams({ style: settings.style, level: settings.level });
  return apiUrl(`${song.midi}?${q}`);
}

async function loadSong(song, settings) {
  const r = await fetch(midiUrl(song, settings));
  if (!r.ok) throw new Error('반주를 받지 못했습니다');
  // 서비스워커가 요청한 편성이 없어 기본 편성으로 대신 준 경우 (오프라인)
  if (r.headers.get('X-MR-Fallback') === 'default') {
    toast('오프라인이라 기본 편성으로 재생합니다.');
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
    ${b.programs.length ? `<button class="row" id="toProgram">
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
      <h2 class="muted" style="margin:18px 0 8px">${esc(book || '기타')}</h2>
      <div class="rows">
        ${songs.map((s) => `
          <button class="row" data-song="${esc(s.id)}">
            <div class="row__main">
              <div class="row__title">${esc(s.title)}</div>
              <div class="row__sub">♩=${s.bpm} · ${esc(s.key_label || s.key)} · ${s.measures}마디</div>
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
    <div class="now">
      ${student ? `<div class="now__student">${esc(student)}</div>` : ''}
      <h2 class="now__title">${esc(song.title)}</h2>
      <div class="now__meta">${esc(song.composer || song.book || '')} ·
        ${esc(song.key_label || song.key)} · ${song.measures}마디</div>
    </div>

    <div class="card">
      <div class="transport">
        <button class="round" id="rewind" title="처음으로">⏮</button>
        <button class="big" id="play" aria-label="재생">▶</button>
        <button class="round" id="loopBtn" title="구간 반복">⟳</button>
      </div>
      <div class="bar" id="bar"><i id="fill"></i></div>
      <div class="times"><span id="pos">0:00</span>
        <span id="barno" class="tiny">1마디</span><span id="dur">0:00</span></div>
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
      <div class="ctl"><span class="ctl__label">편성</span>
        <select id="style">${styleOptions(settings.style, song)}</select></div>
      <div class="ctl"><span class="ctl__label">두께</span>
        <select id="level">${levelOptions(settings.level, song)}</select></div>
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
const STYLE_LABEL = [['strings', '현악 앙상블'], ['chamber', '실내악'],
  ['orchestra', '풀 오케스트라'], ['fairytale', '동화풍'], ['warm', '따뜻한 소편성'],
  ['march', '행진곡풍'], ['pop', '팝·재즈풍']];
const LEVEL_LABEL = [['simple', '간단'], ['normal', '보통'], ['rich', '풍성']];

/* 꾸러미에 없는 편성을 고르게 두지 않는다. 고를 수 있는데 안 바뀌는 것보다
 * 애초에 없는 편이 낫다 — 원장님이 "왜 안 바뀌지" 로 헤매지 않는다. */
function options(all, cur, allowed) {
  const list = allowed ? all.filter(([k]) => allowed.has(k)) : all;
  return (list.length ? list : all)
    .map(([k, v]) => `<option value="${k}"${k === cur ? ' selected' : ''}>${v}</option>`)
    .join('');
}
const styleOptions = (cur, song) => options(STYLE_LABEL, cur,
  song && song.variants ? new Set(song.variants.map((v) => v.style)) : null);
const levelOptions = (cur, song) => options(LEVEL_LABEL, cur,
  song && song.variants ? new Set(song.variants.map((v) => v.level)) : null);

function wirePlay(song, settings, student) {
  const persist = () => store.saveSettings(student, song.id, settings);
  const refreshBars = () => {
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
  $('#style').onchange = (e) => reload('style', e.target.value);
  $('#level').onchange = (e) => reload('level', e.target.value);

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
  $('#fill').style.width = `${(at / total) * 100}%`;
  $('#pos').textContent = mmss(at * 60 / player.bpm);
  $('#barno').textContent = `${player.bar}마디`;
  $('#fade').disabled = !player.playing;
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
          <div class="row__main">
            <div class="row__title">${it.order}. ${esc(it.student)}</div>
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
