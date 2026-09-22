'use strict';
/* Web Audio 신디사이저 — 반주 MIDI 를 브라우저에서 소리로.
 *
 * 외부 샘플을 받지 않는다. 그래야 정말로 오프라인이다 (지시서 모듈 ⑤-1 타협 불가).
 * 서버 렌더(FluidR3 SoundFont)만큼의 음색은 아니지만, 반주는 패드·저음·분산화음이
 * 대부분이라 감산합성으로 충분히 따라간다. 카톡으로 보내는 mp3 와 영상편집용
 * 스템은 여전히 서버가 만든다 (모듈 ④).
 *
 * 설계 제1원칙(지시서 1장)을 소리에도 적용한다 — 어택을 뭉개고 릴리스를 길게 둬서
 * 박절감을 죽인다. "따라오는 반주"가 아니라 "용서하는 반주".
 */

// GM 프로그램 -> 음색 가족
const FAMILY = {
  bowed:  { waves: ['sawtooth', 'sawtooth', 'triangle'], detune: [-6, 7, 0],
            cutoff: 1900, q: 0.6, attack: 0.28, decay: 0.5, sustain: 0.82,
            release: 0.85, gain: 0.30, drift: 2.2 },
  choir:  { waves: ['triangle', 'sawtooth'], detune: [-4, 5],
            cutoff: 1400, q: 0.4, attack: 0.40, decay: 0.6, sustain: 0.85,
            release: 1.10, gain: 0.32, drift: 3.0 },
  pad:    { waves: ['sawtooth', 'triangle', 'sine'], detune: [-9, 6, 0],
            cutoff: 1250, q: 0.5, attack: 0.55, decay: 0.8, sustain: 0.88,
            release: 1.35, gain: 0.30, drift: 3.6 },
  wind:   { waves: ['triangle', 'sine'], detune: [0, 3],
            cutoff: 2600, q: 0.7, attack: 0.10, decay: 0.3, sustain: 0.80,
            release: 0.40, gain: 0.26, drift: 3.4 },
  brass:  { waves: ['sawtooth', 'square'], detune: [-4, 4],
            cutoff: 2300, q: 0.9, attack: 0.09, decay: 0.35, sustain: 0.74,
            release: 0.35, gain: 0.24, drift: 1.6 },
  pluck:  { waves: ['triangle', 'sawtooth'], detune: [0, -5],
            cutoff: 2800, q: 0.8, attack: 0.004, decay: 1.1, sustain: 0.0,
            release: 0.35, gain: 0.34, drift: 0 },
  bell:   { waves: ['sine', 'sine'], detune: [0, 1200],
            cutoff: 5200, q: 0.4, attack: 0.002, decay: 1.8, sustain: 0.0,
            release: 0.9, gain: 0.26, drift: 0 },
  keys:   { waves: ['triangle', 'square'], detune: [0, -6],
            cutoff: 2100, q: 0.7, attack: 0.006, decay: 1.4, sustain: 0.12,
            release: 0.5, gain: 0.28, drift: 0 },
  bass:   { waves: ['triangle', 'sine'], detune: [0, -3],
            cutoff: 900, q: 0.5, attack: 0.02, decay: 0.7, sustain: 0.55,
            release: 0.45, gain: 0.42, drift: 0 },
  timp:   { waves: ['sine', 'triangle'], detune: [0, -12],
            cutoff: 700, q: 0.6, attack: 0.006, decay: 1.2, sustain: 0.0,
            release: 0.6, gain: 0.50, drift: 0 },
};

// General MIDI 프로그램 번호 -> 가족
const PROGRAM_FAMILY = {
  4: 'keys', 8: 'bell', 9: 'bell', 10: 'bell', 11: 'bell',
  19: 'keys', 21: 'keys', 24: 'pluck',
  32: 'bass', 33: 'bass',
  40: 'bowed', 41: 'bowed', 42: 'bowed', 43: 'bass',
  45: 'pluck', 46: 'pluck', 47: 'timp',
  48: 'bowed', 49: 'bowed', 50: 'bowed', 51: 'bowed', 52: 'choir',
  56: 'brass', 57: 'brass', 60: 'brass',
  68: 'wind', 70: 'wind', 71: 'wind', 73: 'wind',
  89: 'pad',
};

// 역할별 기본 밸런스. pad 가 소리의 70% 라는 것을 여기서 지킨다.
const ROLE_GAIN = { pad: 1.0, bass: 0.9, color: 0.62, counter: 0.55,
                    accent: 0.6, perc: 0.5, count_in: 1.0 };

const midiToHz = (n) => 440 * 2 ** ((n - 69) / 12);

export class Synth {
  constructor(ctx, destination) {
    this.ctx = ctx;
    this.master = ctx.createGain();
    this.master.gain.value = 0.9;

    // 살짝 눌러 붙여 준다. 화음이 겹칠 때 찢어지지 않게.
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -16;
    comp.knee.value = 24;
    comp.ratio.value = 3;
    comp.attack.value = 0.01;
    comp.release.value = 0.25;

    this.master.connect(comp);
    comp.connect(destination || ctx.destination);

    this.buses = new Map();
    this.live = new Set();
    this.noise = this._noiseBuffer();
  }

  bus(role) {
    if (!this.buses.has(role)) {
      const g = this.ctx.createGain();
      g.gain.value = ROLE_GAIN[role] === undefined ? 0.7 : ROLE_GAIN[role];
      g.connect(this.master);
      this.buses.set(role, g);
    }
    return this.buses.get(role);
  }

  setRoleGain(role, value) {
    this.bus(role).gain.setTargetAtTime(value, this.ctx.currentTime, 0.02);
  }

  setMasterGain(value, seconds = 0.02) {
    this.master.gain.setTargetAtTime(value, this.ctx.currentTime, seconds);
  }

  /** 정해진 시각에 한 음을 통째로 예약한다 (어택부터 릴리스까지). */
  play(when, ev) {
    if (ev.channel === 9) return this._drum(when, ev);
    const fam = FAMILY[PROGRAM_FAMILY[ev.program] || 'bowed'];
    const ctx = this.ctx;
    const hz = midiToHz(ev.note);
    const vel = (ev.velocity || 64) / 127;
    const dur = Math.max(0.08, ev.seconds);

    const amp = ctx.createGain();
    amp.gain.value = 0;
    const filt = ctx.createBiquadFilter();
    filt.type = 'lowpass';
    filt.Q.value = fam.q;
    // 세게 친 음일수록 조금 더 열어 준다
    const cutoff = Math.min(ctx.sampleRate / 2.2, fam.cutoff * (0.75 + vel * 0.55));
    filt.frequency.setValueAtTime(cutoff, when);
    filt.connect(amp);
    amp.connect(this.bus(ev.role));

    const oscs = [];
    fam.waves.forEach((wave, i) => {
      const o = ctx.createOscillator();
      o.type = wave;
      o.frequency.value = hz;
      o.detune.value = fam.detune[i] || 0;
      // 아주 느린 흔들림. 완전히 정지한 음보다 덜 기계적이다.
      if (fam.drift) o.detune.linearRampToValueAtTime(
        (fam.detune[i] || 0) + (i % 2 ? fam.drift : -fam.drift), when + dur);
      o.connect(filt);
      o.start(when);
      oscs.push(o);
    });

    const peak = fam.gain * (0.35 + vel * 0.75);
    const a = when + fam.attack;
    const d = a + fam.decay;
    amp.gain.setValueAtTime(0, when);
    amp.gain.linearRampToValueAtTime(peak, a);
    amp.gain.exponentialRampToValueAtTime(
      Math.max(0.0001, peak * (fam.sustain || 0.001)), d);
    const off = Math.max(d, when + dur);
    if (fam.sustain > 0) {
      amp.gain.setValueAtTime(Math.max(0.0001, peak * fam.sustain), off);
    }
    amp.gain.exponentialRampToValueAtTime(0.0001, off + fam.release);

    const stop = off + fam.release + 0.05;
    oscs.forEach((o) => o.stop(stop));
    const entry = { oscs, amp };
    this.live.add(entry);
    oscs[0].onended = () => {
      this.live.delete(entry);
      try { amp.disconnect(); } catch (e) { /* 이미 끊김 */ }
    };
  }

  _drum(when, ev) {
    const ctx = this.ctx;
    const out = this.bus(ev.role === 'count_in' ? 'count_in' : 'perc');
    const amp = ctx.createGain();
    amp.connect(out);
    const vel = (ev.velocity || 64) / 127;

    if (ev.note === 36 || ev.note === 35) {          // 베이스드럼
      const o = ctx.createOscillator();
      o.type = 'sine';
      o.frequency.setValueAtTime(120, when);
      o.frequency.exponentialRampToValueAtTime(45, when + 0.12);
      amp.gain.setValueAtTime(0.9 * vel, when);
      amp.gain.exponentialRampToValueAtTime(0.0001, when + 0.3);
      o.connect(amp);
      o.start(when);
      o.stop(when + 0.35);
    } else {                                          // 하이햇·우드블록
      const src = ctx.createBufferSource();
      src.buffer = this.noise;
      const bp = ctx.createBiquadFilter();
      bp.type = 'bandpass';
      bp.frequency.value = ev.note >= 76 ? 2400 : 7200;   // 76/77 = 카운트인 우드블록
      bp.Q.value = ev.note >= 76 ? 3 : 1.2;
      const len = ev.note >= 76 ? 0.06 : 0.05;
      amp.gain.setValueAtTime(0.5 * vel, when);
      amp.gain.exponentialRampToValueAtTime(0.0001, when + len);
      src.connect(bp);
      bp.connect(amp);
      src.start(when);
      src.stop(when + len + 0.02);
    }
  }

  _noiseBuffer() {
    const n = Math.floor(this.ctx.sampleRate * 0.4);
    const buf = this.ctx.createBuffer(1, n, this.ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
    return buf;
  }

  /** 예약된 것까지 즉시 끊는다 (정지·곡 이동). */
  allOff() {
    const now = this.ctx.currentTime;
    for (const { oscs, amp } of this.live) {
      try {
        amp.gain.cancelScheduledValues(now);
        amp.gain.setTargetAtTime(0, now, 0.015);
        oscs.forEach((o) => o.stop(now + 0.1));
      } catch (e) { /* 이미 끝난 음 */ }
    }
    this.live.clear();
  }
}

export { ROLE_GAIN, PROGRAM_FAMILY };
