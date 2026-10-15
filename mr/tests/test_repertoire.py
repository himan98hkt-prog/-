# -*- coding: utf-8 -*-
"""콩쿨 레퍼토리 목록 — 넣어도 되는 곡인지 사람 대신 코드가 본다.

이 목록은 **데이터**다. 나중에 누가 콩쿨에서 자주 봤다는 이유로 아직 보호기간
안인 작곡가를 끼워 넣을 수 있다. 그게 팔리는 제품에 들어가면 지시서 7장이
경고한 바로 그 일이 된다. 그래서 목록 자체를 여기서 검사한다.
"""
import datetime
import json
import os

import pytest

from piano_mr import catalog as cat, orchestration as orch, repertoire as rep

TODAY = datetime.date(2026, 9, 23)


@pytest.fixture(scope='module')
def data():
    return rep.load()


# --- 보호기간 계산 ----------------------------------------------------------------

def test_the_term_is_counted_from_the_year_after_death():
    """한국 저작권법 제44조 — 사망한 **다음 해 1월 1일**부터 70년."""
    assert rep.expired(1955, TODAY) is True      # 2025년말 만료
    assert rep.expired(1956, TODAY) is False     # 2026년말 만료 (아직)
    assert rep.expired(1750, TODAY) is True      # 바흐


def test_not_knowing_when_they_died_is_not_a_yes():
    """모르는 것을 넘겨주는 쪽이 위험하다."""
    assert rep.expired(None, TODAY) is False
    with pytest.raises(cat.CopyrightError, match='확인되지 않았습니다'):
        rep.check({'id': 'x', 'title': '시험', 'composer': '누군가', 'died': None}, TODAY)


def test_a_living_copyright_says_when_it_expires():
    with pytest.raises(cat.CopyrightError) as e:
        rep.check({'id': 'x', 'title': '시험', 'composer': 'D. Kabalevsky',
                   'died': 1987}, TODAY)
    assert '2058' in str(e.value), '언제 풀리는지 말해 줘야 한다'


# --- 우리가 싣고 다니는 목록 그 자체 -------------------------------------------------

def test_every_work_we_ship_is_out_of_copyright(data):
    """**이 시험이 이 파일의 이유다.** 하나라도 보호기간 안이면 여기서 멈춘다."""
    for w in data['works']:
        rep.check(w, TODAY)


def test_the_excluded_ones_really_are_blocked(data):
    """「콩쿨에 자주 나오지만 못 쓴다」고 적어 둔 것들이 실제로 막히는가."""
    assert data['excluded'], '제외 목록이 비었습니다'
    for e in data['excluded']:
        with pytest.raises(cat.CopyrightError):
            rep.check({'id': 'x', 'title': '시험', 'composer': e['composer'],
                       'died': e['died']}, TODAY)


def test_the_list_is_usable_as_import_arguments(data):
    """목록의 값이 그대로 `import_score` 인자로 들어간다 — 오타 하나면 그 곡만 조용히 빠진다."""
    ids = [w['id'] for w in data['works']]
    assert len(ids) == len(set(ids)), '곡 id 가 겹칩니다'
    for w in data['works']:
        assert w['title'] and w['composer'] and w.get('book')
        assert w['style'] in orch.STYLES, f'{w["id"]}: 모르는 편성 {w["style"]}'
        assert 1 <= int(w['level']) <= 10, f'{w["id"]}: 난이도가 1~10 이 아닙니다'
        assert 30 <= int(w['bpm']) <= 220, f'{w["id"]}: 템포가 이상합니다'
        assert w.get('grade') in ('초급', '중급', '상급'), w['id']


def test_it_covers_the_books_a_regional_competition_actually_uses(data):
    """바이엘·체르니·부르크뮐러·소나티네·바흐 — 이 다섯이 빠지면 목록이 아니다."""
    books = ' '.join(w['book'] for w in data['works'])
    for must in ('바이엘', '체르니', '부르크뮐러', '소나티네', '바흐'):
        assert must in books, f'{must} 가 목록에 없습니다'


# --- 악보 찾기 --------------------------------------------------------------------

def test_a_score_named_after_the_id_is_found(tmp_path):
    open(tmp_path / 'burgmuller_op100_02.musicxml', 'w').close()
    w = {'id': 'burgmuller_op100_02'}
    assert rep.find_score(w, str(tmp_path)).endswith('burgmuller_op100_02.musicxml')


def test_an_explicit_file_name_wins(tmp_path):
    open(tmp_path / '아라베스크.mxl', 'w').close()
    w = {'id': 'burgmuller_op100_02', 'file': '아라베스크.mxl'}
    assert rep.find_score(w, str(tmp_path)).endswith('아라베스크.mxl')


def test_survey_splits_into_ready_missing_and_blocked(tmp_path):
    open(tmp_path / 'a.musicxml', 'w').close()
    works = [
        {'id': 'a', 'title': '있는 것', 'composer': 'J.S. Bach', 'died': 1750},
        {'id': 'b', 'title': '없는 것', 'composer': 'J.S. Bach', 'died': 1750},
        {'id': 'c', 'title': '막힌 것', 'composer': 'D. Kabalevsky', 'died': 1987},
    ]
    ready, missing, blocked = rep.survey(works, str(tmp_path), TODAY)
    assert [w['id'] for w in ready] == ['a']
    assert [w['id'] for w in missing] == ['b']
    assert [w['id'] for w in blocked] == ['c']
    assert blocked[0]['why'], '왜 막혔는지 말해 줘야 한다'


def test_a_file_that_is_not_the_right_format_is_refused(tmp_path):
    bad = tmp_path / 'x.json'
    bad.write_text('{"format": "다른것"}', encoding='utf-8')
    with pytest.raises(ValueError, match='레퍼토리 목록이 아닙니다'):
        rep.load(str(bad))
