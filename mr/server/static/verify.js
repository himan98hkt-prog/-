'use strict';
/* 화성 확인 화면 — 지시서 10장.
 *
 *   음표가 아니라 화음 이름만 보여준다. 악보를 음표 단위로 교정하면 40분,
 *   화성만 보면 3~5분이다.
 *
 * 구간 재생은 서버를 다시 부르지 않는다. 받아 둔 mp3 안에서
 *   초 = 마디 시작(4분음표 단위) × 60 / bpm
 * 으로 건너뛰고, 마디 끝에서 멈춘다. 템포가 일정하므로 이 환산이 정확하다.
 */

const $ = (s) => document.querySelector(s);
const songId = new URLSearchParams(location.search).get('id');

const state = {
  view: null,          // 서버가 준 곡 구조
  dirty: new Map(),    // "bar:i" -> label (아직 저장 안 한 교정)
  audioDirty: true,    // 화성/설정이 바뀌어 반주를 다시 만들어야 하는가
  secPerQl: 0.625,
  lead: 0,
  url: null,
  stopAt: null,        // 구간 재생 종료 시각(초)
  playingBar: null,
  started: Date.now(), // 검수 시간 측정 시작
  savedSeconds: 0,
};

const audio = $('#audio');

/* ---------- 유틸 ---------- */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function elapsed() { return Math.round((Date.now() - state.started) / 1000); }
function say(msg, isErr) {
  const el = $('#status');
  el.textContent = msg || '';
  el.className = 'status' + (isErr ? ' err' : '');
}
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch (e) { /* 본문 없음 */ }
    throw new Error(detail);
  }
  return r.json();
}

/* ---------- 그리기 ---------- */
function optionsHtml(choices, current) {
  const mk = (v) => `<option value="${esc(v)}"${v === current ? ' selected' : ''}>${esc(v)}</option>`;
  let html = '<optgroup label="이 조성의 화음">' + choices.in_key.map(mk).join('') + '</optgroup>';
  html += '<optgroup label="그 외">' + choices.all.map(mk).join('') + '</optgroup>';
  if (!choices.in_key.includes(current) && !choices.all.includes(current)) {
    html = mk(current) + html;
  }
  return html;
}

function render() {
  const v = state.view;
  $('#title').textContent = v.title;
  $('#meta').textContent =
    `${v.key_label || v.key} · ${v.time} · ${v.measures}마디` + (v.low_count ? ` · 확인 필요 ${v.low_count}곳` : '');
  document.title = `${v.title} — 화성 확인`;

  $('#bars').innerHTML = v.bars.map((bar) => {
    const cells = bar.cells.map((c) => {
      const key = `${bar.bar}:${c.i}`;
      const label = state.dirty.has(key) ? state.dirty.get(key) : c.label;
      const cls = [c.low ? 'low' : '', label !== c.auto ? 'changed' : ''].join(' ').trim();
      return `<select class="${cls}" data-bar="${bar.bar}" data-i="${c.i}"
                title="엔진 판정: ${esc(c.auto)}${c.alts.length ? ' / 다음 후보: ' + esc(c.alts.join(', ')) : ''}"
              >${optionsHtml(v.choices, label)}</select>`;
    }).join('');
    const weak = bar.cells.filter((c) => c.low);
    const hint = weak.length && weak[0].alts.length
      ? `다음 후보: ${esc(weak[0].alts.slice(0, 2).join(' / '))}` : '';
    return `<div class="bar" data-bar="${bar.bar}">
      <div class="bar-head">
        <span class="bar-no">m${bar.m}</span>
        <button data-play="${bar.bar}" title="이 마디만 들어보기">▶</button>
      </div>
      <div class="cells">${cells}</div>
      <div class="hint">${hint}</div>
    </div>`;
  }).join('');

  fill('#style', v.styleList, v.style);
  fill('#level', v.levelList, v.level_name);
  fill('#bpm', bpmOptions(v), String(v.bpm));
  // 화성을 확인하려면 선율이 같이 들려야 한다. 그래서 확인 화면의 기본은 full.
  // 원장님께 나가는 것은 mr(반주만)이고, 여기서도 골라 들을 수 있다.
  fill('#mix', v.mixList, $('#mix').value || 'full');
  $('#done').textContent = v.verified ? '확인 완료됨' : '확인 완료';
  state.savedSeconds = v.verify_seconds;
}

/* 이 곡의 템포와 추천 템포를 반드시 포함시킨다.
 * 곡의 bpm(예: 126)이 보기에 없으면 브라우저가 멋대로 첫 항목을 고르고,
 * 그 상태로 저장하면 곡에 저장된 템포가 조용히 덮어써진다. */
const BPM_PRESET = [60, 66, 72, 76, 84, 92, 96, 104, 112, 120, 132, 144];
function bpmOptions(v) {
  const all = new Set(BPM_PRESET.map(Number));
  all.add(Number(v.bpm));
  (v.recommended_bpm || []).forEach((b) => all.add(Number(b)));
  return [...all].sort((a, b) => a - b)
    .map((b) => ({ key: String(b), label: String(b) }));
}

function fill(sel, items, current) {
  const el = $(sel);
  if (!items) return;
  const list = items.slice();
  // 현재 값이 보기에 없으면 넣어 준다 — 없는 채로 두면 다른 값이 선택된다
  if (current != null && !list.some((o) => o.key === current)) {
    list.unshift({ key: current, label: current });
  }
  el.innerHTML = list.map((o) =>
    `<option value="${esc(o.key)}"${o.key === current ? ' selected' : ''}>${esc(o.label)}</option>`).join('');
  el.value = current;
}

/* ---------- 소리 ---------- */
async function ensureAudio() {
  if (!state.audioDirty && state.url) return;
  say('반주를 다시 만드는 중…');
  const q = new URLSearchParams({
    style: $('#style').value, level: $('#level').value,
    bpm: $('#bpm').value, mix: $('#mix').value,
  });
  const info = await api(`/api/songs/${encodeURIComponent(songId)}/audio?${q}`);
  state.url = info.url + '?v=' + Date.now();
  state.secPerQl = info.sec_per_ql;
  state.lead = info.lead_seconds || 0;   // 카운트인을 구워 넣었으면 그만큼 밀린다
  state.audioDirty = false;
  audio.src = state.url;
  audio.load();
  say(info.cached ? '' : `반주 생성 ${info.seconds}초`);
}

async function playRange(fromQl, toQl, barId) {
  try {
    // 저장하지 않은 교정이 있으면 먼저 반영해야 소리에 반영된다
    if (state.dirty.size) await save({ silent: true });
    await ensureAudio();
    await once(audio, 'loadedmetadata');      // 길이를 알아야 seek 이 먹는다
    state.stopAt = toQl == null ? null : state.lead + toQl * state.secPerQl;
    audio.currentTime = Math.max(0, state.lead + fromQl * state.secPerQl);
    markBar(barId);
    await audio.play();
  } catch (e) {
    markBar(null);
    say(`재생 실패: ${e.message}`, true);
  }
}

/** 이미 준비된 오디오면 즉시, 아니면 해당 이벤트를 기다린다. */
function once(el, event, ms = 30000) {
  if (el.readyState >= 1) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const done = () => { cleanup(); resolve(); };
    const fail = () => { cleanup(); reject(new Error('음원을 불러오지 못했습니다.')); };
    const timer = setTimeout(fail, ms);
    function cleanup() {
      clearTimeout(timer);
      el.removeEventListener(event, done);
      el.removeEventListener('error', fail);
    }
    el.addEventListener(event, done, { once: true });
    el.addEventListener('error', fail, { once: true });
  });
}

function markBar(barId) {
  state.playingBar = barId;
  document.querySelectorAll('.bar').forEach((el) => {
    el.classList.toggle('playing', String(el.dataset.bar) === String(barId));
  });
}

audio.addEventListener('timeupdate', () => {
  if (state.stopAt != null && audio.currentTime >= state.stopAt) stop();
});
audio.addEventListener('ended', () => markBar(null));

function stop() {
  audio.pause();
  state.stopAt = null;
  markBar(null);
}

/* ---------- 저장 ---------- */
async function save({ verified = null, silent = false } = {}) {
  const cells = [...state.dirty.entries()].map(([key, label]) => {
    const [bar, i] = key.split(':').map(Number);
    return { bar, i, label };
  });
  const add = elapsed();
  const body = {
    cells, verified, add_seconds: add,
    style: $('#style').value, level: $('#level').value, bpm: Number($('#bpm').value),
  };
  if (!silent) say('저장 중…');
  const v = await api(`/api/songs/${encodeURIComponent(songId)}/harmony`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  state.started = Date.now();            // 누적했으니 타이머를 되감는다
  state.dirty.clear();
  attach(v);
  render();
  if (!silent) say(verified ? '확인 완료로 저장했습니다.' : '저장했습니다.');
}

function attach(v) {
  v.styleList = state.view ? state.view.styleList : null;
  v.levelList = state.view ? state.view.levelList : null;
  v.mixList = state.view ? state.view.mixList : null;
  state.view = v;
}

/* ---------- 이벤트 ---------- */
$('#bars').addEventListener('change', (e) => {
  const sel = e.target.closest('select[data-bar]');
  if (!sel) return;
  state.dirty.set(`${sel.dataset.bar}:${sel.dataset.i}`, sel.value);
  state.audioDirty = true;               // 바꾸면 반주를 다시 만든다
  const cell = state.view.bars.find((b) => String(b.bar) === sel.dataset.bar)
    .cells.find((c) => String(c.i) === sel.dataset.i);
  sel.classList.toggle('changed', sel.value !== cell.auto);
  say(`고친 칸 ${state.dirty.size}개 — 재생하거나 저장하면 반영됩니다.`);
});

$('#bars').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-play]');
  if (!btn) return;
  const bar = state.view.bars.find((b) => String(b.bar) === btn.dataset.play);
  playRange(bar.off, bar.end, bar.bar);
});

/* ---------- 내보내기 ----------
 *
 * 화면에서 듣는 것(캐시)과 가져가는 것은 다른 일이다. 여기서는 **고른 형식들을
 * 한 번에** 굽고, 여럿이면 서버가 zip 으로 묶어 준다.
 *
 * 편성·두께·템포·듣기는 위 연장통 값을 그대로 쓴다. 여기서 또 고르게 하면
 * 「화면에서 듣던 것과 받은 파일이 다르다」가 생긴다. */
const FMT_ON = ['midi'];        // 처음 열었을 때 켜져 있는 것

async function fillExport() {
  if (state.formats) return;
  const d = await api('/api/export/formats');
  state.formats = d.formats;
  $('#exportPicks').innerHTML = d.formats.map((f) => `
    <label class="pick2">
      <input type="checkbox" value="${esc(f.key)}"${FMT_ON.includes(f.key) ? ' checked' : ''}>
      <span><b>${esc(f.label)}</b><i>${esc(f.ext)}</i>
        <em>${esc(f.desc || '')}</em></span>
    </label>`).join('');
}

/** 지금 무엇으로 나갈지 사람 말로. 받기 전에 확인할 수 있어야 한다. */
function exportNow() {
  const label = (sel) => {
    const el = $(sel);
    return el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : el.value;
  };
  $('#exportNow').textContent =
    `${label('#style')} · ${label('#level')} · ♩=${$('#bpm').value} · ${label('#mix')}`;

  // 이 화면은 **일부러** 피아노까지 틀어 준다 — 선율 없이 화음만 들어서는 그 화음이
  // 이 곡에 맞는지 판단할 수 없다. 그런데 그 상태로 내보내면 아이가 녹음된 피아노
  // 위에 겹쳐 치게 된다. 고른 값을 몰래 바꾸지는 않고, 말은 해 준다.
  const warn = $('#exportWarn');
  const mr = $('#mix').value === 'mr';
  warn.hidden = mr;
  if (!mr) {
    warn.innerHTML = '지금 <b>피아노가 들어간 음원</b>으로 나갑니다. ' +
      '아이 연습·발표회용이면 위 <b>듣기</b>를 <b>반주만</b>으로 바꾸세요.';
  }
}

function chosen() {
  return [...document.querySelectorAll('#exportPicks input:checked')].map((i) => i.value);
}

$('#export').addEventListener('click', async () => {
  const panel = $('#exportPanel');
  if (!panel.hidden) { panel.hidden = true; return; }
  try {
    await fillExport();
    exportNow();
    panel.hidden = false;
  } catch (e) { say(e.message, true); }
});

['#style', '#level', '#bpm', '#mix'].forEach((sel) =>
  $(sel).addEventListener('change', () => { if (!$('#exportPanel').hidden) exportNow(); }));

$('#exportGo').addEventListener('click', async () => {
  const formats = chosen();
  if (!formats.length) { $('#exportSay').textContent = '형식을 하나는 고르세요.'; return; }
  try {
    // **고친 칸을 먼저 저장한다.** 안 하면 기계가 처음 분석한 화성이 나간다 —
    // 화면에서 고친 시간이 통째로 버려지고, 그걸 파일을 열어 보기 전엔 모른다.
    if (state.dirty.size) {
      $('#exportSay').textContent = '고친 칸을 저장하는 중…';
      await save({ silent: true });
    }
    const q = new URLSearchParams({
      formats: formats.join(','),
      style: $('#style').value, level: $('#level').value,
      bpm: $('#bpm').value, mix: $('#mix').value,
      stems: $('#exportStems').checked ? 'true' : 'false',
    });
    $('#exportSay').textContent =
      formats.length === 1 && formats[0] === 'midi' ? '받는 중…' : '굽는 중… (곡당 몇 초)';
    // 서버가 `attachment` 로 내려 주므로 화면은 그대로 있고 내려받기만 시작된다.
    window.location.href = `/api/songs/${encodeURIComponent(songId)}/export?${q}`;
    setTimeout(() => { $('#exportSay').textContent = ''; }, 4000);
  } catch (e) {
    $('#exportSay').textContent = e.message;
  }
});

$('#play').addEventListener('click', () => playRange(0, null, null));
$('#stop').addEventListener('click', stop);
$('#save').addEventListener('click', () => save().catch((e) => say(e.message, true)));
$('#done').addEventListener('click', () =>
  save({ verified: true }).catch((e) => say(e.message, true)));

['#style', '#level', '#bpm', '#mix'].forEach((sel) =>
  $(sel).addEventListener('change', () => { state.audioDirty = true; stop(); }));

$('#reanalyze').addEventListener('click', async () => {
  if (!confirm('엔진으로 다시 분석합니다. 사람이 고친 값은 사라집니다. 계속할까요?')) return;
  try {
    const v = await api(`/api/songs/${encodeURIComponent(songId)}/reanalyze`, { method: 'POST' });
    state.dirty.clear();
    state.audioDirty = true;
    attach(v); render(); say('다시 분석했습니다.');
  } catch (e) { say(e.message, true); }
});

window.addEventListener('beforeunload', (e) => {
  if (state.dirty.size) { e.preventDefault(); e.returnValue = ''; }
});

setInterval(() => {
  const t = state.savedSeconds + elapsed();
  $('#timer').textContent = `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
}, 1000);

/* ---------- 시작 ---------- */
(async function boot() {
  if (!songId) { say('곡 id 가 없습니다.', true); return; }
  try {
    const [v, s] = await Promise.all([
      api(`/api/songs/${encodeURIComponent(songId)}`),
      api('/api/styles'),
    ]);
    state.view = v;
    v.styleList = s.styles.map((x) => ({ key: x.key, label: x.label }));
    v.levelList = s.levels;
    v.mixList = s.mixes;
    render();
    if (v.low_count) say(`확인 필요 ${v.low_count}곳이 노란색입니다. 거기부터 들어보세요.`);
  } catch (e) { say(`불러오기 실패: ${e.message}`, true); }
})();
