'use strict';
/* 표준 MIDI 파일(SMF) 파서 — 반주 MIDI 를 브라우저에서 직접 읽는다.
 *
 * 지시서 8.4: "MIDI 를 클라이언트에 내려주고 브라우저에서 재생하면 서버 렌더링조차
 * 불필요하다." 모듈 ⑤-5·6 의 템포 슬라이더와 조옮김이 "사전 렌더 불필요"인 것도
 * 여기서 나온다. 반주 MIDI 는 1 KB 안팎이라 카탈로그 전체를 오프라인에 담을 수 있다.
 *
 * 필요한 것만 읽는다: 음표, 악기(program_change), 템포, 박자, 트랙 이름.
 */

export function parseMidi(buffer) {
  const v = new DataView(buffer instanceof ArrayBuffer ? buffer : buffer.buffer);
  let p = 0;

  const str = (n) => {
    let s = '';
    for (let i = 0; i < n; i++) s += String.fromCharCode(v.getUint8(p++));
    return s;
  };
  const u32 = () => { const x = v.getUint32(p); p += 4; return x; };
  const u16 = () => { const x = v.getUint16(p); p += 2; return x; };

  if (str(4) !== 'MThd') throw new Error('MIDI 파일이 아닙니다.');
  const headerLen = u32();
  const format = u16();
  const trackCount = u16();
  const division = u16();
  p += headerLen - 6;                       // 헤더가 6바이트보다 길면 남는 건 무시

  if (division & 0x8000) throw new Error('SMPTE 타임코드 MIDI 는 지원하지 않습니다.');
  const ticksPerBeat = division;

  const tracks = [];
  const tempos = [];                        // {tick, usPerBeat}
  let timeSignature = { numerator: 4, denominator: 4 };

  for (let t = 0; t < trackCount; t++) {
    if (p >= v.byteLength) break;
    if (str(4) !== 'MTrk') throw new Error('트랙 헤더가 깨졌습니다.');
    // 길이를 먼저 변수에 받는다. `p + u32()` 로 쓰면 자바스크립트가 왼쪽 p 를
    // 먼저 읽어서, u32() 가 p 를 4 밀기 전의 값으로 끝 위치를 잡는다.
    const trackLen = u32();
    const end = p + trackLen;

    const track = { name: '', program: 0, channel: null, notes: [] };
    const open = new Map();                 // `${channel}:${note}` -> {tick, velocity}
    let tick = 0;
    let running = 0;

    while (p < end) {
      tick += readVarInt();
      let status = v.getUint8(p);
      if (status & 0x80) { p++; running = status; } else { status = running; }
      const type = status & 0xf0;
      const channel = status & 0x0f;

      if (status === 0xff) {                // 메타 이벤트
        const meta = v.getUint8(p++);
        const len = readVarInt();
        if (meta === 0x03) {                // 트랙 이름
          const at = p;
          track.name = str(len);
          p = at + len;
        } else if (meta === 0x51) {         // 템포
          tempos.push({ tick, usPerBeat: (v.getUint8(p) << 16) | (v.getUint8(p + 1) << 8)
                                           | v.getUint8(p + 2) });
          p += len;
        } else if (meta === 0x58) {         // 박자
          timeSignature = { numerator: v.getUint8(p),
                            denominator: 2 ** v.getUint8(p + 1) };
          p += len;
        } else {
          p += len;
        }
      } else if (status === 0xf0 || status === 0xf7) {
        p += readVarInt();                  // 시스템 배타 — 건너뛴다
      } else if (type === 0x90 || type === 0x80) {
        const note = v.getUint8(p++);
        const velocity = v.getUint8(p++);
        const key = `${channel}:${note}`;
        if (type === 0x90 && velocity > 0) {
          open.set(key, { tick, velocity });
          if (track.channel === null) track.channel = channel;
        } else {
          const on = open.get(key);
          if (on) {
            open.delete(key);
            track.notes.push({ note, channel, velocity: on.velocity,
                               startTick: on.tick, endTick: tick });
          }
        }
      } else if (type === 0xc0) {
        track.program = v.getUint8(p++);
        if (track.channel === null) track.channel = channel;
      } else if (type === 0xd0) {
        p += 1;
      } else if (type === 0xa0 || type === 0xb0 || type === 0xe0) {
        p += 2;
      } else {
        p = end;                            // 모르는 이벤트 — 이 트랙은 여기까지
      }
    }
    // 닫히지 않은 음은 트랙 끝에서 끊는다
    for (const [key, on] of open) {
      const note = Number(key.split(':')[1]);
      track.notes.push({ note, channel: Number(key.split(':')[0]), velocity: on.velocity,
                         startTick: on.tick, endTick: tick });
    }
    p = end;
    if (track.notes.length) tracks.push(track);
  }

  function readVarInt() {
    let x = 0;
    for (let i = 0; i < 4; i++) {
      const b = v.getUint8(p++);
      x = (x << 7) | (b & 0x7f);
      if (!(b & 0x80)) break;
    }
    return x;
  }

  const usPerBeat = tempos.length ? tempos[0].usPerBeat : 500000;   // 기본 ♩=120
  const sourceBpm = Math.round(60000000 / usPerBeat);

  let lastTick = 0;
  for (const tr of tracks) {
    for (const n of tr.notes) lastTick = Math.max(lastTick, n.endTick);
  }

  return { format, ticksPerBeat, tracks, sourceBpm, timeSignature,
           beats: lastTick / ticksPerBeat, lastTick };
}

/** 트랙들을 시간순 음표 하나의 목록으로. 박(beat) 단위라 템포와 무관하다. */
export function toNotes(midi) {
  const out = [];
  for (const tr of midi.tracks) {
    for (const n of tr.notes) {
      out.push({
        note: n.note,
        channel: n.channel,
        program: n.program === undefined ? tr.program : n.program,
        role: tr.name || 'pad',
        velocity: n.velocity,
        start: n.startTick / midi.ticksPerBeat,          // 박
        duration: Math.max(0.02, (n.endTick - n.startTick) / midi.ticksPerBeat),
      });
    }
  }
  out.sort((a, b) => a.start - b.start);
  return out;
}
