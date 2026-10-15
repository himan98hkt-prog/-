# -*- coding: utf-8 -*-
"""데이터 모델 (지시서 6장) + 저작권 방어선 (7장)."""
import json

import pytest

from conftest import score
from piano_mr import catalog, harmony, score_loader


def a_song(**kw):
    base = dict(id='czerny100_05', title='체르니 100번 5번', composer='Carl Czerny',
                book='체르니 100', level=3, public_domain=True,
                source_xml='czerny100_05.mxl', key='C major', time='4/4',
                measures=16, default_style='march', recommended_bpm=[72, 84, 96])
    base.update(kw)
    return catalog.Song(**base)


# --- 저작권 (7장: 위반 시 사업 전체가 무너짐) --------------------------------

@pytest.mark.parametrize('title,book', [
    ('별빛 아래', '피아노 어드벤처 2급'),
    ('Kiss the Rain', '이루마 베스트'),
    ('하울의 움직이는 성', '지브리 피아노'),
    ('Let It Go', '디즈니 OST 모음'),
    ('첫사랑', '바스티앙 피아노 베이직'),
])
def test_blacklist_is_refused(title, book):
    with pytest.raises(catalog.CopyrightError):
        a_song(id='x', title=title, book=book).validate()


def test_non_public_domain_is_refused():
    with pytest.raises(catalog.CopyrightError, match='public_domain'):
        a_song(public_domain=False).validate()


def test_whitelist_passes():
    a_song().validate()
    a_song(id='burg_02', title='부르크뮐러 25곡 2번', book='부르크뮐러 25').validate()
    a_song(id='own_01', title='우리 학원 오리지널 1번', composer='자사').validate()


def test_whitelist_hint_detects_known_repertoire():
    assert catalog.looks_whitelisted('체르니 100번')
    assert catalog.looks_whitelisted('Burgmuller Op.100')
    assert not catalog.looks_whitelisted('무명 창작곡')


# --- 곡 ---------------------------------------------------------------------

@pytest.mark.parametrize('bad', [
    dict(id='대문자Id'), dict(id=''), dict(title=''), dict(level=0), dict(level=11),
    dict(default_style='없는스타일'),
])
def test_song_validation(bad):
    with pytest.raises((ValueError, catalog.CopyrightError)):
        a_song(**bad).validate()


def test_song_from_analysis():
    ls = score_loader.load(score('p01_block_c'))
    segs = harmony.analyze_segments(ls)
    s = catalog.Song.from_analysis('own_01', '오리지널 1번', ls, segs,
                                   public_domain=True, composer='자사')
    s.validate()
    assert s.key == 'C major' and s.measures == 8
    assert len(s.harmony) == len(segs)
    assert s.harmony_verified is False          # 사람이 아직 안 봤다
    assert s.harmony_labels()[0] == 'C'


# --- 배정 / 프로그램 ---------------------------------------------------------

def test_assignment_validation():
    catalog.Assignment(student_id='s_0142', song_id='czerny100_05', bpm=76,
                       style='march', level='normal').validate()
    with pytest.raises(ValueError):
        catalog.Assignment(student_id='s', song_id='x', bpm=500).validate()
    with pytest.raises(ValueError):
        catalog.Assignment(student_id='s', song_id='x', transpose=20).validate()
    with pytest.raises(ValueError):
        catalog.Assignment(student_id='', song_id='x').validate()


def test_beginner_can_turn_the_accompaniment_off():
    """박자 불안한 저학년은 반주를 끈다 (지시서 6장)."""
    a = catalog.Assignment(student_id='s', song_id='x', use_accompaniment=False)
    assert a.use_accompaniment is False


def test_program_cue_lines():
    p = catalog.Program(event='2026 겨울 발표회', date='2026-12-20', queue=[
        catalog.QueueItem(order=2, student='박서준', song_id='czerny100_05',
                          bpm=92, style='march', level='simple'),
        catalog.QueueItem(order=1, student='김지우', song_id='czerny100_05',
                          bpm=84, style='chamber', level='rich', note='리허설 완료'),
    ])
    p.validate()
    lines = p.cue_lines()
    assert lines[0].startswith('1. 김지우')
    assert '♩=84' in lines[0] and '실내악' in lines[0] and '풍성' in lines[0]


def test_program_minutes_estimate():
    p = catalog.Program(event='x', queue=[
        catalog.QueueItem(order=i, student=f's{i}', song_id='s') for i in range(1, 11)])
    assert p.minutes == 30


def test_program_id_is_validated():
    p = catalog.Program(event='x', id='대문자Id')
    with pytest.raises(ValueError, match='프로그램 id'):
        p.validate()
    catalog.Program(event='x', id='winter_2026').validate()


def test_duplicate_order_is_refused():
    p = catalog.Program(event='x', queue=[
        catalog.QueueItem(order=1, student='a', song_id='s'),
        catalog.QueueItem(order=1, student='b', song_id='s'),
    ])
    with pytest.raises(ValueError, match='순서'):
        p.validate()


# --- 저장소 ------------------------------------------------------------------

def test_roundtrip(tmp_path):
    c = catalog.Catalog(str(tmp_path))
    c.add(a_song())
    c.assign(catalog.Assignment(student_id='s_0142', song_id='czerny100_05', bpm=76,
                                style='march'))
    c.add_program(catalog.Program(event='발표회', queue=[
        catalog.QueueItem(order=1, student='김지우', song_id='czerny100_05')]))
    path = c.save()
    again = catalog.Catalog.load(path)
    assert again.songs['czerny100_05'].title == '체르니 100번 5번'
    assert again.assignments[0].bpm == 76
    assert again.programs[0].queue[0].student == '김지우'


def test_no_audio_is_stored(tmp_path):
    c = catalog.Catalog(str(tmp_path))
    c.add(a_song(accomp_midi='czerny100_05.mid'))
    blob = json.dumps(c.to_dict(), ensure_ascii=False)
    for ext in ('.mp3', '.wav', '.ogg', '.m4a'):
        assert ext not in blob
    assert '.mid' in blob


def test_assignment_needs_an_existing_song(tmp_path):
    c = catalog.Catalog(str(tmp_path))
    with pytest.raises(KeyError):
        c.assign(catalog.Assignment(student_id='s', song_id='없는곡'))


def test_apply_corrections_marks_verified(tmp_path):
    ls = score_loader.load(score('p01_block_c'))
    segs = harmony.analyze_segments(ls)
    c = catalog.Catalog(str(tmp_path))
    song = c.add(catalog.Song.from_analysis('own_01', '오리지널', ls, segs,
                                            public_domain=True, composer='자사'))
    first = song.harmony[0]
    c.apply_corrections('own_01', [{'m': first['m'], 'i': first['i'], 'label': 'G7'}])
    assert song.harmony[0]['root'] == 7 and song.harmony[0]['qual'] == '7'
    assert song.harmony_verified is True


def test_apply_corrections_rejects_garbage(tmp_path):
    ls = score_loader.load(score('p01_block_c'))
    segs = harmony.analyze_segments(ls)
    c = catalog.Catalog(str(tmp_path))
    c.add(catalog.Song.from_analysis('own_01', '오리지널', ls, segs,
                                     public_domain=True, composer='자사'))
    with pytest.raises(ValueError):
        c.apply_corrections('own_01', [{'m': 1, 'i': 0, 'label': '아무말'}])
    with pytest.raises(KeyError):
        c.apply_corrections('own_01', [{'m': 999, 'i': 0, 'label': 'C'}])


def test_unverified_can_be_blocked(tmp_path):
    c = catalog.Catalog(str(tmp_path))
    with pytest.raises(ValueError, match='화성 확인'):
        c.add(a_song(harmony_verified=False), allow_unverified=False)


# --- 조성 이름 (원장님 화면에 music21 표기를 내보내지 않는다) --------------------

def test_key_label_is_korean():
    assert catalog.key_label('C major') == 'C장조'
    assert catalog.key_label('E- major') == 'E♭장조'     # music21 의 '-' 는 플랫
    assert catalog.key_label('f# minor') == 'F♯단조'
    assert catalog.key_label('a minor') == 'A단조'


def test_key_label_passes_through_what_it_cannot_read():
    assert catalog.key_label('') == '' and catalog.key_label(None) == ''
    assert catalog.key_label('알 수 없음') == '알 수 없음'
