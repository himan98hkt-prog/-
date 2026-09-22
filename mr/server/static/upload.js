'use strict';
/* PDF 악보 올리기 — 지시서 9장 4단계.
 *
 * 이 화면이 하지 말아야 할 것이 하나 있다: **"올리면 끝"처럼 보이는 것.**
 * 지시서 3장이 "'PDF 넣으면 바로 완성'을 약속하지 말 것"이라고 못 박았고,
 * 2.2 표를 보면 인식 90~95% 에서 32마디 중 2~6마디가 틀린다. 그래서 인식이
 * 끝나면 화면이 "완료"가 아니라 **"화성 확인 대기"** 로 간다.
 */
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// 한 대의 태블릿 = 한 학원. 계정은 주소로 바꿔 끼울 수 있게 해 둔다.
const ACCOUNT = new URLSearchParams(location.search).get('account') || '우리학원';
let picked = null;
let timer = null;

function say(text, kind) {
  const el = $('#msg');
  el.textContent = text;
  el.className = 'msg' + (kind ? ' ' + kind : '');
  el.hidden = !text;
}

/* ---------- 파일 고르기 ---------- */
function choose(file) {
  if (!file) return;
  const looksPdf = file.type === 'application/pdf' || /\.pdf$/i.test(file.name);
  if (!looksPdf) {
    say('PDF 파일만 올릴 수 있습니다. (' + esc(file.name) + ')', 'bad');
    return;
  }
  picked = file;
  $('#picked').hidden = false;
  $('#picked').textContent = `${file.name} · ${Math.round(file.size / 1024)} KB`;
  if (!$('#title').value) {
    $('#title').value = file.name.replace(/\.pdf$/i, '');
  }
  $('#go').disabled = false;
  say('');
}

const drop = $('#drop');
drop.addEventListener('click', (e) => {
  if (e.target.closest('input, button, label')) return;
  $('#file').click();
});
$('#file').addEventListener('change', (e) => choose(e.target.files[0]));
['dragenter', 'dragover'].forEach((n) => drop.addEventListener(n, (e) => {
  e.preventDefault();
  drop.classList.add('over');
}));
['dragleave', 'drop'].forEach((n) => drop.addEventListener(n, (e) => {
  e.preventDefault();
  drop.classList.remove('over');
}));
drop.addEventListener('drop', (e) => choose(e.dataTransfer.files[0]));

/* ---------- 올리기 ---------- */
drop.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!picked) return;
  const body = new FormData();
  body.append('file', picked);
  body.append('account', ACCOUNT);
  body.append('title', $('#title').value.trim());
  $('#go').disabled = true;
  say('올리는 중…');
  try {
    const r = await fetch('/api/uploads', { method: 'POST', body });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '올리지 못했습니다.');
    say(`접수했습니다 — ${d.pages}쪽. ${d.provider === 'manual'
      ? '악보 인식이 끝나면 화성 확인 화면에 나타납니다.'
      : '악보를 인식하는 중입니다.'}`, 'good');
    picked = null;
    $('#file').value = '';
    $('#title').value = '';
    $('#picked').hidden = true;
    await refresh();
  } catch (err) {
    say(err.message, 'bad');
    $('#go').disabled = false;
  }
});

/* ---------- 목록 ---------- */
function quotaCards(q) {
  // 지시서 8.2 의 단가를 그대로 보여 준다. 남은 몫을 모르면 원장님이 계획을 못 세운다.
  const cards = [
    ['남은 이번 달 몫', `${q.remaining}쪽`],
    ['이번 달 쓴 양', `${q.used} / ${q.limit}쪽`],
    ['이번 달 비용', `${q.spent_won.toLocaleString()}원`],
    ['한 번에', `${q.max_pages_per_upload}쪽까지`],
  ];
  $('#quota').innerHTML = cards.map(([label, value]) =>
    `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`).join('');
}

function jobRow(j) {
  const bits = [`${j.pages}쪽`, `${j.won.toLocaleString()}원`, esc(j.filename)];
  if (j.detail) bits.push(`<span class="detail">${esc(j.detail)}</span>`);
  const actions = [];
  if (j.state === 'review') {
    actions.push(`<a class="pill review" href="${esc(j.verify_url)}">화성 확인하러 가기</a>`);
    if (j.verified) actions.push(`<button data-finish="${j.id}">확인 끝냄</button>`);
  }
  if (j.state === 'omr' || j.state === 'received') {
    actions.push(`<button data-poll="${j.id}">확인</button>`);
    actions.push(`<button data-cancel="${j.id}">취소</button>`);
  }
  return `<div class="job">
    <div class="job__main">
      <div class="job__title">${esc(j.title || j.filename)}</div>
      <div class="job__sub">${bits.join(' · ')}</div>
    </div>
    <span class="pill ${esc(j.state)}">${esc(j.label)}</span>
    ${actions.join(' ')}
  </div>`;
}

async function refresh() {
  const r = await fetch(`/api/uploads?account=${encodeURIComponent(ACCOUNT)}`);
  const d = await r.json();
  $('#who').textContent = `${ACCOUNT} · 인식 ${d.provider === 'manual' ? '신청제' : d.provider}`;
  $('#accuracy').textContent = d.accuracy_note;
  quotaCards(d.quota);
  $('#jobs').innerHTML = d.jobs.length
    ? d.jobs.map(jobRow).join('')
    : '<div class="empty">아직 올린 악보가 없습니다.</div>';
  $('#go').disabled = !picked;

  // 인식 중인 게 있으면 천천히 다시 물어본다. 없으면 폴링을 멈춘다.
  clearTimeout(timer);
  if (d.jobs.some((j) => j.state === 'omr' || j.state === 'received')) {
    timer = setTimeout(pollOpen, 5000);
  }
}

async function pollOpen() {
  const r = await fetch(`/api/uploads?account=${encodeURIComponent(ACCOUNT)}`);
  const d = await r.json();
  for (const j of d.jobs) {
    if (j.state === 'omr') await fetch(`/api/uploads/${j.id}/poll`, { method: 'POST' });
  }
  await refresh();
}

$('#jobs').addEventListener('click', async (e) => {
  const el = e.target.closest('[data-poll],[data-cancel],[data-finish]');
  if (!el) return;
  const { poll, cancel, finish } = el.dataset;
  try {
    let r;
    if (poll) r = await fetch(`/api/uploads/${poll}/poll`, { method: 'POST' });
    if (finish) r = await fetch(`/api/uploads/${finish}/finish`, { method: 'POST' });
    if (cancel) {
      if (!confirm('이 악보를 취소할까요? 이번 달 몫은 돌려드립니다.')) return;
      r = await fetch(`/api/uploads/${cancel}`, { method: 'DELETE' });
    }
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || '처리하지 못했습니다.');
    say('');
  } catch (err) {
    say(err.message, 'bad');
  }
  await refresh();
});

refresh().catch((e) => say(e.message, 'bad'));
