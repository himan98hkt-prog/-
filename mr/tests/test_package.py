# -*- coding: utf-8 -*-
"""배포 꾸러미 — 원장님 PC 에는 파이썬이 없다.

플레이어가 런타임에 부르는 건 곡 목록과 반주 MIDI 둘뿐이고 둘 다 그냥 파일이므로,
앱이 부르는 **그 경로 그대로** 깔아 두면 정적 호스트에서 돈다 (지시서 8.4).
"""
import json
import os

import pytest

from conftest import score
from piano_mr import store

PLAYER_FILES = ('index.html', 'player.css', 'sw.js', 'manifest.webmanifest',
                'js/app.js', 'js/engine.js', 'js/midi.js', 'js/synth.js')


@pytest.fixture
def st(tmp_path):
    s = store.CatalogStore(str(tmp_path / 'catalog'))
    # `score_license='own'` 은 장식이 아니다. 꾸러미는 **파는 물건**이라 입력본
    # 출처가 확인 안 된 악보를 빼고 만든다 (piano_mr/provenance.py). 이 곡들은
    # 우리가 만든 fixture 악보이므로 'own' 이 사실이다.
    s.import_score(score('p05_waltz_c'), '작은 왈츠 (C장조)', song_id='waltz',
                   composer='자사 오리지널', book='오리지널 연습곡', level=2,
                   public_domain=True, default_style='fairytale', default_bpm=108,
                   score_source='자사 제작', score_license='own')
    s.import_score(score('p01_block_c'), '첫 화음 연습', song_id='block',
                   composer='자사 오리지널', book='오리지널 연습곡',
                   public_domain=True, score_source='자사 제작', score_license='own')
    return s


def bundle_of(out):
    with open(os.path.join(out, 'api', 'player', 'bundle'), encoding='utf-8') as f:
        return json.load(f)


# --- 무엇이 들어가나 -------------------------------------------------------------

def test_the_package_has_the_player_and_the_data(st, tmp_path):
    out = str(tmp_path / 'pkg')
    info = st.export_static(out)
    for name in PLAYER_FILES:
        assert os.path.exists(os.path.join(out, name)), name
    assert info['songs'] == 2
    b = bundle_of(out)
    assert b['static'] is True
    assert {s['id'] for s in b['songs']} == {'waltz', 'block'}


def test_the_midi_sits_at_the_path_the_app_asks_for(st, tmp_path):
    """앱 코드를 고치지 않고 정적 호스트에서 돌게 하는 핵심."""
    out = str(tmp_path / 'pkg')
    st.export_static(out)
    for song in bundle_of(out)['songs']:
        for v in song['variants']:
            path = os.path.join(out, *v['url'].split('/'))
            assert os.path.exists(path), v['url']
            with open(path, 'rb') as f:
                assert f.read(4) == b'MThd'


def test_urls_are_relative_so_a_subfolder_works(st, tmp_path):
    """원장님은 도메인 루트에도, `/반주/` 같은 하위 폴더에도 올린다."""
    out = str(tmp_path / 'pkg')
    st.export_static(out)
    for song in bundle_of(out)['songs']:
        for v in song['variants']:
            assert not v['url'].startswith('/'), v['url']
    with open(os.path.join(out, 'index.html'), encoding='utf-8') as f:
        assert 'data-api="./"' in f.read()


def test_the_served_index_keeps_the_absolute_root(st, tmp_path):
    """서버로 띄울 때는 `/` 여야 한다 — 확인 화면과 API 가 다른 경로에 있다."""
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'server', 'static', 'player', 'index.html')
    with open(src, encoding='utf-8') as f:
        assert 'data-api="/"' in f.read()


# --- 무엇이 안 들어가나 (지시서 7장) ----------------------------------------------

def test_the_package_carries_no_scores_or_cache(st, tmp_path):
    """악보 원본은 원장님께 필요 없고, 재배포하는 모양이 되어서도 안 된다."""
    out = str(tmp_path / 'pkg')
    st.export_static(out)
    names = [n for _, _, fs in os.walk(out) for n in fs]
    assert not any(n.endswith(('.musicxml', '.xml', '.mxl')) for n in names)
    assert not any(n.endswith(('.mp3', '.wav')) for n in names)
    assert not os.path.exists(os.path.join(out, 'scores'))
    assert not os.path.exists(os.path.join(out, 'cache'))


def test_the_package_is_small_enough_to_mail(st, tmp_path):
    """26곡 실측 128 KB. 여기서는 2곡이라 더 작다."""
    out = str(tmp_path / 'pkg')
    info = st.export_static(out)
    assert info['total_bytes'] < 200 * 1024


# --- 편성 -------------------------------------------------------------------

def test_only_the_default_arrangement_by_default(st, tmp_path):
    out = str(tmp_path / 'pkg')
    st.export_static(out)
    waltz = next(s for s in bundle_of(out)['songs'] if s['id'] == 'waltz')
    assert waltz['variants'] == [
        {'style': 'fairytale', 'level': 'normal',
         'url': 'api/player/midi/waltz'}]


def test_extra_arrangements_get_their_own_files(st, tmp_path):
    """정적 호스트는 쿼리스트링을 무시한다 — 편성마다 파일이 따로여야 한다."""
    out = str(tmp_path / 'pkg')
    st.export_static(out, styles=['march'], levels=['rich'])
    waltz = next(s for s in bundle_of(out)['songs'] if s['id'] == 'waltz')
    urls = {(v['style'], v['level']): v['url'] for v in waltz['variants']}
    assert urls[('fairytale', 'normal')] == 'api/player/midi/waltz'
    assert urls[('march', 'rich')] == 'api/player/midi/waltz__march_rich'
    assert len(set(urls.values())) == 2          # 같은 파일을 가리키면 안 된다
    a = open(os.path.join(out, 'api/player/midi/waltz'), 'rb').read()
    b = open(os.path.join(out, 'api/player/midi/waltz__march_rich'), 'rb').read()
    assert a != b


def test_the_default_is_always_included_even_if_not_requested(st, tmp_path):
    out = str(tmp_path / 'pkg')
    st.export_static(out, styles=['march'])
    for song in bundle_of(out)['songs']:
        assert song['variants'][0]['url'].endswith(song['id'])


# --- 곁가지 ------------------------------------------------------------------

def test_verified_only_filters(st, tmp_path):
    out = str(tmp_path / 'pkg')
    st.save_harmony('waltz', [], verified=True)
    st.export_static(out, only_verified=True)
    assert [s['id'] for s in bundle_of(out)['songs']] == ['waltz']


def test_programs_travel_with_the_package(st, tmp_path):
    """발표회 큐가 없으면 현장에서 못 쓴다."""
    from piano_mr import catalog as cat
    st.catalog.add_program(cat.Program(
        id='winter', event='2026 겨울 발표회',
        queue=[cat.QueueItem(order=1, student='김지우', song_id='waltz')]))
    st.save()
    out = str(tmp_path / 'pkg')
    st.export_static(out)
    programs = bundle_of(out)['programs']
    assert len(programs) == 1 and programs[0]['items'][0]['student'] == '김지우'


def test_a_readme_for_the_director_not_for_a_developer(st, tmp_path):
    out = str(tmp_path / 'pkg')
    st.export_static(out, academy='행복피아노')
    with open(os.path.join(out, '읽어보세요.txt'), encoding='utf-8') as f:
        text = f.read()
    assert '행복피아노' in text
    assert 'https' in text                    # 오프라인이 https 에서만 켜진다
    assert '홈 화면에 추가' in text
    # 원장님이 읽을 글이다 — 개발 용어가 나오면 안 된다
    for jargon in ('npm', 'pip', 'JSON', 'API', 'localhost', 'git'):
        assert jargon not in text, jargon


def test_rebuilding_replaces_the_folder(st, tmp_path):
    out = str(tmp_path / 'pkg')
    st.export_static(out)
    stray = os.path.join(out, '지난번찌꺼기.txt')
    with open(stray, 'w', encoding='utf-8') as f:
        f.write('x')
    st.export_static(out)
    assert not os.path.exists(stray)
