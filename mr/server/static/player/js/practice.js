'use strict';
/* 연습을 센다 — 그리고 **실제로 들은 만큼만** 센다.
 *
 * 이 숫자는 학부모 리포트로 나간다. 눌렀다 바로 끈 것까지 한 번으로 세면 리포트가
 * 거짓말을 하게 되고, 한 번 그러면 그 뒤로 아무도 안 믿는다. 그래서 세는 규칙을
 * 좁게 잡는다.
 *
 *   · 시간은 **재생 중인 벽시계 시간**만 더한다. 템포를 늦추면 실제로 더 오래 걸리고,
 *     리포트에 쓰는 건 "몇 분 앉아 있었나"라서 벽시계가 맞다.
 *   · 한 번(횟수)은 **끝까지 쳤을 때** 센다. 끝까지 못 갔어도 한 자리에서 1분 넘게
 *     쳤으면 한 번으로 친다 — 구간 반복으로 어려운 데만 파는 것도 연습이다.
 *   · 30초도 안 되는 건 아무것도 아니다. 곡을 잘못 눌러 본 것이다.
 *
 * 기록은 이 기기에만 쌓인다. 보내는 것은 사람이 누를 때만 (`store.js` 참고).
 */
import { store } from './store.js';
import { localDate } from './practice-format.js';

/** 이 시간을 넘겨야 "한 번"으로 친다 (초). */
export const MIN_RUN_SECONDS = 60;

/** 이 시간도 안 되면 기록 자체를 안 남긴다 (초). */
export const MIN_KEEP_SECONDS = 30;

export class PracticeTracker {
  /**
   * @param {{student?: string, studentId?: string, song: object, bpm?: number}} what
   */
  constructor(what) {
    this.what = what;
    this.startedAt = 0;      // 재생이 시작된 벽시계 (0 이면 멈춘 상태)
    this.runSeconds = 0;     // 마지막으로 "한 번" 센 뒤로 친 시간
    this.pending = 0;        // 아직 저장 안 한 시간
  }

  /**
   * 누구 연습인지 알 때만 적는다.
   *
   * 이름도 id 도 모르면 그 기록은 **보낼 수가 없다** — 받는 쪽에서 누구에게 붙일지
   * 알 수 없기 때문이다. 그런데도 적어 두면 화면에는 "3일 · 12번"이 뜨는데 보내면
   * 빈 파일이 간다. 아무 말 없이 안 적는 편이 낫고, 화면이 그 이유를 말해 준다.
   */
  get tracking() {
    return !!(this.what.student || this.what.studentId);
  }

  /** 재생이 시작됐다. */
  start() {
    if (this.startedAt) return;
    this.startedAt = Date.now();
  }

  /** 재생이 멈췄다 (일시정지·페이드아웃·화면 이탈). */
  stop() {
    this._collect();
    this.startedAt = 0;
    // 끝까지 못 갔어도 한참 쳤으면 한 번으로 친다. **한 번까지만이다** —
    // 3분 쳤다고 세 번이라고 하면 그건 이미 리포트가 거짓말을 하는 것이다.
    const run = this.runSeconds >= MIN_RUN_SECONDS ? 1 : 0;
    if (run) this.runSeconds = 0;
    this._save(run);
  }

  /** 곡이 끝까지 갔다 — 이건 확실히 한 번이다. */
  finished() {
    this._collect();
    this.startedAt = 0;
    this.runSeconds = 0;
    this._save(1);
  }

  /** 지금까지 이 화면에서 친 시간 (초) — 화면에 보여 줄 때 쓴다. */
  get seconds() {
    return Math.round(this.pending + this._live());
  }

  _live() {
    return this.startedAt ? (Date.now() - this.startedAt) / 1000 : 0;
  }

  /** 재생 중이던 시간을 장부에 옮기고 시계를 다시 맞춘다. */
  _collect() {
    const live = this._live();
    if (!live) return;
    this.pending += live;
    this.runSeconds += live;
    this.startedAt = Date.now();
  }

  _save(addCount) {
    if (!this.tracking) { this.pending = 0; return; }
    const seconds = Math.round(this.pending);
    // 30초도 안 친 건 남기지 않는다. 다만 "한 번"이 잡혔으면 짧아도 남긴다
    // (아주 짧은 곡을 끝까지 친 경우다).
    if (!addCount && seconds < MIN_KEEP_SECONDS) return;
    this.pending = 0;
    const w = this.what;
    store.addPractice({
      student: w.student || '',
      student_id: w.studentId || '',
      song_id: w.song.id,
      title: w.song.title || '',
      date: localDate(),
      bpm: w.bpm || 0,
    }, seconds, addCount);
  }
}
