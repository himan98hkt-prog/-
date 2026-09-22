'use strict';
/* 로컬 저장 — 아이별 설정 (지시서 모듈 ⑤-9) 과 곡별 볼륨 프리셋 (⑤-8).
 *
 * 서버에 로그인하지 않는다. 집 연습 링크가 "설치·로그인 없이 재생"이어야 하므로
 * (⑤-10) 설정은 이 기기에만 남는다.
 */
const KEY = 'mr-player-v1';

function load() {
  try { return JSON.parse(localStorage.getItem(KEY)) || {}; }
  catch (e) { return {}; }
}
function save(d) {
  try { localStorage.setItem(KEY, JSON.stringify(d)); } catch (e) { /* 사생활 모드 */ }
}

export const store = {
  all() { return load(); },

  /** 학생 : 곡 : 템포 : 스타일 : 레벨 : 조옮김 : 볼륨 (⑤-9) */
  settingsFor(student, songId, fallback) {
    const d = load();
    const k = `${student || '_'}::${songId}`;
    return Object.assign({}, fallback, (d.settings || {})[k] || {});
  },
  saveSettings(student, songId, settings) {
    const d = load();
    d.settings = d.settings || {};
    d.settings[`${student || '_'}::${songId}`] = settings;
    save(d);
  },

  students() {
    const d = load();
    const names = new Set(Object.keys(d.settings || {})
      .map((k) => k.split('::')[0]).filter((x) => x && x !== '_'));
    return [...names].sort();
  },

  get lastStudent() { return load().lastStudent || ''; },
  set lastStudent(v) { const d = load(); d.lastStudent = v; save(d); },

  get countInBars() { const v = load().countInBars; return v === undefined ? 1 : v; },
  set countInBars(v) { const d = load(); d.countInBars = v; save(d); },

  get offlineReady() { return !!load().offlineReady; },
  set offlineReady(v) { const d = load(); d.offlineReady = !!v; save(d); },

  /** 카운트인을 들을 장치 (⑤-4). `{id, label}` — 기기마다 따로 기억한다. */
  get cueOutput() { return load().cueOutput || { id: '', label: '' }; },
  set cueOutput(v) { const d = load(); d.cueOutput = v || { id: '', label: '' }; save(d); },

  /* ---------- 연습 기록 ----------
   *
   * **이 기기 안에만 쌓인다.** 「연습 기록 보내기」를 누르기 전에는 아무 데도 안 나간다.
   * 집 연습 링크는 로그인이 없어서(⑤-10) 학부모 기기에 계정이 없고, 그래서 기록을
   * 몰래 올릴 방법도 없다 — 보낼지 말지는 누르는 사람이 정한다.
   */

  /** 이 기기를 가리키는 무작위 문자열. 사람을 가리키지 않는다. */
  get deviceId() {
    const d = load();
    if (d.deviceId) return d.deviceId;
    const id = 'd' + Math.random().toString(36).slice(2, 10);
    d.deviceId = id;
    save(d);
    return id;
  },

  practiceRows() { return Object.values(load().practice || {}); },

  /**
   * 그 날 그 곡의 연습을 더한다. 같은 날 같은 곡은 **한 줄에 누적**된다 —
   * 줄이 늘어나면 보내는 파일만 커지고 뜻은 같다.
   */
  addPractice(row, addSeconds = 0, addCount = 0) {
    const d = load();
    d.practice = d.practice || {};
    const key = `${row.student_id || row.student || '_'}::${row.song_id}::${row.date}`;
    const cur = d.practice[key] || {
      student: row.student || '', student_id: row.student_id || '',
      song_id: row.song_id, title: row.title || '', date: row.date,
      count: 0, seconds: 0,
    };
    cur.seconds = Math.min(86400, cur.seconds + Math.max(0, Math.round(addSeconds)));
    cur.count = Math.min(999, cur.count + Math.max(0, addCount));
    if (row.bpm) cur.bpm = row.bpm;
    if (row.student_id) cur.student_id = row.student_id;   // 나중에 id 를 알게 되면 붙인다
    if (row.title) cur.title = row.title;
    d.practice[key] = cur;
    prune(d);
    save(d);
    return cur;
  },

  /** 보낸 뒤 지우기. 보내기 전에는 절대 지우지 않는다 — 못 보내면 다시 보내야 한다. */
  clearPractice() { const d = load(); d.practice = {}; save(d); },
};

/* 오래된 기록은 스스로 지운다. 학부모 기기에 아이 연습 기록이 몇 년씩 남을 이유가 없다. */
const KEEP_DAYS = 180;
function prune(d) {
  const limit = new Date(Date.now() - KEEP_DAYS * 86400_000).toISOString().slice(0, 10);
  for (const [k, v] of Object.entries(d.practice || {})) {
    if (v.date < limit) delete d.practice[k];
  }
}
