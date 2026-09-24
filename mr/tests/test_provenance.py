# -*- coding: utf-8 -*-
"""악보 **입력본**의 출처 — 곡이 만료된 것과 팔 수 있는 것은 다른 문제다.

여기서 잡는 고장은 전부 **조용한** 것들이다. 라이선스가 틀려도 프로그램은 잘
돌고, 꾸러미도 잘 만들어지고, 반주도 잘 나온다. 틀린 게 드러나는 것은 **팔고
난 뒤**다. 그래서 검사로 못 박는다.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import seed_catalog                                    # noqa: E402
from piano_mr import provenance as prov, store         # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(os.path.dirname(HERE), 'fixtures', 'scores')


def score(name):
    return os.path.join(FIXTURES, name + '.musicxml')


def make(tmp_path, **kw):
    st = store.CatalogStore(str(tmp_path / 'catalog'))
    st.import_score(score('p05_waltz_c'), '작은 왈츠 (C장조)', song_id='waltz',
                    composer='자사 오리지널', book='오리지널 연습곡',
                    public_domain=True, **kw)
    return st


# --------------------------------------------------------------------------
# 무엇을 팔 수 있는가
# --------------------------------------------------------------------------

@pytest.mark.parametrize('key', ['own', 'omr', 'cc0', 'pd', 'cc-by', 'cc-by-sa'])
def test_these_can_be_sold(key):
    assert prov.sellable(key), f'{key} 는 팔 수 있어야 합니다'


@pytest.mark.parametrize('key', ['cc-by-nc', 'cc-by-nc-sa', 'cc-by-nc-nd',
                                 'cc-by-nd', 'unknown'])
def test_these_cannot_be_sold(key):
    assert not prov.sellable(key), f'{key} 는 팔 수 없어야 합니다'


def test_noderiv_allows_commerce_but_still_blocks_us():
    """ND 는 **상업적 사용을 허용하면서도** 우리한테는 막힌 것이다.

    `commercial` 만 보고 통과시키면 여기서 틀린다. 반주를 붙이는 행위 자체가
    2차적 저작물이라 변경금지에 걸린다.
    """
    t = prov.term('cc-by-nd')
    assert t.commercial is True
    assert t.sellable is False


def test_sharealike_is_sellable_but_says_what_it_costs():
    t = prov.term('cc-by-sa')
    assert t.sellable is True
    assert '같은 조건' in t.caution, '동일조건변경허락이라는 걸 말해 줘야 합니다'


@pytest.mark.parametrize('key', ['', None, '   ', '모르는키', 'CC-BY-NC-SA-9.9'])
def test_anything_we_do_not_recognise_falls_to_unknown(key):
    """모르는 값은 **안전한 쪽으로** 떨어진다.

    옛 카탈로그 파일이나 사람이 손으로 고친 값이 들어와도 마찬가지다. 여기서
    예외를 던지면 카탈로그가 통째로 안 열린다.
    """
    assert prov.term(key).key == 'unknown'
    assert not prov.sellable(key)


def test_case_and_spacing_do_not_matter():
    assert prov.term('  CC-BY-NC-SA  ').key == 'cc-by-nc-sa'


# --------------------------------------------------------------------------
# 가져올 때
# --------------------------------------------------------------------------

def test_a_typo_in_the_licence_is_caught_at_import(tmp_path):
    """오타를 **넣을 때** 잡는다.

    안 잡으면 `cc0` 를 `cc-0` 로 친 악보가 조용히 'unknown' 이 되고, 팔 수 있는
    악보가 이유도 없이 꾸러미에서 빠진다. 원장님은 곡이 왜 없는지 모른다.
    """
    with pytest.raises(ValueError, match='모르는 입력본 출처'):
        make(tmp_path, score_license='cc-0')


def test_import_records_what_we_were_told(tmp_path):
    st = make(tmp_path, score_source='IMSLP', score_license='pd')
    song = st.catalog.get('waltz')
    assert (song.score_source, song.score_license) == ('IMSLP', 'pd')


def test_licence_survives_a_save_and_load(tmp_path):
    """카탈로그를 닫았다 열어도 출처가 남아 있어야 한다."""
    make(tmp_path, score_source='Mutopia', score_license='cc0')
    again = store.CatalogStore(str(tmp_path / 'catalog'))
    assert again.catalog.get('waltz').score_license == 'cc0'


def test_an_old_catalog_without_the_field_still_opens(tmp_path):
    """이 기능이 생기기 전에 만든 카탈로그도 열려야 한다 — 열리고, `unknown` 이다."""
    st = make(tmp_path)
    path = st.catalog.save()
    import json
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    for s in data['songs']:            # 필드가 없던 시절처럼 만든다
        s.pop('score_source', None)
        s.pop('score_license', None)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

    again = store.CatalogStore(str(tmp_path / 'catalog'))
    assert again.catalog.get('waltz').score_license == ''
    assert not prov.sellable(again.catalog.get('waltz').score_license)


# --------------------------------------------------------------------------
# 꾸러미 — 여기가 실제로 팔려 나가는 자리다
# --------------------------------------------------------------------------

def test_the_sale_package_leaves_out_what_we_cannot_sell(tmp_path):
    st = make(tmp_path, score_license='cc-by-nc-sa')
    out = st.export_static(str(tmp_path / 'pkg'))
    assert out['songs'] == 0
    assert [d['id'] for d in out['dropped']] == ['waltz']


def test_it_says_which_song_and_why(tmp_path):
    """뺀 것을 조용히 빼면 안 된다 — 원장님이 곡이 없어진 줄 안다."""
    st = make(tmp_path, score_source='kernScores', score_license='cc-by-nc-sa')
    dropped = st.export_static(str(tmp_path / 'pkg'))['dropped'][0]
    assert dropped['title'] == '작은 왈츠 (C장조)'
    assert dropped['source'] == 'kernScores'
    assert '비영리' in dropped['license']


def test_a_personal_package_keeps_everything(tmp_path):
    """원장님이 **자기 학원에서만** 쓰시는 건 파는 게 아니다."""
    st = make(tmp_path, score_license='unknown')
    out = st.export_static(str(tmp_path / 'pkg'), for_sale=False)
    assert out['songs'] == 1
    assert out['dropped'] == []


def test_our_own_scores_always_go_in(tmp_path):
    st = make(tmp_path, score_license='own')
    assert st.export_static(str(tmp_path / 'pkg'))['songs'] == 1


def test_sharealike_ships_but_warns(tmp_path):
    """팔 수는 있다. 다만 **말은 해야 한다** — 결과물까지 같은 조건으로 풀린다."""
    st = make(tmp_path, score_license='cc-by-sa')
    out = st.export_static(str(tmp_path / 'pkg'))
    assert out['songs'] == 1
    assert out['cautions'] and '같은 조건' in out['cautions'][0]['caution']


# --------------------------------------------------------------------------
# 우리가 실제로 넣어 둔 곡들
# --------------------------------------------------------------------------

def test_the_corpus_songs_are_not_sold(tmp_path):
    """music21 코퍼스에서 온 아홉 곡은 **판매용 꾸러미에 못 들어간다.**

    곡은 전부 만료됐다. 문제는 입력본이다 — 코퍼스의 license.txt 가 스스로
    "일부는 상업적으로 쓸 수 없다"고 하면서 **어느 것인지는 알려 주지 않는다.**
    실제로 코퍼스의 쇼팽 마주르카는 `!!!ENC: Craig Stuart Sapp` 이고, 같은
    사람의 GitHub 저장소들은 전부 CC BY-NC-SA 다.

    이 값을 'pd' 같은 걸로 바꾸면 아홉 곡이 조용히 판매용에 들어간다.
    """
    assert seed_catalog.CORPUS_LICENSE == 'unknown'
    assert not prov.sellable(seed_catalog.CORPUS_LICENSE)


def test_our_originals_are_marked_as_ours(tmp_path):
    """자사 오리지널 20곡은 악보까지 같이 팔 수 있다 — 그렇게 기록돼야 한다."""
    st = store.CatalogStore(str(tmp_path / 'catalog'))
    seed_catalog.seed_originals(st, verbose=False)
    songs = list(st.catalog.songs.values())
    assert songs, '오리지널이 하나도 안 들어갔습니다'
    assert all(s.score_license == 'own' for s in songs)
    assert all(prov.sellable(s.score_license) for s in songs)
