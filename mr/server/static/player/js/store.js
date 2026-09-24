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
};
