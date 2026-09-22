# -*- coding: utf-8 -*-
"""카탈로그 저장소 — 지시서 9장 2단계 · 6장 저장 원칙 · 7장 저작권."""
import json
import os
import shutil

import pytest

from conftest import score
from piano_mr import catalog as cat, store


@pytest.fixture
def st(tmp_path):
    return store.CatalogStore(str(tmp_path / 'catalog'))


def imported(st, fixture='p05_waltz_c', **kw):
    base = dict(song_id=fixture, composer='자사 오리지널', book='오리지널 연습곡',
                level=2, public_domain=True, default_style='fairytale', default_bpm=108)
    base.update(kw)
    return st.import_score(score(fixture), '작은 왈츠 (C장조)', **base)


# --- 들이기 ------------------------------------------------------------------

def test_import_lays_out_the_directory(st):
    song = imported(st)
    assert os.path.exists(os.path.join(st.scores_dir, song.source_xml))
    assert os.path.exists(st.json_path)
    assert song.status == 'analyzed' and song.harmony
    assert song.key == 'C major' and song.time == '3/4' and song.measures == 8


def test_import_refuses_blacklisted_music_before_copying(st, tmp_path):
    """지시서 7장 — 파일이 디스크에 남기 전에 막아야 한다."""
    with pytest.raises(cat.CopyrightError):
        st.import_score(score('p01_block_c'), '하울의 움직이는 성',
                        song_id='ghibli', book='지브리 피아노', public_domain=True)
    assert os.listdir(st.scores_dir) == []


def test_import_requires_public_domain(st):
    with pytest.raises(cat.CopyrightError, match='public_domain'):
        st.import_score(score('p01_block_c'), '무명 곡', song_id='x')
    assert os.listdir(st.scores_dir) == []


def test_import_rejects_path_traversal_id(st):
    """id 가 그대로 파일명이 되므로 scores/ 밖으로 나가면 안 된다."""
    with pytest.raises(ValueError, match='곡 id'):
        st.import_score(score('p01_block_c'), '나쁜 곡', song_id='../../etc/passwd',
                        public_domain=True)
    assert os.listdir(st.scores_dir) == []


def test_duplicate_id(st):
    imported(st)
    with pytest.raises(ValueError, match='이미 있는'):
        imported(st)


@pytest.mark.parametrize('title,expected', [
    ('Czerny 100 no.5', 'czerny_100_no_5'),
    ('체르니 100번 5번', ''),       # 한글은 ASCII 로 숫자만 남아 쓸 수 없다
    ('100', ''),
    ('', ''),
])
def test_slugify(title, expected):
    assert store.slugify(title) == expected


def test_korean_title_demands_an_explicit_id(st):
    """곡 id 는 배정·발표회 큐가 물고 가는 영구 식별자다. 지어내지 않는다."""
    with pytest.raises(ValueError, match='--id'):
        st.import_score(score('p01_block_c'), '체르니 100번 5번',
                        composer='Carl Czerny', book='체르니 100', public_domain=True)
    assert os.listdir(st.scores_dir) == []
    song = st.import_score(score('p01_block_c'), '체르니 100번 5번',
                           song_id='czerny100_05', composer='Carl Czerny',
                           book='체르니 100', public_domain=True)
    assert song.id == 'czerny100_05'


# --- 분석 --------------------------------------------------------------------

def test_analyze_will_not_clobber_human_work(st):
    imported(st)
    st.save_harmony('p05_waltz_c', [], verified=True)
    with pytest.raises(ValueError, match='이미 사람이 확인'):
        st.analyze('p05_waltz_c')
    st.reanalyze('p05_waltz_c')          # 명시적으로 하면 된다
    assert st.catalog.get('p05_waltz_c').harmony_verified is False


def test_locked_key_is_used(st):
    song = st.import_score(score('p17_two_four_pickup'), '2/4박 행진',
                           song_id='pickup', composer='자사 오리지널',
                           book='오리지널 연습곡', public_domain=True, key_name='C')
    assert song.key_locked and song.key == 'C major'


# --- 확인 화면이 읽는 모양 -----------------------------------------------------

def test_view_carries_no_notes_only_chords(st):
    """음표 단위로 교정하면 40분, 화성만 보면 3~5분 (지시서 10장)."""
    imported(st)
    v = st.view('p05_waltz_c')
    blob = json.dumps(v, ensure_ascii=False)
    for forbidden in ('pitch', 'midi', 'octave', 'notes'):
        assert forbidden not in blob
    assert len(v['bars']) == 8
    for bar in v['bars']:
        for c in bar['cells']:
            assert set(c) >= {'i', 'label', 'conf', 'low', 'alts', 'auto', 'off', 'len'}


def test_view_choices_lead_with_the_key(st):
    imported(st)
    ch = st.view('p05_waltz_c')['choices']
    assert 'C' in ch['in_key'] and 'G7' in ch['in_key']
    assert not set(ch['in_key']) & set(ch['all'])      # 겹치지 않는다


def test_low_confidence_is_flagged(st):
    st.import_score(score('p03_scale_g'), '음계 연습곡 (G장조)', song_id='p03',
                    composer='자사 오리지널', book='오리지널 연습곡', public_domain=True)
    v = st.view('p03')
    assert v['low_count'] > 0
    assert any(c['low'] for b in v['bars'] for c in b['cells'])


# --- 교정 저장 ----------------------------------------------------------------

def test_save_harmony_records_correction_and_time(st):
    imported(st)
    st.save_harmony('p05_waltz_c', [{'bar': 1, 'i': 0, 'label': 'Am'}],
                    add_seconds=90)
    v = st.view('p05_waltz_c')
    cell = v['bars'][0]['cells'][0]
    assert cell['label'] == 'Am' and cell['changed'] is True
    assert cell['auto'] == 'C'          # 엔진이 뭐라 했는지가 남는다
    assert v['verify_seconds'] == 90
    st.save_harmony('p05_waltz_c', [], add_seconds=30)
    assert st.view('p05_waltz_c')['verify_seconds'] == 120


def test_verified_flag_and_timestamp(st):
    imported(st)
    st.save_harmony('p05_waltz_c', [], verified=True)
    song = st.catalog.get('p05_waltz_c')
    assert song.harmony_verified and song.verified_at and song.status == 'verified'


def test_save_harmony_can_change_settings(st):
    imported(st)
    st.save_harmony('p05_waltz_c', [], style='march', level='rich', bpm=132)
    song = st.catalog.get('p05_waltz_c')
    assert (song.default_style, song.default_level, song.default_bpm) == ('march', 'rich', 132)
    with pytest.raises(Exception):
        st.save_harmony('p05_waltz_c', [], bpm=9999)


def test_corrections_target_one_bar_when_repeats_are_expanded(st):
    """반복 전개로 같은 마디 번호가 두 번 나와도 찍은 칸만 바뀌어야 한다."""
    st.import_score(score('p18_repeat_g'), '반복기호가 있는 소품', song_id='rep',
                    composer='자사 오리지널', book='오리지널 연습곡', public_domain=True)
    song = st.catalog.get('rep')
    dupes = [m for m in {h['m'] for h in song.harmony}
             if sum(1 for h in song.harmony if h['m'] == m) > 1]
    assert dupes, '반복이 펼쳐지지 않았습니다'
    bars = sorted({h['bar'] for h in song.harmony if h['m'] == dupes[0]})
    st.save_harmony('rep', [{'bar': bars[0], 'i': 0, 'label': 'Bdim'}])
    got = {h['bar']: h for h in st.catalog.get('rep').harmony if h['m'] == dupes[0]}
    assert got[bars[0]]['root'] == 11
    assert got[bars[1]]['root'] != 11 or got[bars[1]]['qual'] != 'd'


# --- 저장 원칙 (지시서 6장) -----------------------------------------------------

def test_catalog_keeps_midi_not_audio(st):
    imported(st)
    path = st.build_midi('p05_waltz_c')
    assert os.path.getsize(path) < 10_000
    assert st.catalog.get('p05_waltz_c').accomp_midi == os.path.relpath(path, st.root)
    blob = json.dumps(st.catalog.to_dict(), ensure_ascii=False)
    for ext in ('.mp3', '.wav', '.ogg'):
        assert ext not in blob


def test_cache_is_disposable(st):
    imported(st)
    open(os.path.join(st.cache_dir, 'x.mp3'), 'w').close()
    assert st.clear_cache() == 1
    assert st.catalog.get('p05_waltz_c').harmony        # 카탈로그는 멀쩡하다


def test_export_player_only_verified_and_no_audio(st, tmp_path):
    imported(st)
    st.import_score(score('p01_block_c'), '첫 화음 연습', song_id='p01',
                    composer='자사 오리지널', book='오리지널 연습곡', public_domain=True)
    st.save_harmony('p05_waltz_c', [], verified=True)
    st.build_midi('p05_waltz_c')
    out = str(tmp_path / 'player.json')
    st.export_player(out)
    data = json.load(open(out, encoding='utf-8'))
    assert [s['id'] for s in data['songs']] == ['p05_waltz_c']
    assert data['songs'][0]['midi'].endswith('.mid')
    assert '.mp3' not in json.dumps(data)


# --- MR · 카운트인 · 미리 만들기 ------------------------------------------------

def test_audio_defaults_to_mr(st):
    """카탈로그가 내보내는 것도 반주만이다. 피아노는 아이가 친다."""
    from piano_mr import render
    assert render.DEFAULT_MIX == 'mr'


def test_song_defaults_cover_the_whole_piece(st):
    song = imported(st)
    assert song.default_curve == 'flat'
    assert song.default_level == 'normal'


def test_bad_curve_and_count_in_are_rejected(st):
    song = imported(st)
    song.default_curve = '없는곡선'
    with pytest.raises(ValueError, match='연출 곡선'):
        song.validate()
    song.default_curve = 'flat'
    song.count_in = 99
    with pytest.raises(ValueError, match='count_in'):
        song.validate()


def test_prebuild_makes_variants(st):
    imported(st)
    made = st.prebuild('p05_waltz_c', styles=['strings', 'march'], levels=['normal'])
    assert os.path.exists(made['midi'])
    assert len(made['variants']) == 2
    for v in made['variants']:
        assert os.path.exists(v) and os.path.getsize(v) < 20_000
    assert made['audio'] is None
    names = sorted(os.path.basename(v) for v in made['variants'])
    assert names == ['p05_waltz_c__march_normal.mid',
                     'p05_waltz_c__strings_normal.mid']


def test_variants_differ_by_style(st):
    imported(st)
    made = st.prebuild('p05_waltz_c', styles=['strings', 'march'], levels=['normal'])
    a, b = [open(v, 'rb').read() for v in made['variants']]
    assert a != b


def test_stats_counts_prebuilt(st):
    imported(st)
    st.prebuild('p05_waltz_c', styles=['march'], levels=['normal'])
    s = st.stats()
    assert s['prebuilt'] == 1 and s['midi_files'] == 2 and s['midi_kb'] > 0


@pytest.mark.skipif(shutil.which('fluidsynth') is None or shutil.which('ffmpeg') is None,
                    reason='fluidsynth/ffmpeg 가 없습니다')
def test_count_in_shifts_the_whole_piece(st):
    """MR 은 원곡 피아노가 없어 시작 신호가 없다. 카운트인을 구우면 곡이 밀린다."""
    song = imported(st)
    none = st.audio('p05_waltz_c', mix='mr')
    assert none['lead_seconds'] == 0
    song.count_in = 1
    with_cue = st.audio('p05_waltz_c', mix='mr')
    # 3/4 한 마디 @ ♩=108
    assert with_cue['lead_seconds'] == pytest.approx(3 * 60 / 108, abs=0.01)
    assert with_cue['path'] != none['path']      # 캐시가 섞이지 않는다


def test_unknown_mix_is_rejected(st):
    imported(st)
    with pytest.raises(ValueError, match='mix'):
        st.audio('p05_waltz_c', mix='없는믹스')


def test_stats(st):
    imported(st)
    st.save_harmony('p05_waltz_c', [], verified=True, add_seconds=300)
    s = st.stats()
    assert s['total'] == 1 and s['verified'] == 1
    assert s['avg_verify_seconds'] == 300 and s['over_20min'] == 0
    st.save_harmony('p05_waltz_c', [], add_seconds=1000)
    assert st.stats()['over_20min'] == 1


def test_reopening_keeps_everything(st, tmp_path):
    imported(st)
    st.save_harmony('p05_waltz_c', [{'bar': 1, 'i': 0, 'label': 'Am'}],
                    verified=True, add_seconds=42)
    again = store.CatalogStore(st.root)
    song = again.catalog.get('p05_waltz_c')
    assert song.harmony_verified and song.verify_seconds == 42
    assert again.view('p05_waltz_c')['bars'][0]['cells'][0]['label'] == 'Am'
