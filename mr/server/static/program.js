'use strict';
/* 발표회 운영 화면 — 지시서 모듈 ⑤.
 *
 *   "원장님은 재생만 누름. 원장님이 진짜 돈 낼 기능."      (⑤-3 큐 리스트)
 *   "아이가 멈췄을 때 3초 안에 반주만 사라짐."             (⑤-2 페이드아웃)
 *
 * 무대 장면은 CSS 로 그린다. 이미지·영상 파일이 있으면 얹고, 없으면 그대로 간다 —
 * 연주홀 와이파이는 믿을 수 없다는 것이 ⑤-1 의 전제다.
 */

const $ = (s) => document.querySelector(s);
const audio = $('#audio');
const FADE_SECONDS = 3;          // 지시서 검증 기준: 버튼 -> 3초 내 완전 무음

const state = {
  program: null,
  at: 0,              // 지금 순서 (0-based)
  urls: new Map(),    // song key -> audio url
  fading: false,
};

/* ---------- 무대 배경 ---------- */
// 파일이 있으면 쓰고 없으면 CSS 무대로 둔다. 404 를 조용히 삼킨다.
(function stageMedia() {
  // 서버가 무엇이 있는지 알려 준다. 없는 파일을 찔러 보면 콘솔이 404 로 지저분해진다.
  fetch('/api/stage').then((r) => r.json()).then((m) => {
    if (m.video) {
      const v = $('#bg');
      v.src = m.video;
      v.addEventListener('loadeddata', () => {
        v.classList.add('on');
        v.play().catch(() => {});
      });
      v.load();
    } else if (m.image) {
      const el = document.createElement('div');
      el.className = 'stage__media on';
      el.style.cssText =
        `background:url(${m.image}) center/cover no-repeat;position:absolute;inset:0`;
      $('#stage').insertBefore(el, $('.stage__paint').nextSibling);
    }
  }).catch(() => {});

  // 빛기둥 안을 떠다니는 먼지
  const box = $('#motes');
  for (let i = 0; i < 26; i++) {
    const m = document.createElement('i');
    m.className = 'mote';
    m.style.left = `${30 + Math.random() * 40}%`;
    m.style.bottom = `${Math.random() * 30}%`;
    m.style.setProperty('--dx', `${(Math.random() - 0.5) * 90}px`);
    m.style.animationDuration = `${14 + Math.random() * 16}s`;
    m.style.animationDelay = `${-Math.random() * 26}s`;
    box.appendChild(m);
  }
})();

/* ---------- 유틸 ---------- */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function mmss(sec) {
  if (!isFinite(sec) || sec < 0) return '—';
  return `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, '0')}`;
}
let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('on'), 2600);
}

/* ---------- 그리기 ---------- */
function render() {
  const p = state.program;
  const it = p.items[state.at];

  $('#event').innerHTML = [
    esc(p.event), p.date && esc(p.date), p.venue && esc(p.venue),
    `${p.count}곡 · 약 ${p.minutes}분`,
  ].filter(Boolean).join('<span class="dot"></span>');

  $('#now').innerHTML = it ? `
    <div class="now-order">${it.order}번째</div>
    <h1 class="now-student">${esc(it.student)}</h1>
    <p class="now-song">${esc(it.title)}</p>
    <p class="now-meta">${esc(it.composer || it.book || '')}${it.composer || it.book ? ' · ' : ''}
      <span class="tempo">♩<span class="n">=${it.bpm}</span></span> ·
      ${esc(it.style_label)} · ${esc(it.level_label)}
      ${it.count_in ? ` · 카운트인 ${it.count_in}마디` : ''}
      ${it.missing ? ' · <span class="warn">카탈로그에 없는 곡</span>' : ''}
      ${!it.missing && !it.verified ? ' · <span class="warn">화성 미확인</span>' : ''}</p>` : '';
  const nowEl = $('#now').firstElementChild;
  if (nowEl) $('#now').querySelectorAll('.now-order,.now-student,.now-song,.now-meta')
    .forEach((el, i) => { el.classList.add('fade-in-up'); el.style.animationDelay = `${i * 60}ms`; });

  const nxt = p.items[state.at + 1];
  $('#upnext').innerHTML = nxt
    ? `다음 ▸ <b>${esc(nxt.student)}</b> — ${esc(nxt.title)} (♩=${nxt.bpm}, ${esc(nxt.style_label)})`
    : '마지막 순서입니다.';

  $('#cues').innerHTML = p.items.map((x, i) => `
    <div class="cue ${i === state.at ? 'current' : ''} ${i < state.at ? 'done' : ''}"
         data-i="${i}">
      <div class="cue__no">${i < state.at ? '✓' : x.order}</div>
      <div>
        <div class="cue__who">${esc(x.student)}</div>
        <div class="cue__what">${esc(x.title)}${x.note ? ' · ' + esc(x.note) : ''}</div>
      </div>
      <div class="cue__meta">♩=${x.bpm} · ${esc(x.style_label)} · ${esc(x.level_label)}</div>
    </div>`).join('');

  $('#prev').disabled = state.at === 0;
  $('#next').disabled = state.at >= p.items.length - 1;
}

/* ---------- 소리 ---------- */
function keyOf(it) { return `${it.song_id}|${it.style}|${it.level}|${it.bpm}`; }

async function urlFor(it) {
  const k = keyOf(it);
  if (state.urls.has(k)) return state.urls.get(k);
  const q = new URLSearchParams({ style: it.style, level: it.level,
                                  bpm: it.bpm, mix: 'mr' });
  const r = await fetch(`/api/songs/${encodeURIComponent(it.song_id)}/audio?${q}`);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  const info = await r.json();
  state.urls.set(k, info.url);
  return info.url;
}

async function play() {
  const it = state.program.items[state.at];
  if (!it) return;
  if (it.missing) { toast('카탈로그에 없는 곡입니다.'); return; }
  cancelFade();
  try {
    $('#play').textContent = '준비 중…';
    audio.src = await urlFor(it);
    audio.volume = 1;
    await audio.play();
    $('#play').textContent = '❚❚ 일시정지';
    prefetchNext();
  } catch (e) {
    $('#play').textContent = '▶ 재생';
    toast(`재생 실패: ${e.message}`);
  }
}

// 다음 곡을 미리 받아 둔다. 무대에서 기다리는 일이 없도록.
function prefetchNext() {
  const nxt = state.program.items[state.at + 1];
  if (nxt && !nxt.missing) urlFor(nxt).catch(() => {});
}

/* 페이드아웃 — 지시서 검증 기준: 버튼을 누르면 3초 안에 완전 무음 */
let fadeTimer = null;
function fadeOut() {
  if (audio.paused || state.fading) return;
  state.fading = true;
  $('#fade').classList.add('active');
  const from = audio.volume;
  const t0 = performance.now();
  clearInterval(fadeTimer);
  fadeTimer = setInterval(() => {
    const k = Math.min(1, (performance.now() - t0) / (FADE_SECONDS * 1000));
    audio.volume = Math.max(0, from * (1 - k));
    if (k >= 1) {
      clearInterval(fadeTimer);
      audio.pause();
      audio.volume = 1;
      state.fading = false;
      $('#fade').classList.remove('active');
      $('#play').textContent = '▶ 재생';
      toast('반주를 내렸습니다.');
    }
  }, 40);
}
function cancelFade() {
  clearInterval(fadeTimer);
  state.fading = false;
  $('#fade').classList.remove('active');
  audio.volume = 1;
}

function go(i) {
  const p = state.program;
  state.at = Math.max(0, Math.min(p.items.length - 1, i));
  cancelFade();
  audio.pause();
  audio.removeAttribute('src');
  $('#play').textContent = '▶ 재생';
  $('#barfill').style.width = '0';
  $('#elapsed').textContent = '0:00';
  $('#total').textContent = '—';
  render();
}

/* ---------- 이벤트 ---------- */
$('#play').addEventListener('click', () => {
  if (!audio.paused) { audio.pause(); $('#play').textContent = '▶ 재생'; return; }
  play();
});
$('#fade').addEventListener('click', fadeOut);
$('#prev').addEventListener('click', () => go(state.at - 1));
$('#next').addEventListener('click', () => go(state.at + 1));
$('#cues').addEventListener('click', (e) => {
  const row = e.target.closest('.cue[data-i]');
  if (row) go(Number(row.dataset.i));
});

audio.addEventListener('timeupdate', () => {
  $('#elapsed').textContent = mmss(audio.currentTime);
  if (isFinite(audio.duration)) {
    $('#total').textContent = mmss(audio.duration);
    $('#barfill').style.width = `${(audio.currentTime / audio.duration) * 100}%`;
  }
});
audio.addEventListener('play', () => { $('#fade').disabled = false; });
audio.addEventListener('pause', () => { $('#fade').disabled = true; });
audio.addEventListener('ended', () => {
  $('#play').textContent = '▶ 재생';
  // 다음 곡 자동 대기 — 자동 재생은 하지 않는다. 무대는 원장님이 연다.
  if (state.at < state.program.items.length - 1) {
    go(state.at + 1);
    toast('다음 순서 대기 중입니다.');
  }
});

document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return;
  if (e.code === 'Space') { e.preventDefault(); $('#play').click(); }
  if (e.code === 'Escape') fadeOut();
  if (e.code === 'ArrowRight') go(state.at + 1);
  if (e.code === 'ArrowLeft') go(state.at - 1);
});

/* ---------- 시작 ---------- */
(async function boot() {
  const idx = new URLSearchParams(location.search).get('i') || '0';
  try {
    const r = await fetch(`/api/programs/${encodeURIComponent(idx)}`);
    if (!r.ok) throw new Error('프로그램이 없습니다');
    state.program = await r.json();
    if (!state.program.items.length) {
      $('#event').textContent = state.program.event;
      $('#cues').innerHTML = '<div class="empty">큐가 비어 있습니다.</div>';
      return;
    }
    render();
  } catch (e) {
    $('#event').textContent = '불러오지 못했습니다';
    $('#cues').innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  }
})();
