# -*- coding: utf-8 -*-
"""MIDI 를 악보로 받을 때 — **적혀 있는 것과 지어낸 것을 구분한다.**

여기서 잡는 고장은 조용하다. 박자표 없는 3/4 곡을 받으면 music21 이 4/4 를
지어 넣고, 마디가 접히고, 화성이 통째로 바뀌는데 **오류가 하나도 안 난다.**
반주는 멀쩡하게 만들어져서 틀린 것은 발표회 당일에 드러난다.
"""
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piano_mr import harmony, midifile, repertoire as rep  # noqa: E402
from piano_mr import score_loader as sl, store             # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(os.path.dirname(HERE), 'fixtures', 'scores')
WALTZ = os.path.join(FIXTURES, 'p05_waltz_c.musicxml')     # 3/4 · 8마디


# --------------------------------------------------------------------------
# 손으로 만드는 MIDI — 라이브러리가 끼어들지 않게
# --------------------------------------------------------------------------

def head(fmt=0, tracks=1, division=96):
    return b'MThd' + struct.pack('>IHHH', 6, fmt, tracks, division)


def track(events: bytes) -> bytes:
    body = events + b'\x00\xFF\x2F\x00'          # End of Track
    return b'MTrk' + struct.pack('>I', len(body)) + body


def note(pitch=60, delta=0, vel=64, dur=96):
    return bytes([delta, 0x90, pitch, vel, dur, 0x80, pitch, 0])


def time_sig(n=3, d_pow=2):
    return bytes([0x00, 0xFF, 0x58, 0x04, n, d_pow, 0x18, 0x08])


# --------------------------------------------------------------------------
# 무엇이 적혀 있는가
# --------------------------------------------------------------------------

def test_a_file_with_no_time_signature_says_so():
    m = midifile.read(head() + track(note(60) + note(62)))
    assert m.declares_meter is False
    assert m.meter is None, '없는 박자를 4/4 로 때우면 안 됩니다'


def test_a_declared_meter_is_read():
    m = midifile.read(head() + track(time_sig(3, 2) + note(60)))
    assert m.meter == '3/4'


@pytest.mark.parametrize('n,d_pow,want', [(4, 2, '4/4'), (6, 3, '6/8'),
                                          (2, 1, '2/2'), (12, 3, '12/8')])
def test_the_denominator_is_a_power_of_two(n, d_pow, want):
    """MIDI 는 분모를 **밑 2 로그**로 적는다. 3 이면 8분음표다."""
    assert midifile.read(head() + track(time_sig(n, d_pow))).meter == want


def test_bytes_that_merely_look_like_a_time_signature_do_not_count():
    """가사 안에 `FF 58 04` 가 들어 있어도 박자표가 아니다.

    바이트열을 그냥 찾으면 여기서 속는다. 속으면 박자표가 없는 파일을 있다고
    보고 통과시켜 버린다 — 이 검사가 막으려는 바로 그 고장이 된다.
    """
    lyric = b'\x00\xFF\x05\x04' + b'\xFF\x58\x04\x03'
    m = midifile.read(head() + track(lyric + note(60)))
    assert m.declares_meter is False


def test_a_meter_change_is_noticed():
    m = midifile.read(head() + track(time_sig(3, 2) + note(60) + time_sig(4, 2)))
    assert m.time_signatures == [(3, 4), (4, 4)]
    assert m.meter_changes is True


def test_running_status_is_followed():
    """상태 바이트를 생략한 이벤트를 못 따라가면 그 뒤가 전부 어긋난다."""
    # 0x90 한 번 쓰고 다음 음표는 상태 바이트 없이
    events = (b'\x00\x90\x3C\x40' + b'\x60\x3E\x40' + b'\x60\x40\x40'
              + time_sig(3, 2))
    m = midifile.read(head() + track(events))
    assert m.meter == '3/4', '러닝 스테이터스를 지나치다 박자표를 놓쳤습니다'
    assert m.note_events == 3


def test_tempo_and_key_signature_come_along():
    tempo = b'\x00\xFF\x51\x03\x07\xA1\x20'      # 500000 us/quarter = 120 BPM
    ksig = b'\x00\xFF\x59\x02\xFD\x00'           # 플랫 3개, 장조
    m = midifile.read(head() + track(tempo + ksig + note(60)))
    assert m.tempos == [500000]
    assert m.key_signatures == [(-3, 0)]


# --------------------------------------------------------------------------
# 못 읽는 것은 추측하지 않는다
# --------------------------------------------------------------------------

@pytest.mark.parametrize('raw,why', [
    (b'%PDF-1.4 whatever', 'PDF'),
    (b'', '빈 파일'),
    (b'MThd' + struct.pack('>IHHH', 6, 0, 1, 96), '트랙이 없다'),
])
def test_it_refuses_what_it_cannot_read(raw, why):
    with pytest.raises(midifile.MidiError):
        midifile.read(raw)


def test_a_truncated_track_does_not_pass_silently():
    good = head() + track(time_sig(3, 2) + note(60))
    with pytest.raises(midifile.MidiError):
        midifile.read(good[:len(good) - 6])


# --------------------------------------------------------------------------
# 악보로 받을 때
# --------------------------------------------------------------------------

@pytest.fixture
def midis(tmp_path):
    """같은 왈츠(3/4)를 박자표 있는 것과 없는 것 두 벌로 만든다."""
    from music21 import converter
    ok = str(tmp_path / 'ok.mid')
    converter.parse(WALTZ).write('midi', fp=ok)

    # music21 의 **쓰기** 쪽이 박자표를 넣어 버리므로 바이트에서 직접 뗀다
    raw = open(ok, 'rb').read()
    i = raw.find(b'\xFF\x58\x04')
    th = raw.rfind(b'MTrk', 0, i)
    old = int.from_bytes(raw[th + 4:th + 8], 'big')
    cut = raw[:i - 1] + raw[i + 8:]
    cut = cut[:th + 4] + struct.pack('>I', old - 9) + cut[th + 8:]
    nots = str(tmp_path / 'nots.mid')
    open(nots, 'wb').write(cut)

    assert midifile.inspect(ok).meter == '3/4'
    assert not midifile.inspect(nots).declares_meter
    return ok, nots


def chords(ls):
    return [harmony.label(s['root'], s['qual'])
            for s in harmony.analyze_segments(ls)]


def test_a_midi_that_declares_its_meter_matches_the_musicxml(midis):
    """MIDI 로 받아도 화성이 같아야 한다 — 다르면 MIDI 를 받을 이유가 없다."""
    ok, _ = midis
    assert chords(sl.load(ok)) == chords(sl.load(WALTZ))


def test_a_midi_without_a_meter_is_refused(midis):
    _, nots = midis
    with pytest.raises(ValueError, match='박자표가 적혀 있지 않습니다'):
        sl.load(nots)


def test_the_refusal_says_how_to_fix_it(midis):
    _, nots = midis
    with pytest.raises(ValueError) as e:
        sl.load(nots)
    assert '--time' in str(e.value), '어떻게 고치는지 말해 줘야 합니다'


def test_telling_it_the_meter_gets_the_right_answer(midis):
    """사람이 박자를 알려 주면 원본과 **똑같이** 나와야 한다."""
    _, nots = midis
    assert chords(sl.load(nots, time_name='3/4')) == chords(sl.load(WALTZ))


def test_guessing_wrong_really_does_wreck_it(midis):
    """왜 막는지를 보여 주는 검사.

    같은 파일을 4/4 로 읽으면 마디가 접히고 화성이 달라진다. 이게 막지 않았을
    때 **조용히** 일어나는 일이다.
    """
    _, nots = midis
    right = sl.load(nots, time_name='3/4')
    wrong = sl.load(nots, time_name='4/4')
    assert len(wrong.bars) < len(right.bars)
    assert chords(wrong) != chords(right)


def test_a_nonsense_meter_is_rejected(midis):
    _, nots = midis
    with pytest.raises(ValueError, match='박자표를 못 읽었습니다'):
        sl.load(nots, time_name='삼사분의')


# --------------------------------------------------------------------------
# 카탈로그에 들어간 뒤
# --------------------------------------------------------------------------

def test_the_declared_meter_survives_reanalysis(tmp_path, midis):
    """다시 분석할 때 또 물으면 안 된다.

    악보는 원래 확장자 그대로 보관되므로, 박자를 안 적어 두면 `reanalyze` 가
    같은 파일에서 또 거절당한다. 사람이 한 번 알려 준 것은 남아야 한다.
    """
    _, nots = midis
    st = store.CatalogStore(str(tmp_path / 'catalog'))
    song = st.import_score(nots, '왈츠', song_id='waltz', composer='자사 오리지널',
                           book='오리지널 연습곡', public_domain=True,
                           time_name='3/4', score_license='own')
    assert song.time_locked is True
    before = list(song.harmony)

    again = store.CatalogStore(str(tmp_path / 'catalog'))   # 닫았다 다시 연다
    re_song = again.reanalyze('waltz')
    assert re_song.time == '3/4'
    assert len(re_song.harmony) == len(before)


def test_a_midi_with_its_own_meter_is_not_locked(tmp_path, midis):
    """파일이 스스로 말하는 것을 사람이 확정했다고 적으면 안 된다."""
    ok, _ = midis
    st = store.CatalogStore(str(tmp_path / 'catalog'))
    song = st.import_score(ok, '왈츠', song_id='waltz', composer='자사 오리지널',
                           book='오리지널 연습곡', public_domain=True,
                           score_license='own')
    assert song.time_locked is False
    assert song.time == '3/4'


def test_the_batch_importer_looks_for_midi():
    """Mutopia 처럼 **곡마다 라이선스를 밝히는** 사이트가 MIDI 로 준다."""
    assert '.mid' in rep.SCORE_EXT
    assert '.midi' in rep.SCORE_EXT


def test_find_score_picks_up_a_midi(tmp_path):
    (tmp_path / 'czerny599_01.mid').write_bytes(head() + track(time_sig()))
    found = rep.find_score({'id': 'czerny599_01'}, str(tmp_path))
    assert found and found.endswith('.mid')
