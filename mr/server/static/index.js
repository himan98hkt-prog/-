'use strict';

const $ = (s) => document.querySelector(s);

function mmss(sec) {
  if (!sec) return '—';
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${m}분 ${String(s).padStart(2, '0')}초`;
}

const STATUS = { verified: '확인 완료', analyzed: '확인 대기', new: '분석 전' };

async function load() {
  const [stats, songs] = await Promise.all([
    fetch('/api/stats').then((r) => r.json()),
    fetch('/api/songs').then((r) => r.json()),
  ]);

  $('#root').textContent = stats.root;
  const done = stats.total ? Math.round((stats.verified / stats.total) * 100) : 0;
  $('#stats').innerHTML = [
    ['곡', stats.total], ['확인 완료', `${stats.verified} (${done}%)`],
    ['확인 대기', stats.analyzed], ['평균 검수', mmss(stats.avg_verify_seconds)],
    ['20분 초과', stats.over_20min], ['반주 MIDI', `${stats.midi_kb} KB`],
  ].map(([k, v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join('');

  if (!songs.songs.length) {
    $('#list').innerHTML =
      '<div class="empty">아직 곡이 없습니다. <code>python3 catalog_cli.py import</code> 로 악보를 넣으세요.</div>';
    return;
  }

  const rows = songs.songs.map((s) => `
    <tr>
      <td><a href="verify.html?id=${encodeURIComponent(s.id)}">${esc(s.title)}</a>
          <div class="sub" style="font-size:12px;color:var(--muted)">${esc(s.book || s.composer || '')}</div></td>
      <td><span class="pill ${s.status}">${STATUS[s.status]}</span></td>
      <td class="num">${s.level}</td>
      <td>${esc(s.key)} · ${esc(s.time)}</td>
      <td class="num">${s.measures}</td>
      <td class="num">${s.low ? `<span style="color:#8a6512">${s.low}</span>` : '0'}</td>
      <td class="num">${mmss(s.verify_seconds)}</td>
      <td><a href="verify.html?id=${encodeURIComponent(s.id)}">확인 화면 →</a></td>
    </tr>`).join('');

  $('#list').innerHTML = `<table>
    <thead><tr><th>곡</th><th>상태</th><th>난이도</th><th>조성·박자</th>
      <th>마디</th><th>확인 필요</th><th>검수 시간</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

load().catch((e) => { $('#list').innerHTML = `<div class="empty">오류: ${esc(e.message)}</div>`; });
