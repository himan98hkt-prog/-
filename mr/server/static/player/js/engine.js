'use strict';
/* 트랜스포트 — 지시서 모듈 ⑤ 의 재생 기능이 전부 여기 모인다.
 *
 *   ⑤-2 페이드아웃 3초   ⑤-4 카운트인   ⑤-5 템포 슬라이더
 *   ⑤-6 조옮김           ⑤-7 구간 루프·마디 점프   ⑤-8 곡별 볼륨
 *
 * 시간 축은 **박(beat)** 이다. 템포를 바꿔도 음표 목록은 그대로 두고 박↔초 환산만
 * 갈아 끼우면 되므로, 사전 렌더 없이 실시간으로 빨라지고 느려진다 (지시서 ⑤-5).
 */
import { parseMidi, toNotes } from './midi.js';
import { Synth } from './synth.js';

const LOOKAHEAD_MS = 25;        // 스케줄러가 도는 주기
const SCHEDULE_AHEAD = 0.18;    // 이만큼 앞의 음을 미리 예약한다 (초)
export const FADE_SECONDS = 3;  // 지시서 검증 기준: 버튼 -> 3초 내 완전 무음

export class Player {
  constructor() {
    this.ctx = null;
    this.synth = null;
    this.notes = [];
    this.midi = null;

    this.bpm = 96;
    this.sourceBpm = 96;
    this.transpose = 0;
    this.volume = 0.85;
    this.countInBars = 0;
    this.beatsPerBar = 4;

    // 카운트인만 따로 내보낼 출력 장치 (⑤-4 "이어폰으로 원장님만 듣기").
    // 스피커에는 반주만 나가고, 딸깍 소리는 원장님 이어폰에서만 난다.
    this.cueCtx = null;
    this.cueSynth = null;
    this.cueSinkId = '';

    this.playing = false;
    this.fading = false;
    this._anchorTime = 0;       // ctx 시각
    this._anchorBeat = 0;       // 그때의 박 위치
    this._next = 0;             // 다음에 예약할 음표 인덱스
    this._timer = null;
    this._loop = null;          // {from, to} 박
    this._pausedAt = 0;

    this.onTick = null;
    this.onEnd = null;
  }

  /* ---------- 준비 ---------- */
  _ensureContext() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AC({ latencyHint: 'interactive' });
      this.synth = new Synth(this.ctx);
      this.synth.setMasterGain(this.volume, 0.001);
    }
    if (this.ctx.state === 'suspended') this.ctx.resume();
    return this.ctx;
  }

  /** 카운트인을 보낼 출력 장치를 고른다. `''` 면 반주와 같은 곳으로 나간다.
   *
   * 브라우저가 `AudioContext.setSinkId` 를 지원해야 한다 (크로미움 110+).
   * iOS 사파리에는 없다 — 그 경우 `false` 를 돌려주니 화면에서 안내한다.
   */
  static get canRouteCue() {
    const AC = typeof window !== 'undefined'
      && (window.AudioContext || window.webkitAudioContext);
    return !!(AC && typeof AC.prototype.setSinkId === 'function');
  }

  async setCueOutput(deviceId) {
    this.cueSinkId = deviceId || '';
    if (!this.cueSinkId) { this._dropCue(); return true; }
    if (!Player.canRouteCue) return false;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!this.cueCtx) {
      this.cueCtx = new AC({ latencyHint: 'interactive' });
      this.cueSynth = new Synth(this.cueCtx);
      this.cueSynth.setMasterGain(1, 0.001);
    }
    try {
      await this.cueCtx.setSinkId(this.cueSinkId);
      return true;
    } catch (err) {
      this._dropCue();                 // 장치가 사라졌으면 조용히 원래대로
      this.cueSinkId = '';
      return false;
    }
  }

  _dropCue() {
    if (this.cueCtx) { this.cueCtx.close(); }
    this.cueCtx = null;
    this.cueSynth = null;
  }

  load(arrayBuffer, { bpm, transpose, countInBars } = {}) {
    this.midi = parseMidi(arrayBuffer);
    this.notes = toNotes(this.midi);
    this.sourceBpm = this.midi.sourceBpm;
    this.beatsPerBar = this.midi.timeSignature.numerator
      * (4 / this.midi.timeSignature.denominator);
    this.bpm = bpm || this.sourceBpm;
    if (transpose !== undefined) this.transpose = transpose;
    if (countInBars !== undefined) this.countInBars = countInBars;
    this.stop();
    return this;
  }

  /* ---------- 위치 ---------- */
  get totalBeats() { return this.midi ? this.midi.beats : 0; }
  get totalBars() { return Math.ceil(this.totalBeats / this.beatsPerBar); }

  get positionBeat() {
    if (!this.playing) return this._pausedAt;
    return this._anchorBeat + (this.ctx.currentTime - this._anchorTime) * this.bpm / 60;
  }
  get positionSeconds() { return this.positionBeat * 60 / this.bpm; }
  get totalSeconds() { return this.totalBeats * 60 / this.bpm; }
  get bar() { return Math.floor(Math.max(0, this.positionBeat) / this.beatsPerBar) + 1; }

  /* ---------- 재생 ---------- */
  play(fromBeat) {
    if (!this.notes.length) return;
    this._ensureContext();
    this.fading = false;
    this.synth.setMasterGain(this.volume, 0.01);

    let at = fromBeat === undefined ? this._pausedAt : fromBeat;
    if (at >= this.totalBeats - 1e-6) at = 0;

    // 처음부터 시작할 때만 카운트인을 붙인다. 중간 재개에는 붙이지 않는다.
    const lead = (at <= 1e-6 && this.countInBars > 0)
      ? this.countInBars * this.beatsPerBar : 0;

    this._anchorBeat = at - lead;
    this._anchorTime = this.ctx.currentTime + 0.08;   // 첫 음이 잘리지 않게 여유
    this._seekIndex(at);
    if (lead) this._scheduleCountIn(this._anchorTime, lead);

    this.playing = true;
    this._timer = setInterval(() => this._tick(), LOOKAHEAD_MS);
    this._tick();
  }

  pause() {
    if (!this.playing) return;
    this._pausedAt = Math.max(0, this.positionBeat);
    this._halt();
  }

  stop() {
    this._pausedAt = 0;
    this._halt();
  }

  _halt() {
    this.playing = false;
    this.fading = false;
    clearInterval(this._timer);
    this._timer = null;
    if (this.synth) {
      this.synth.allOff();
      this.synth.setMasterGain(this.volume, 0.01);
    }
    if (this.cueSynth) this.cueSynth.allOff();
  }

  seek(beat) {
    const at = Math.max(0, Math.min(this.totalBeats, beat));
    if (this.playing) {
      this.synth.allOff();
      this._anchorBeat = at;
      this._anchorTime = this.ctx.currentTime + 0.05;
      this._seekIndex(at);
    } else {
      this._pausedAt = at;
    }
  }

  seekBar(bar) { this.seek((Math.max(1, bar) - 1) * this.beatsPerBar); }

  _seekIndex(beat) {
    this._next = 0;
    while (this._next < this.notes.length && this.notes[this._next].start < beat) {
      this._next++;
    }
  }

  /* ---------- 실시간 조절 ---------- */
  /** 템포. 재생 중에 바꿔도 끊기지 않는다 — 사전 렌더가 필요 없는 이유 (⑤-5). */
  setTempo(bpm) {
    const next = Math.max(30, Math.min(220, Math.round(bpm)));
    if (this.playing) {
      const here = this.positionBeat;        // 현재 박을 고정하고
      this._anchorBeat = here;               // 그 지점부터 새 템포로 환산
      this._anchorTime = this.ctx.currentTime;
    }
    this.bpm = next;
  }

  /** 조옮김. 예약된 음은 그대로 두고 다음 음부터 적용된다 (⑤-6). */
  setTranspose(semitones) {
    this.transpose = Math.max(-12, Math.min(12, Math.round(semitones)));
  }

  setVolume(v) {
    this.volume = Math.max(0, Math.min(1, v));
    if (this.synth && !this.fading) this.synth.setMasterGain(this.volume);
  }

  setRoleGain(role, v) { if (this.synth) this.synth.setRoleGain(role, v); }

  /** 구간 루프 (⑤-7). to 가 없으면 해제. */
  setLoop(fromBeat, toBeat) {
    this._loop = (toBeat === undefined || toBeat === null)
      ? null : { from: Math.max(0, fromBeat), to: toBeat };
  }
  setLoopBars(fromBar, toBar) {
    if (fromBar === null) return this.setLoop(null, null);
    this.setLoop((fromBar - 1) * this.beatsPerBar, toBar * this.beatsPerBar);
  }
  get loopBars() {
    if (!this._loop) return null;
    return { from: Math.round(this._loop.from / this.beatsPerBar) + 1,
             to: Math.round(this._loop.to / this.beatsPerBar) };
  }

  /** 아이가 멈췄을 때 — 3초 안에 반주만 사라진다 (⑤-2). */
  fadeOut(seconds = FADE_SECONDS) {
    if (!this.playing || this.fading) return Promise.resolve();
    this.fading = true;
    // setTargetAtTime 은 지수라 끝이 안 떨어진다. 선형으로 0 까지 확실히 내린다.
    const g = this.synth.master.gain;
    const now = this.ctx.currentTime;
    g.cancelScheduledValues(now);
    g.setValueAtTime(g.value, now);
    g.linearRampToValueAtTime(0, now + seconds);
    return new Promise((resolve) => setTimeout(() => {
      this.pause();
      resolve();
    }, seconds * 1000 + 60));
  }

  /* ---------- 스케줄러 ---------- */
  _tick() {
    if (!this.playing) return;
    const horizon = this.positionBeat + SCHEDULE_AHEAD * this.bpm / 60;

    if (this._loop && this.positionBeat >= this._loop.to) {
      this.seek(this._loop.from);
      return;
    }

    while (this._next < this.notes.length && this.notes[this._next].start < horizon) {
      const n = this.notes[this._next++];
      if (this._loop && (n.start < this._loop.from || n.start >= this._loop.to)) continue;
      const when = this._timeOf(n.start);
      if (when < this.ctx.currentTime - 0.05) continue;    // 이미 지나간 음
      this.synth.play(Math.max(when, this.ctx.currentTime), {
        note: n.channel === 9 ? n.note : n.note + this.transpose,
        program: n.program,
        role: n.role,
        channel: n.channel,
        velocity: n.velocity,
        seconds: n.duration * 60 / this.bpm,
      });
    }

    if (this.onTick) this.onTick(this);

    if (!this._loop && this.positionBeat >= this.totalBeats) {
      const end = this.onEnd;
      this.stop();
      if (end) end(this);
    }
  }

  _timeOf(beat) {
    return this._anchorTime + (beat - this._anchorBeat) * 60 / this.bpm;
  }

  _scheduleCountIn(startTime, leadBeats) {
    const perBeat = 60 / this.bpm;
    // 이어폰으로 뺄 때는 시계가 다른 AudioContext 를 쓴다. 두 시계 모두 실시간으로
    // 흐르므로, 지금 이 순간의 차이만큼 밀어 주면 몇 초짜리 카운트인 동안은 어긋나지
    // 않는다. (예약 시점에 한 번 재는 게 중요하다 — 미리 저장해 두면 틀어진다.)
    let synth = this.synth;
    let at = startTime;
    if (this.cueSynth && this.cueCtx && this.cueCtx.state !== 'closed') {
      if (this.cueCtx.state === 'suspended') this.cueCtx.resume();
      synth = this.cueSynth;
      at = startTime - this.ctx.currentTime + this.cueCtx.currentTime;
    }
    for (let i = 0; i < leadBeats; i++) {
      synth.play(at + i * perBeat, {
        note: i % this.beatsPerBar === 0 ? 76 : 77,
        program: 0, role: 'count_in', channel: 9,
        velocity: i % this.beatsPerBar === 0 ? 96 : 68,
        seconds: 0.12,
      });
    }
  }
}
