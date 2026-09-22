# -*- coding: utf-8 -*-
"""카탈로그 CLI."""
import json
import os

import pytest

import catalog_cli
from conftest import score
from piano_mr import store


@pytest.fixture
def root(tmp_path):
    return str(tmp_path / 'catalog')


def run(root, *args):
    return catalog_cli.main(['--catalog', root, *args])


def seed(root, fixture='p05_waltz_c', song_id='waltz'):
    st = store.CatalogStore(root)
    st.import_score(score(fixture), '작은 왈츠 (C장조)', song_id=song_id,
                    composer='자사 오리지널', book='오리지널 연습곡', level=2,
                    public_domain=True, default_style='fairytale', default_bpm=108)
    return st


def test_import(root, capsys):
    assert run(root, 'import', score('p01_block_c'), '--title', '첫 화음 연습',
               '--id', 'p01', '--composer', '자사 오리지널',
               '--book', '오리지널 연습곡', '--public-domain') == 0
    out = capsys.readouterr().out
    assert 'p01' in out and 'C major' in out and '8마디' in out


def test_import_refuses_blacklist(root, capsys):
    rc = run(root, 'import', score('p01_block_c'), '--title', '하울의 움직이는 성',
             '--id', 'ghibli', '--book', '지브리', '--public-domain')
    assert rc == 2
    assert '저작권' in capsys.readouterr().err


def test_import_without_public_domain_flag(root, capsys):
    assert run(root, 'import', score('p01_block_c'), '--title', 'Some Piece',
               '--id', 'x') == 2
    assert 'public_domain' in capsys.readouterr().err


def test_import_warns_when_not_obviously_whitelisted(root, capsys):
    run(root, 'import', score('p01_block_c'), '--title', 'Untitled Study',
        '--id', 'u1', '--public-domain')
    assert '화이트리스트' in capsys.readouterr().out


def test_list_and_status(root, capsys):
    seed(root)
    assert run(root, 'list') == 0
    out = capsys.readouterr().out
    assert 'waltz' in out and '확인 대기' in out

    assert run(root, 'status') == 0
    out = capsys.readouterr().out
    assert '곡          1' in out and '20분 이내' in out


def test_list_filters_by_status(root, capsys):
    st = seed(root)
    st.save_harmony('waltz', [], verified=True)
    run(root, 'list', '--status', 'verified')
    assert 'waltz' in capsys.readouterr().out
    run(root, 'list', '--status', 'new')
    assert '곡이 없습니다' in capsys.readouterr().out


def test_show_prints_the_grid(root, capsys):
    seed(root)
    assert run(root, 'show', 'waltz') == 0
    out = capsys.readouterr().out
    assert 'm1' in out and '│' in out


def test_show_lists_human_edits(root, capsys):
    st = seed(root)
    st.save_harmony('waltz', [{'bar': 1, 'i': 0, 'label': 'Am'}])
    run(root, 'show', 'waltz')
    out = capsys.readouterr().out
    assert '사람이 고친 칸' in out and 'C -> Am' in out


def test_show_unknown(root, capsys):
    store.CatalogStore(root)
    assert run(root, 'show', '없는곡') == 1


def test_build_all(root, capsys):
    seed(root)
    assert run(root, 'build', '--all') == 0
    out = capsys.readouterr().out
    assert 'waltz' in out and 'bytes' in out
    assert os.path.exists(os.path.join(root, 'midi', 'waltz.mid'))


def test_build_with_style_variants(root, capsys):
    seed(root)
    assert run(root, 'build', '--all', '--styles', 'strings,march',
               '--levels', 'normal') == 0
    out = capsys.readouterr().out
    assert '변형 2' in out and '편성 변형' in out
    assert os.path.exists(os.path.join(root, 'midi', 'waltz__march_normal.mid'))


def test_build_rejects_unknown_style(root):
    seed(root)
    with pytest.raises(Exception):
        run(root, 'build', '--all', '--styles', '없는스타일')


def test_build_needs_a_target(root, capsys):
    store.CatalogStore(root)
    assert run(root, 'build') == 1


def test_reanalyze_all(root, capsys):
    st = seed(root)
    st.save_harmony('waltz', [{'bar': 1, 'i': 0, 'label': 'Am'}], verified=True)
    assert run(root, 'reanalyze', '--all') == 0
    again = store.CatalogStore(root)
    assert again.catalog.get('waltz').harmony_verified is False


def test_export(root, tmp_path, capsys):
    st = seed(root)
    st.save_harmony('waltz', [], verified=True)
    st.build_midi('waltz')
    out = str(tmp_path / 'player.json')
    assert run(root, 'export', out) == 0
    data = json.load(open(out, encoding='utf-8'))
    assert len(data['songs']) == 1 and data['songs'][0]['id'] == 'waltz'


def test_cache_clear(root, capsys):
    st = seed(root)
    open(os.path.join(st.cache_dir, 'a.mp3'), 'w').close()
    assert run(root, 'cache') == 0
    assert '1개 삭제' in capsys.readouterr().out
