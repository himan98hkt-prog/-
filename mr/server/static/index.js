'use strict';

const $ = (s) => document.querySelector(s);

function mmss(sec) {
  if (!sec) return '—';
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${m}분 ${String(s).padStart(2, '0')}초`;
}

/** "약 1시간 20분" — 남은 일이 얼마나 되는지 어림잡아 주는 말. */
function roughly(sec) {
  const m = Math.round(sec / 60);
  if (m < 60) return `약 ${m}분`;
  const h = Math.floor(m / 60), r = m % 60;
  return r ? `약 ${h}시간 ${r}분` : `약 ${h}시간`;
}

/** 조성 머리글자 — 'E♭장조' → 'E♭'. 목록에서 곡을 **한 장**으로 보이게 하는 표지. */
function keyBadge(s) {
  const k = String(s.key_label || s.key || '').trim();
  const m = k.match(/^([A-G][#b♯♭]?)/);
  return m ? m[1] : (k.slice(0, 2) || '♪');
}

const STATUS = { verified: '확인 완료', analyzed: '확인 대기', new: '분석 전' };

async function load() {
  const [stats, songs] = await Promise.all([
    fetch('/api/stats').then((r) => r.json()),
    fetch('/api/songs').then((r) => r.json()),
  ]);

  // 폴더 경로 전체를 머리말에 박으면 화면마다 다른 길이의 잡음이 된다.
  // 끝 두 칸만 보이고, 전체 경로는 마우스를 올리면 나온다.
  const root = String(stats.root || '');
  const tail = root.split(/[\\/]/).filter(Boolean).slice(-2).join('/');
  $('#root').textContent = tail;
  $('#root').title = root;

  // ── 머리 패널 ── 이 화면에서 묻는 것은 하나다: **몇 곡까지 됐나.**
  const done = stats.total ? Math.round((stats.verified / stats.total) * 100) : 0;
  const remain = stats.total - stats.verified;
  const avg = stats.avg_verify_seconds;
  const aside = [
    avg ? `평균 검수 <b>${mmss(avg)}</b>` : '아직 검수 기록이 없습니다',
    // 남은 시간은 **평균에서 어림잡은 것**이다. 약속이 아니라 가늠이라 '예상'이라 쓴다.
    avg && remain ? `남은 ${remain}곡 예상 <b>${roughly(remain * avg)}</b>` : '',
    stats.over_20min
      ? `<span style="color:var(--warn)">20분 넘긴 곡 <b>${stats.over_20min}</b></span>`
      : '목표 곡당 20분 (지시서 9장)',
  ].filter(Boolean).join('<br>');

  $('#hero').innerHTML = `
    <div>
      <div class="eyebrow">확인 완료</div>
      <div class="hero__num">${stats.verified}<small> / ${stats.total}곡</small></div>
      <div class="hero__say">${
        remain ? `${done}% 까지 왔습니다 · 남은 <b>${remain}</b>곡` : '전부 확인했습니다'
      }</div>
    </div>
    <div class="hero__aside">${aside}</div>
    <div class="hero__rail"><i></i></div>`;
  // 한 박자 뒤에 채워야 막대가 **자라는 것**이 보인다. 바로 주면 그냥 그려진다.
  requestAnimationFrame(() => { $('#hero .hero__rail i').style.width = `${done}%`; });

  $('#stats').innerHTML = [
    ['확인 대기', stats.analyzed], ['분석 전', stats.new],
    ['확인 필요 칸', stats.low_confidence_cells], ['반주 파일', stats.midi_files],
    ['반주 MIDI', `${stats.midi_kb} KB`],
  ].map(([k, v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join('');

  if (!songs.songs.length) {
    $('#list').innerHTML =
      '<div class="empty">아직 곡이 없습니다. <code>python3 catalog_cli.py import</code> 로 악보를 넣으세요.</div>';
    return;
  }

  const rows = songs.songs.map((s) => {
    const href = `verify.html?id=${encodeURIComponent(s.id)}`;
    return `
    <tr>
      <td>
        <div class="cell__song">
          <span class="row__key">${esc(keyBadge(s))}</span>
          <span>
            <a href="${href}">${esc(s.title)}</a>
            <div class="row__sub">${esc(s.book || s.composer || '')}</div>
          </span>
        </div>
      </td>
      <td><span class="pill ${s.status}">${STATUS[s.status]}</span></td>
      <td class="num">${s.level}</td>
      <td>${esc(s.key_label || s.key)} · ${esc(s.time)}</td>
      <td class="num">${s.measures}</td>
      <td class="num">${s.low ? `<span class="row__low">${s.low}</span>` : '0'}</td>
      <td class="num">${mmss(s.verify_seconds)}</td>
      <td><a href="${href}" class="row__go">확인 화면 →</a></td>
    </tr>`;
  }).join('');

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
