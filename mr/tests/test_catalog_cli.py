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


# --- 4단계 PDF 업로드 (신청제 운영자용) ------------------------------------------

def submit(root, pages='three_pages.pdf', title='체르니 100번 5번'):
    from conftest import FIXTURES
    st = store.CatalogStore(root)
    with open(os.path.join(FIXTURES, 'pdf', pages), 'rb') as f:
        blob = f.read()
    return st.submit_pdf(blob, 'czerny.pdf', account='행복피아노', title=title)


def test_uploads_shows_what_needs_doing(root, capsys):
    job = submit(root)
    assert run(root, 'uploads') == 0
    out = capsys.readouterr().out
    assert job['id'] in out and '악보 인식 중' in out
    assert '3쪽' in out and '1,200원' in out
    assert 'incoming' in out              # 사람이 PDF 를 어디서 집어 가는지
    assert 'deliver' in out               # 다음에 칠 명령


def test_uploads_on_an_empty_catalog_says_so(root, capsys):
    store.CatalogStore(root)
    assert run(root, 'uploads') == 0
    assert '올라온 악보가 없습니다' in capsys.readouterr().out


def test_deliver_attaches_a_musicxml_and_points_at_the_verify_screen(root, capsys):
    job = submit(root)
    assert run(root, 'deliver', job['id'], score('p05_waltz_c'),
               '--id', 'czerny100_05') == 0
    out = capsys.readouterr().out
    assert '화성 확인 대기' in out and 'czerny100_05' in out
    assert '90~95%' in out                # "바로 완성"이라고 하지 않는다
    st = store.CatalogStore(root)
    assert st.catalog.get('czerny100_05').owner == '행복피아노'
    assert os.listdir(st.incoming_dir) == []      # PDF 는 지워졌다


def test_limit_changes_the_monthly_cap_and_shows_the_money(root, capsys):
    store.CatalogStore(root)
    assert run(root, 'limit', '6') == 0
    assert '월 6쪽' in capsys.readouterr().out
    assert run(root, 'limit') == 0
    out = capsys.readouterr().out
    assert '월 6쪽' in out and '2,400원' in out    # 6쪽 × 400원


def test_sweep_reports_what_it_cleared(root, capsys):
    job = submit(root)
    st = store.CatalogStore(root)
    st.ledger.update(job['id'], pdf_at='2020-01-01T00:00:00')
    assert run(root, 'sweep', '--hours', '1') == 0
    out = capsys.readouterr().out
    assert '1건 정리' in out
    assert os.listdir(store.CatalogStore(root).incoming_dir) == []


def test_poll_with_no_running_jobs_says_so(root, capsys):
    store.CatalogStore(root)
    assert run(root, 'poll') == 0
    assert '인식 중인 작업이 없습니다' in capsys.readouterr().out


# --- 5단계 관리노트 연동 -----------------------------------------------------------

def roster_path(tmp_path):
    import json
    from piano_mr import roster as R
    p = tmp_path / '명단.json'
    p.write_text(json.dumps({
        'format': R.ROSTER_FORMAT, 'version': 1, 'academy': '행복피아노',
        'students': [{'id': 's1', 'name': '김지우', 'class': '월수금 4시', 'active': True},
                     {'id': 's2', 'name': '박서준', 'class': '', 'active': False}]},
        ensure_ascii=False), encoding='utf-8')
    return str(p)


def test_roster_with_no_file_tells_you_where_to_get_one(root, capsys):
    store.CatalogStore(root)
    assert run(root, 'roster') == 0
    out = capsys.readouterr().out
    assert '아직 명단을 받지 않았습니다' in out
    assert '관리노트' in out and '설정' in out       # 어디서 내려받는지 알려 준다


def test_roster_imports_and_then_lists(root, tmp_path, capsys):
    store.CatalogStore(root)
    assert run(root, 'roster', roster_path(tmp_path)) == 0
    assert '2명을 받았습니다' in capsys.readouterr().out

    assert run(root, 'roster') == 0
    out = capsys.readouterr().out
    assert '행복피아노' in out and '재원 1명' in out
    assert '김지우' in out and '월수금 4시' in out


def test_roster_reports_who_left(root, tmp_path, capsys):
    import json
    from piano_mr import roster as R
    store.CatalogStore(root)
    run(root, 'roster', roster_path(tmp_path))
    capsys.readouterr()
    smaller = tmp_path / '작은명단.json'
    smaller.write_text(json.dumps({
        'format': R.ROSTER_FORMAT, 'version': 1,
        'students': [{'id': 's1', 'name': '김지우'}]}, ensure_ascii=False),
        encoding='utf-8')
    run(root, 'roster', str(smaller))
    assert '빠진 학생 1명' in capsys.readouterr().out
