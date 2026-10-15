# -*- coding: utf-8 -*-
"""반주를 따로 팔 수 있는 상태인가.

관리노트와 **별도로 판매하는 제품**이므로, 나가는 꾸러미에 관리노트가 한
조각도 섞이면 안 되고 동시에 **혼자서 다 돌아야** 한다. 둘 다 조용히 깨지는
종류다 — 섞여 나가도 프로그램은 잘 돌고, 빠져 나가도 우리 PC 에서는 잘 돈다.
구매자 PC 에서만 안 돈다.
"""
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import standalone  # noqa: E402

MR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    out = str(tmp_path_factory.mktemp('product') / '피아노반주')
    standalone.build(out, zip_it=True)
    return out


def names_in(root):
    return {os.path.relpath(os.path.join(r, n), root).replace(os.sep, '/')
            for r, _, fs in os.walk(root) for n in fs}


# --- 혼자 서는가 ------------------------------------------------------------

def test_the_product_has_everything_it_needs(built):
    """`MUST_HAVE` 가 빠지면 `build` 가 이미 터진다. 여기서는 그 목록 자체가
    비어 가지 않는지를 본다 — 목록을 지우면 검사도 같이 사라진다."""
    assert len(standalone.MUST_HAVE) >= 15
    have = names_in(built)
    for need in standalone.MUST_HAVE:
        assert need in have, need


def test_nothing_reaches_outside_the_product(built):
    """제품 안의 파이썬이 제품 밖을 부르면 구매자 PC 에서 import 에러가 난다."""
    bad = []
    for rel in sorted(names_in(built)):
        if not rel.endswith('.py'):
            continue
        with open(os.path.join(built, rel), encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                s = line.strip()
                if s.startswith(('import ', 'from ')) and '..' in s:
                    bad.append(f'{rel}:{i} {s}')
    assert not bad, bad[:3]


def test_the_player_is_whole(built):
    """플레이어는 폴더째 나간다. 한 장이라도 빠지면 오프라인이 통째로 죽는다."""
    have = names_in(built)
    player = {n for n in have if n.startswith('server/static/player/')}
    for need in ('index.html', 'sw.js', 'manifest.webmanifest', 'tokens.css',
                 'player.css', 'js/app.js', 'js/engine.js', 'js/midi.js',
                 'js/synth.js', 'js/store.js'):
        assert f'server/static/player/{need}' in player, need


# --- 관리노트가 안 섞였는가 ---------------------------------------------------

def test_no_academy_note_files(built):
    have = names_in(built)
    for foreign in standalone.FOREIGN:
        assert not [n for n in have if foreign in n], foreign


def test_the_developer_readme_does_not_ship(built):
    """우리가 읽는 글이다 — 「지시서 9장」이며 테스트 건수가 그대로 들어 있다."""
    assert 'README.md' not in names_in(built)
    assert '읽어보세요.txt' in names_in(built)


def test_the_buyer_note_speaks_to_the_buyer(built):
    with open(os.path.join(built, '읽어보세요.txt'), encoding='utf-8') as f:
        text = f.read()
    assert '두 번 누르' in text
    for jargon in ('지시서', 'pytest', 'CI', 'git', 'PR '):
        assert jargon not in text, jargon


# --- 개발용은 안 나가는가 -----------------------------------------------------

def test_tests_and_dev_files_are_left_behind(built):
    have = names_in(built)
    assert not [n for n in have if n.startswith('tests/')]
    for dev in ('bench.py', 'Makefile', 'pytest.ini'):
        assert dev not in have, dev


def test_no_machine_droppings(built):
    have = names_in(built)
    assert not [n for n in have if '__pycache__' in n or n.endswith('.pyc')]
    assert not [n for n in have if n.startswith('catalog/')]


def test_with_dev_puts_them_back(tmp_path):
    """유지보수용으로 받고 싶을 때. **파는 꾸러미가 아니다.**"""
    out = str(tmp_path / 'dev')
    standalone.build(out, dev=True)
    have = names_in(out)
    assert [n for n in have if n.startswith('tests/')]
    assert 'README.md' in have


# --- 압축 ------------------------------------------------------------------

def test_the_zip_has_one_folder_inside(built):
    """바탕화면에서 풀었을 때 파일 백 개가 흩어지면 안 된다."""
    with zipfile.ZipFile(built + '.zip') as z:
        tops = {n.split('/')[0] for n in z.namelist()}
    assert tops == {os.path.basename(built)}, tops
