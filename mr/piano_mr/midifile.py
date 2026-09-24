# -*- coding: utf-8 -*-
"""MIDI 파일이 **무엇을 실제로 적어 두었는지** 원본 바이트에서 읽는다.

왜 music21 에 안 묻고 직접 읽는가. **music21 은 박자표가 없는 MIDI 에 4/4 를
지어 넣는다.** 그래서 파싱된 결과만 보면 진짜 4/4 와 지어낸 4/4 가 똑같이 보인다.

그 차이가 조용한 사고를 만든다. 3/4 왈츠를 박자표 없이 받으면

    박자 4/4 · 8마디 → 6마디,  화성 C G7 C F C G7 C C → C Bdim C Em F Am Am C…

**아무 오류 없이** 이렇게 나온다. 반주는 멀쩡하게 만들어지고, 틀린 것은 발표회
당일에 드러난다. `pdf.py` 가 쪽수를 "못 세면 추측하지 않고 거절"하는 것과 같은
이유로, 여기서도 **적혀 있는 것과 없는 것을 구분**한다.

의존성은 쓰지 않는다. 필요한 건 메타 이벤트 두 개뿐이라 표준 MIDI 파일 구조를
그대로 걸어가면 된다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

HEADER = b'MThd'
TRACK = b'MTrk'

META = 0xFF
META_TIME_SIG = 0x58
META_KEY_SIG = 0x59
META_TEMPO = 0x51

SYSEX = (0xF0, 0xF7)

# 채널 메시지별 데이터 바이트 수 (상위 니블 기준)
CHANNEL_DATA = {0x8: 2, 0x9: 2, 0xA: 2, 0xB: 2, 0xC: 1, 0xD: 1, 0xE: 2}


class MidiError(ValueError):
    """MIDI 파일로 읽을 수 없다."""


@dataclass
class MidiMeta:
    format: int = 0
    tracks: int = 0
    division: int = 0
    # **적혀 있는 것만** 담는다. 비어 있으면 파일에 없었다는 뜻이다.
    time_signatures: List[Tuple[int, int]] = field(default_factory=list)
    key_signatures: List[Tuple[int, int]] = field(default_factory=list)
    tempos: List[int] = field(default_factory=list)
    note_events: int = 0

    @property
    def declares_meter(self) -> bool:
        return bool(self.time_signatures)

    @property
    def meter(self) -> Optional[str]:
        """파일에 적힌 첫 박자표 ('3/4'). 없으면 None — **4/4 로 때우지 않는다.**"""
        if not self.time_signatures:
            return None
        n, d = self.time_signatures[0]
        return f'{n}/{d}'

    @property
    def meter_changes(self) -> bool:
        return len(set(self.time_signatures)) > 1


def _varint(buf: bytes, i: int) -> Tuple[int, int]:
    """가변길이 수를 읽는다 -> (값, 다음 위치)."""
    val = 0
    for _ in range(4):
        if i >= len(buf):
            raise MidiError('가변길이 수를 읽다 파일이 끝났습니다.')
        b = buf[i]
        i += 1
        val = (val << 7) | (b & 0x7F)
        if not b & 0x80:
            return val, i
    raise MidiError('가변길이 수가 4바이트를 넘습니다.')


def _u32(buf: bytes, i: int) -> int:
    return int.from_bytes(buf[i:i + 4], 'big')


def _u16(buf: bytes, i: int) -> int:
    return int.from_bytes(buf[i:i + 2], 'big')


def _track(buf: bytes, start: int, end: int, out: MidiMeta) -> None:
    """트랙 하나를 걸어가며 메타 이벤트를 줍는다.

    단순히 바이트열 `FF 58` 을 찾으면 안 된다 — 가사나 시스템 익스클루시브
    데이터 안에 같은 바이트가 들어 있을 수 있다. 델타타임과 러닝 스테이터스를
    제대로 따라가야 **적힌 것만** 걸린다.
    """
    i = start
    running = 0
    while i < end:
        _, i = _varint(buf, i)          # 델타타임
        if i >= end:
            break
        status = buf[i]
        if status < 0x80:
            # 러닝 스테이터스 — 상태 바이트가 생략됐다
            if not running:
                raise MidiError('상태 바이트 없이 시작하는 이벤트가 있습니다.')
            status = running
        else:
            i += 1
            if status < 0xF0:
                running = status

        if status == META:
            if i >= end:
                raise MidiError('메타 이벤트가 잘렸습니다.')
            kind = buf[i]
            i += 1
            length, i = _varint(buf, i)
            data = buf[i:i + length]
            i += length
            if kind == META_TIME_SIG and len(data) >= 2:
                # nn = 분자, dd = 분모의 밑 2 로그
                out.time_signatures.append((data[0], 1 << data[1]))
            elif kind == META_KEY_SIG and len(data) >= 2:
                sf = data[0] - 256 if data[0] > 127 else data[0]
                out.key_signatures.append((sf, data[1]))
            elif kind == META_TEMPO and len(data) >= 3:
                out.tempos.append(int.from_bytes(data[:3], 'big'))
        elif status in SYSEX:
            length, i = _varint(buf, i)
            i += length
        else:
            n = CHANNEL_DATA.get(status >> 4)
            if n is None:
                raise MidiError(f'모르는 이벤트입니다: 0x{status:02X}')
            if (status >> 4) == 0x9 and i + 1 < end and buf[i + 1] > 0:
                out.note_events += 1     # 벨로시티 0 은 사실상 노트오프다
            i += n


def read(raw: bytes) -> MidiMeta:
    """표준 MIDI 파일의 메타 정보를 읽는다. 못 읽으면 추측하지 않고 던진다."""
    if len(raw) < 14 or raw[:4] != HEADER:
        raise MidiError('MIDI 파일이 아닙니다 (MThd 로 시작하지 않습니다).')
    hlen = _u32(raw, 4)
    if hlen < 6:
        raise MidiError('MIDI 헤더가 너무 짧습니다.')
    out = MidiMeta(format=_u16(raw, 8), tracks=_u16(raw, 10),
                   division=_u16(raw, 12))
    i = 8 + hlen
    seen = 0
    while i + 8 <= len(raw):
        if raw[i:i + 4] != TRACK:
            # 모르는 청크는 건너뛴다 (규격이 허용한다)
            i += 8 + _u32(raw, i + 4)
            continue
        length = _u32(raw, i + 4)
        start = i + 8
        if start + length > len(raw):
            # 트랙이 자기 길이만큼 들어 있지 않다. 여기서 멈추지 않고 있는
            # 데까지 읽으면 **박자표가 잘려 나간 파일을 "박자표 없음"으로**
            # 보고하게 된다 — 없는 것과 잘린 것은 다른 사고다.
            raise MidiError(
                f'트랙이 잘렸습니다 (적힌 길이 {length}바이트, 남은 것 '
                f'{len(raw) - start}바이트). 파일이 온전한지 확인하세요.')
        _track(raw, start, start + length, out)
        seen += 1
        i = start + length
    if not seen:
        raise MidiError('트랙(MTrk)이 하나도 없습니다.')
    return out


def inspect(path: str) -> MidiMeta:
    with open(path, 'rb') as f:
        return read(f.read())


def is_midi(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in ('.mid', '.midi')
