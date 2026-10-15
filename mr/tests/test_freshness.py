# -*- coding: utf-8 -*-
"""고친 반주가 아이 폰까지 가는가.

브라우저로 실제 고장을 두 개 잡고 만든 검사다. 둘 다 **오류가 하나도 안 나고**,
화면에는 고친 화성이 보이는데 소리만 옛것이 나는 종류였다.

    ① 미리 구워 둔 MIDI 가 화성을 안 따라갔다
       `save_harmony` 는 catalog.json 만 고치고 `midi/*.mid` 를 그대로 둔다.
       그런데 화성 확인 화면의 「듣기」는 `render_key` 에 화성이 들어가서 그
       자리에서 다시 굽는다. 그래서 **원장님은 고친 반주를 듣는데 꾸러미에는
       고치기 전 것이 담겼다.**

    ② 담겼어도 폰이 안 받았다
       서비스워커가 반주 MIDI 를 `cacheFirst` 로 잡는데 주소가 그대로여서,
       다시 올려도 캐시에서 옛것을 꺼내 줬다. 실측:

           처음 받은 반주 598바이트 → 고쳐서 718바이트로 다시 올림
           → 폰이 다시 받은 반주 598바이트 (옛것)

둘 다 발표회 당일에야 드러난다. 아이는 그동안 틀린 반주로 연습한다.
"""
import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piano_mr import store  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MR = os.path.dirname(HERE)
FIXTURES = os.path.join(MR, 'fixtures', 'scores')
PLAYER = os.path.join(MR, 'server', 'static', 'player')


def score(name):
    return os.path.join(FIXTURES, name + '.musicxml')


@pytest.fixture
def st(tmp_path):
    s = store.CatalogStore(str(tmp_path / 'catalog'))
    s.import_score(score('p05_waltz_c'), '작은 왈츠 (C장조)', song_id='waltz',
                   composer='자사 오리지널', book='오리지널 연습곡',
                   public_domain=True, score_license='own')
    return s


def bend(st, song_id='waltz', by=4):
    """원장님이 화성 확인 화면에서 화음 하나를 고친 것과 같은 상태로."""
    song = st.catalog.get(song_id)
    song.harmony[1]['root'] = (song.harmony[1]['root'] + by) % 12
    st.save()


# --------------------------------------------------------------------------
# ① 미리 구워 둔 반주가 화성을 따라가는가
# --------------------------------------------------------------------------

def test_the_accompaniment_follows_a_harmony_fix(st, tmp_path):
    """**이 검사가 제일 중요하다.**

    고치기 전 것이 그대로 나오면, 원장님은 고쳤다고 믿는데 아이는 틀린
    반주로 연습한다. 화면과 소리가 어긋나는데 아무 데서도 오류가 안 난다.
    """
    before = st.accomp_midi_bytes('waltz')
    bend(st)
    again = store.CatalogStore(st.root)            # 닫았다 다시 연다
    after = again.accomp_midi_bytes('waltz')
    assert after != before, '화성을 고쳤는데 반주가 그대로입니다'


def test_it_does_not_rebuild_when_nothing_changed(st):
    """반대 방향 — 아무것도 안 바뀌었는데 매번 다시 구우면 느려진다."""
    first = st.accomp_midi_bytes('waltz')
    stamp = st.stamp_of(st.midi_path('waltz'))
    second = st.accomp_midi_bytes('waltz')
    assert first == second
    assert st.stamp_of(st.midi_path('waltz')) == stamp


def test_the_stamp_records_what_it_was_built_from(st):
    st.accomp_midi_bytes('waltz')
    song = st.catalog.get('waltz')
    assert st.stamp_of(st.midi_path('waltz')) == st.song_rev(song)


def test_a_catalog_from_before_the_stamp_rebuilds_once(st):
    """표식이 생기기 전에 만든 카탈로그도 맞춰져야 한다."""
    st.accomp_midi_bytes('waltz')
    os.remove(st.stamp_path(st.midi_path('waltz')))
    assert st.stamp_of(st.midi_path('waltz')) == ''
    st.accomp_midi_bytes('waltz')                  # 표식이 없으면 다시 굽는다
    assert st.stamp_of(st.midi_path('waltz')) != ''


def test_variants_follow_the_fix_too(st):
    """편성별로 구워 둔 것도 같이 낡는다 — 하나만 고치면 절반만 맞는다."""
    before = st.accomp_midi_bytes('waltz', style='march', level='simple')
    bend(st)
    again = store.CatalogStore(st.root)
    after = again.accomp_midi_bytes('waltz', style='march', level='simple')
    assert after != before, '편성 변형이 화성을 안 따라갑니다'


# --------------------------------------------------------------------------
# ② 주소가 바뀌어야 폰이 새로 받는다
# --------------------------------------------------------------------------

def test_the_revision_changes_with_the_harmony(st):
    song = st.catalog.get('waltz')
    before = st.song_rev(song)
    bend(st)
    assert st.song_rev(st.catalog.get('waltz')) != before


def test_the_revision_ignores_things_that_do_not_change_the_sound(st):
    """제목이 바뀌었다고 폰이 반주를 다시 받을 이유는 없다."""
    song = st.catalog.get('waltz')
    before = st.song_rev(song)
    song.title = '다른 제목'
    song.level = 9
    st.save()
    assert st.song_rev(st.catalog.get('waltz')) == before


def test_the_bundle_row_carries_the_revision(st):
    row = st.song_row(st.catalog.get('waltz'))
    assert row['rev'] == st.song_rev(st.catalog.get('waltz'))


def test_static_urls_carry_the_bytes_hash(st, tmp_path):
    """정적 꾸러미는 **구운 바이트 그대로**를 해시해 붙인다."""
    out = st.export_static(str(tmp_path / 'pkg'))
    import json
    with open(os.path.join(out['out'], 'api', 'player', 'bundle'),
              encoding='utf-8') as f:
        bundle = json.load(f)
    url = bundle['songs'][0]['variants'][0]['url']
    assert '?v=' in url, f'주소에 판 표식이 없습니다: {url}'
    path, v = url.split('?v=')
    with open(os.path.join(out['out'], path), 'rb') as f:
        assert hashlib.sha1(f.read()).hexdigest()[:8] == v


def test_the_static_url_changes_after_a_fix(st, tmp_path):
    """이게 안 바뀌면 폰이 캐시에서 옛 반주를 영영 꺼낸다."""
    def url_of(where):
        import json
        out = store.CatalogStore(st.root).export_static(str(where))
        with open(os.path.join(out['out'], 'api', 'player', 'bundle'),
                  encoding='utf-8') as f:
            return json.load(f)['songs'][0]['variants'][0]['url']

    before = url_of(tmp_path / 'a')
    bend(st)
    assert url_of(tmp_path / 'b') != before


# --------------------------------------------------------------------------
# 플레이어 쪽 — 화면에서만 보이는 고장이라 여기서 못 박는다
# --------------------------------------------------------------------------

def read(name):
    with open(os.path.join(PLAYER, name), encoding='utf-8') as f:
        return f.read()


def test_the_player_puts_the_revision_in_the_address():
    """서버 경로에서도 `v` 를 붙여야 한다 — 정적 꾸러미만 고치면 절반만 맞다."""
    assert "q.set('v', song.rev)" in read('js/app.js')


def test_the_worker_version_was_bumped():
    """서비스워커 로직이 바뀌었으면 버전을 올려야 이미 깔린 기기가 받아 간다.

    안 올리면 옛 워커가 계속 돌고, 고친 것이 폰에 영영 안 간다.
    """
    sw = read('sw.js')
    assert "mr-player-v5" in sw


def test_the_worker_tells_a_stale_render_apart_from_another_arrangement():
    """오프라인에서 캐시의 다른 것을 대신 줄 때 **무엇이 다른지** 바르게 말한다.

    `v` 만 다르면 편성은 맞고 판만 옛것이다. 그걸 "기본 편성으로 재생합니다"
    라고 하면 거짓말이 된다.
    """
    sw = read('sw.js')
    assert 'onlyVersionDiffers' in sw
    assert "'stale'" in sw
    app = read('js/app.js')
    assert "=== 'stale'" in app, '화면이 그 경우를 따로 안내하지 않습니다'
