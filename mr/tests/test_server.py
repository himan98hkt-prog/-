# -*- coding: utf-8 -*-
"""화성 확인 화면 서버 (지시서 10장)."""
import json
import shutil

import pytest

pytest.importorskip('fastapi', reason='fastapi 가 없습니다 (pip install -r requirements.txt)')
pytest.importorskip('httpx2', reason='TestClient 에 httpx2 가 필요합니다')

from fastapi.testclient import TestClient      # noqa: E402

from conftest import score                     # noqa: E402
from piano_mr import store                     # noqa: E402
from server.app import create_app              # noqa: E402

needs_audio = pytest.mark.skipif(
    shutil.which('fluidsynth') is None or shutil.which('ffmpeg') is None,
    reason='fluidsynth/ffmpeg 가 없습니다')


@pytest.fixture
def client(tmp_path):
    root = str(tmp_path / 'catalog')
    st = store.CatalogStore(root)
    st.import_score(score('p05_waltz_c'), '작은 왈츠 (C장조)', song_id='waltz',
                    composer='자사 오리지널', book='오리지널 연습곡', level=2,
                    public_domain=True, default_style='fairytale', default_bpm=108)
    app = create_app(root)
    c = TestClient(app)
    c.store = app.state.store
    return c


def test_stats(client):
    d = client.get('/api/stats').json()
    assert d['total'] == 1 and d['analyzed'] == 1 and d['verified'] == 0


def test_song_list(client):
    rows = client.get('/api/songs').json()['songs']
    assert [r['id'] for r in rows] == ['waltz']
    assert rows[0]['status'] == 'analyzed'


def test_song_view_is_chords_not_notes(client):
    d = client.get('/api/songs/waltz').json()
    assert len(d['bars']) == 8
    assert d['key'] == 'C major'
    assert 'C' in d['choices']['in_key']
    blob = json.dumps(d)
    for forbidden in ('pitch', 'midi', 'octave'):
        assert forbidden not in blob


def test_unknown_song_is_404(client):
    assert client.get('/api/songs/없는곡').status_code == 404
    assert client.put('/api/songs/없는곡/harmony', json={'cells': []}).status_code == 404


def test_save_correction(client):
    r = client.put('/api/songs/waltz/harmony',
                   json={'cells': [{'bar': 1, 'i': 0, 'label': 'Am'}], 'add_seconds': 60})
    assert r.status_code == 200
    d = r.json()
    assert d['bars'][0]['cells'][0]['label'] == 'Am'
    assert d['bars'][0]['cells'][0]['changed'] is True
    assert d['verify_seconds'] == 60


def test_save_rejects_nonsense_chord(client):
    r = client.put('/api/songs/waltz/harmony',
                   json={'cells': [{'bar': 1, 'i': 0, 'label': '아무말'}]})
    assert r.status_code == 400
    assert '화음 이름' in r.json()['detail']


def test_save_needs_a_target(client):
    r = client.put('/api/songs/waltz/harmony', json={'cells': [{'i': 0, 'label': 'C'}]})
    assert r.status_code == 400


def test_mark_verified(client):
    d = client.put('/api/songs/waltz/harmony',
                   json={'cells': [], 'verified': True}).json()
    assert d['verified'] is True and d['status'] == 'verified'


def test_bad_settings_are_rejected(client):
    assert client.put('/api/songs/waltz/harmony',
                      json={'cells': [], 'style': '없는스타일'}).status_code == 400
    assert client.put('/api/songs/waltz/harmony',
                      json={'cells': [], 'bpm': 9999}).status_code == 400


def test_reanalyze_drops_human_edits(client):
    client.put('/api/songs/waltz/harmony',
               json={'cells': [{'bar': 1, 'i': 0, 'label': 'Am'}], 'verified': True})
    d = client.post('/api/songs/waltz/reanalyze').json()
    assert d['verified'] is False
    assert d['bars'][0]['cells'][0]['label'] == 'C'


def test_styles(client):
    d = client.get('/api/styles').json()
    assert len(d['styles']) == 7
    assert {x['key'] for x in d['levels']} == {'simple', 'normal', 'rich'}


def test_audio_path_traversal_is_blocked(client):
    for name in ('../catalog.json', '..%2Fcatalog.json', 'x.txt'):
        assert client.get(f'/api/audio/{name}').status_code in (400, 404)


def test_missing_audio_is_404(client):
    assert client.get('/api/audio/nope.mp3').status_code == 404


@needs_audio
def test_audio_is_built_then_cached(client):
    first = client.get('/api/songs/waltz/audio').json()
    assert first['cached'] is False and first['bpm'] == 108
    assert first['sec_per_ql'] == pytest.approx(60 / 108)
    again = client.get('/api/songs/waltz/audio').json()
    assert again['cached'] is True and again['url'] == first['url']
    r = client.get(first['url'])
    assert r.status_code == 200 and r.headers['content-type'] == 'audio/mpeg'
    assert len(r.content) > 10_000


@needs_audio
def test_changing_a_chord_changes_the_audio(client):
    """지시서 10장: 바꾸면 즉시 반주 재생성."""
    before = client.get('/api/songs/waltz/audio').json()['url']
    client.put('/api/songs/waltz/harmony',
               json={'cells': [{'bar': 1, 'i': 0, 'label': 'Am'}]})
    after = client.get('/api/songs/waltz/audio').json()
    assert after['url'] != before and after['cached'] is False


def test_styles_include_mixes(client):
    d = client.get('/api/styles').json()
    assert {x['key'] for x in d['mixes']} == {'mr', 'full', 'piano'}


@needs_audio
def test_verify_screen_hears_the_melody_by_default(client):
    """화음이 곡에 맞는지 판단하려면 선율이 같이 들려야 한다."""
    assert client.get('/api/songs/waltz/audio').json()['mix'] == 'full'


@needs_audio
def test_mix_is_selectable_and_cached_separately(client):
    full = client.get('/api/songs/waltz/audio?mix=full').json()
    mr = client.get('/api/songs/waltz/audio?mix=mr').json()
    assert full['url'] != mr['url']
    assert mr['mix'] == 'mr'


@needs_audio
def test_audio_reports_count_in_lead(client):
    d = client.get('/api/songs/waltz/audio').json()
    assert d['count_in'] == 0 and d['lead_seconds'] == 0
    client.put('/api/songs/waltz/harmony', json={'cells': []})
    client.store.catalog.get('waltz').count_in = 1
    client.store.save()
    d = client.get('/api/songs/waltz/audio').json()
    assert d['count_in'] == 1
    assert d['lead_seconds'] == pytest.approx(3 * 60 / 108, abs=0.01)


def test_midi_endpoint(client):
    d = client.post('/api/songs/waltz/midi').json()
    assert d['path'].endswith('.mid') and d['bytes'] < 10_000


# --- 발표회 운영 화면 (지시서 모듈 ⑤-3) ---------------------------------------

def program_client(tmp_path):
    from piano_mr import catalog as cat
    root = str(tmp_path / 'catalog')
    st = store.CatalogStore(root)
    st.import_score(score('p05_waltz_c'), '작은 왈츠 (C장조)', song_id='waltz',
                    composer='자사 오리지널', book='오리지널 연습곡', level=2,
                    public_domain=True, default_style='fairytale', default_bpm=108)
    st.import_score(score('p01_block_c'), '첫 화음 연습', song_id='block',
                    composer='자사 오리지널', book='오리지널 연습곡',
                    public_domain=True)
    st.catalog.add_program(cat.Program(
        id='winter', event='2026 겨울 발표회', date='2026-12-20', venue='아트홀',
        queue=[cat.QueueItem(order=2, student='박서준', song_id='block', bpm=76),
               cat.QueueItem(order=1, student='김지우', song_id='waltz', bpm=84,
                             style='fairytale', level='normal', note='리허설 완료')]))
    st.save()
    return TestClient(create_app(root))


def test_program_list(tmp_path):
    c = program_client(tmp_path)
    d = c.get('/api/programs').json()
    assert len(d['programs']) == 1
    assert d['programs'][0]['event'] == '2026 겨울 발표회'


def test_program_is_ordered_and_named(tmp_path):
    """원장님 화면에 song_id 를 보여 줄 수는 없다. 곡 제목이 붙어 나와야 한다."""
    c = program_client(tmp_path)
    d = c.get('/api/programs/0').json()
    assert [i['order'] for i in d['items']] == [1, 2]
    assert d['items'][0]['student'] == '김지우'
    assert d['items'][0]['title'] == '작은 왈츠 (C장조)'
    assert d['items'][0]['style_label'] == '동화풍'
    assert d['items'][0]['level_label'] == '보통'
    assert d['venue'] == '아트홀' and d['count'] == 2


def test_program_cue_line_matches_the_spec(tmp_path):
    """`1. 김지우 — 아라베스크 (♩=84, 실내악, 보통)` (지시서 모듈 ⑤-3)"""
    c = program_client(tmp_path)
    cue = c.get('/api/programs/0').json()['items'][0]['cue']
    assert cue.startswith('1. 김지우 — 작은 왈츠 (C장조) (♩=84,')
    assert '동화풍' in cue and '보통' in cue


def test_program_flags_unready_songs(tmp_path):
    c = program_client(tmp_path)
    d = c.get('/api/programs/0').json()
    assert d['ready'] is False                 # 아직 화성 확인 전
    assert all(not i['missing'] for i in d['items'])


def test_program_marks_missing_song(tmp_path):
    from piano_mr import catalog as cat
    c = program_client(tmp_path)
    st = c.app.state.store
    st.catalog.programs[0].queue.append(
        cat.QueueItem(order=3, student='이하은', song_id='waltz'))
    st.catalog.songs.pop('block')
    st.save()
    d = TestClient(create_app(st.root)).get('/api/programs/0').json()
    missing = [i for i in d['items'] if i['missing']]
    assert len(missing) == 1 and missing[0]['student'] == '박서준'


def test_unknown_program_is_404(tmp_path):
    assert program_client(tmp_path).get('/api/programs/99').status_code == 404


def test_stage_media_is_optional(client):
    """배경 파일이 없어도 화면은 떠야 한다 (지시서 ⑤-1 오프라인)."""
    d = client.get('/api/stage').json()
    assert set(d) == {'video', 'image', 'keys', 'curtain'}
    assert all(v is None or v.startswith('img/') for v in d.values())


def test_static_screens_are_served(client):
    for path in ('/static/index.html', '/static/verify.html',
                 '/static/program.html', '/static/hall.css', '/static/program.js',
                 '/static/app.css', '/static/verify.js', '/static/index.js'):
        assert client.get(path).status_code == 200, path
    assert client.get('/', follow_redirects=False).status_code in (307, 302)


# --- 3단계 플레이어 PWA (지시서 모듈 ⑤) ---------------------------------------

def test_player_bundle_lists_songs_with_a_midi_link(client):
    d = client.get('/api/player/bundle').json()
    assert [s['id'] for s in d['songs']] == ['waltz']
    s = d['songs'][0]
    assert s['title'] == '작은 왈츠 (C장조)' and s['bpm'] == 108
    assert s['style'] == 'fairytale' and s['level_name'] == 'normal'
    assert s['midi'] == '/api/player/midi/waltz'
    assert client.get(s['midi']).status_code == 200      # 죽은 링크가 아니다


def test_player_bundle_carries_no_audio(client):
    """오프라인 캐시는 MIDI 라서 가능하다. mp3 주소가 섞이면 설계가 깨진다."""
    blob = json.dumps(client.get('/api/player/bundle').json())
    for forbidden in ('.mp3', '.wav', '/api/audio/'):
        assert forbidden not in blob


def test_player_bundle_is_small_enough_to_cache(client):
    """한 곡당 수백 바이트. 150곡이어도 수십 KB 다 (지시서 ⑤-1)."""
    raw = client.get('/api/player/bundle').content
    assert len(raw) / max(1, len(client.get('/api/player/bundle').json()['songs'])) < 2_000


def test_player_bundle_can_be_limited_to_verified(client):
    assert client.get('/api/player/bundle?verified_only=true').json()['songs'] == []
    client.put('/api/songs/waltz/harmony', json={'cells': [], 'verified': True})
    d = client.get('/api/player/bundle?verified_only=true').json()
    assert [s['id'] for s in d['songs']] == ['waltz'] and d['songs'][0]['verified'] is True


def test_player_bundle_includes_programs(tmp_path):
    """발표회 당일 와이파이가 없어도 큐가 떠야 한다."""
    c = program_client(tmp_path)
    d = c.get('/api/player/bundle').json()
    assert len(d['programs']) == 1
    assert [i['student'] for i in d['programs'][0]['items']] == ['김지우', '박서준']


def test_player_midi_is_a_midi_file(client):
    r = client.get('/api/player/midi/waltz')
    assert r.status_code == 200
    assert r.headers['content-type'] == 'audio/midi'
    assert r.content[:4] == b'MThd'
    assert len(r.content) < 10_000            # 한 곡 1 KB 안팎


def test_player_midi_has_no_original_piano(client):
    """MR — 원음은 빠지고 반주만. 피아노 채널(0)이 있으면 안 된다."""
    import io
    from mido import MidiFile
    from piano_mr import orchestration as orch
    mf = MidiFile(file=io.BytesIO(client.get('/api/player/midi/waltz').content))
    chans = {m.channel for tr in mf.tracks for m in tr
             if m.type == 'note_on' and m.velocity > 0}
    assert chans and orch.PIANO_CHANNEL not in chans
    assert chans <= set(orch.CHANNEL.values())


def test_player_midi_is_cacheable_forever(client):
    """반주 MIDI 는 내용이 바뀌면 곡을 다시 구우므로 영구 캐시해도 된다."""
    r = client.get('/api/player/midi/waltz')
    assert 'max-age=31536000' in r.headers['cache-control']


def test_player_midi_variant_differs_from_default(client):
    base = client.get('/api/player/midi/waltz').content
    rich = client.get('/api/player/midi/waltz?style=orchestra&level=rich').content
    assert rich[:4] == b'MThd' and rich != base


def test_player_midi_rejects_unknown_song_and_style(client):
    assert client.get('/api/player/midi/없는곡').status_code == 404
    assert client.get('/api/player/midi/waltz?style=없는스타일').status_code == 400


def test_player_bundle_shows_the_key_in_korean(client):
    """원장님 화면에 'E- major' 같은 music21 표기가 나가면 안 된다."""
    s = client.get('/api/player/bundle').json()['songs'][0]
    assert s['key_label'] == 'C장조'
