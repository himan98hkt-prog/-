#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카탈로그 씨앗 — 지금 이 환경에서 **합법적으로 확보 가능한** 곡만 넣는다.

곡마다 카운트인 1마디를 기본으로 둔다. MR 에는 원곡 피아노가 없어서 시작 신호가
없기 때문에, 혼자 연습할 음원이라면 세는 소리가 앞에 있어야 아이가 들어올 수 있다.

지시서 9장 2단계의 목표는 약 150곡(체르니 100 전곡 + 바이엘 후반 + 부르크뮐러 25)이다.
그 악보들은 MuseScore.com·IMSLP 에서 사람이 골라 받아야 하고, 여기서는 못 한다.

대신 파이프라인이 실제로 도는 것을 증명할 만큼은 넣는다:

  * music21 코퍼스의 퍼블릭도메인 피아노곡 (바흐·모차르트·클라라 슈만)
  * 우리가 만든 오리지널 연습곡 20곡 (지시서 7장 화이트리스트의 마지막 항목)

악보를 더 확보하면 `catalog_cli.py import` 로 같은 자리에 들어간다.
"""
import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from piano_mr import store  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures')

# music21 코퍼스의 퍼블릭도메인 피아노곡. 전부 지시서 7장 화이트리스트 안이다.
CORPUS = [
    dict(corpus='bach/bwv846', id='bach_bwv846_prelude',
         title='바흐 평균율 1권 1번 전주곡', composer='J.S. Bach',
         book='바흐', level=6, style='chamber', bpm=72,
         note='왼손 분산화음 위에 화성만 움직이는 곡 — 반주가 가장 잘 붙는 형태'),
    dict(corpus='mozart/k545/movement1_exposition', id='mozart_k545_1_exp',
         title='모차르트 소나타 K.545 1악장 (제시부)', composer='W.A. Mozart',
         book='모차르트 쉬운 소나타', level=7, style='chamber', bpm=126,
         note='프로토타입 검증곡 (지시서 12장)'),
    dict(corpus='schumann_clara/polonaise_op1n1', id='cschumann_op1n1',
         title='클라라 슈만 폴로네즈 Op.1-1', composer='Clara Schumann',
         book='슈만', level=6, style='fairytale', bpm=104),
    dict(corpus='schumann_clara/polonaise_op1n2', id='cschumann_op1n2',
         title='클라라 슈만 폴로네즈 Op.1-2', composer='Clara Schumann',
         book='슈만', level=6, style='fairytale', bpm=104),
    dict(corpus='schumann_clara/polonaise_op1n3', id='cschumann_op1n3',
         title='클라라 슈만 폴로네즈 Op.1-3', composer='Clara Schumann',
         book='슈만', level=6, style='chamber', bpm=100),
    dict(corpus='schumann_clara/polonaise_op1n4', id='cschumann_op1n4',
         title='클라라 슈만 폴로네즈 Op.1-4', composer='Clara Schumann',
         book='슈만', level=6, style='chamber', bpm=100),

    # 여기 셋은 코퍼스를 다시 훑어 **피아노 독주곡만** 골라낸 것이다. 코퍼스의
    # 베토벤·하이든·모차르트는 거의 다 현악 4중주고, 비치·클라라 슈만 Op.17 ·
    # 슈만 Op.48 은 합창·3중주·가곡이라 뺐다 — 피아노 독주가 아니면 이 제품이
    # 쓸 자리가 없다.
    dict(corpus='chopin/mazurka06-2', id='chopin_mazurka_op6n2',
         title='쇼팽 마주르카 Op.6-2', composer='F. Chopin',
         book='쇼팽', level=7, style='chamber', bpm=132,
         note='지역 콩쿨 중급 단골. 마주르카 리듬이라 반주가 박을 끌지 않게 두께는 간단부터'),
    dict(corpus='cpebach/h186', id='cpebach_h186',
         title='C.P.E. 바흐 H.186', composer='C.P.E. Bach',
         book='바흐', level=6, style='strings', bpm=92,
         note='바로크-고전 사이. 인벤션 대신 쓸 수 있는 몇 안 되는 퍼블릭도메인 건반곡'),
    dict(corpus='joplin/maple_leaf_rag', id='joplin_maple_leaf',
         title='조플린 단풍잎 래그', composer='S. Joplin',
         book='래그타임', level=7, style='pop', bpm=100,
         note='싱커페이션이 강해 반주가 박을 또박또박 잡아 줘야 한다'),
]


def seed_originals(st: store.CatalogStore, verbose=True) -> int:
    """오리지널 연습곡 20곡 — 저작권 걱정 0, 악보까지 같이 팔 수 있다."""
    truth_dir = os.path.join(FIXTURES, 'truth')
    n = 0
    for name in sorted(os.listdir(truth_dir)):
        if not name.endswith('.json'):
            continue
        with open(os.path.join(truth_dir, name), encoding='utf-8') as f:
            rec = json.load(f)
        if rec['id'] in st.catalog.songs:
            continue
        path = os.path.join(FIXTURES, 'scores', rec['id'] + '.musicxml')
        song = st.import_score(
            path, rec['title'], song_id=rec['id'], composer='자사 오리지널',
            book='오리지널 연습곡', level=rec.get('level', 3), public_domain=True,
            default_style=rec.get('default_style', 'strings'),
            default_bpm=96, count_in=1, note='회귀 테스트 세트와 같은 곡')
        n += 1
        if verbose:
            print(f'  {song.id:<24} {song.key:<10} {song.measures:>3}마디 '
                  f'확인필요 {song.low_confidence_count}')
    return n


def seed_corpus(st: store.CatalogStore, verbose=True) -> int:
    from music21 import corpus
    n = 0
    for spec in CORPUS:
        if spec['id'] in st.catalog.songs:
            continue
        try:
            sc = corpus.parse(spec['corpus'])
        except Exception as e:
            if verbose:
                print(f'  건너뜀 {spec["id"]}: {e}')
            continue
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, spec['id'] + '.musicxml')
            sc.write('musicxml', fp=path)
            song = st.import_score(
                path, spec['title'], song_id=spec['id'], composer=spec['composer'],
                book=spec['book'], level=spec['level'], public_domain=True,
                default_style=spec['style'], default_bpm=spec['bpm'],
                count_in=1, note=spec.get('note', ''))
        n += 1
        if verbose:
            print(f'  {song.id:<24} {song.key:<10} {song.measures:>3}마디 '
                  f'확인필요 {song.low_confidence_count}')
    return n


# 발표회 프로그램 예시 (지시서 6장 · 모듈 ⑤-3).
# 운영 화면이 실제 데이터로 도는 것을 보여 주기 위한 것이라, 카탈로그에 실제로
# 들어 있는 곡만 쓴다.
PROGRAM = dict(
    id='winter_2026', event='2026 겨울 발표회', date='2026-12-20',
    venue='구민회관 아트홀',
    queue=[
        ('김지우', 'p05_waltz_c', 84, 'fairytale', 'normal', '리허설 완료'),
        ('박서준', 'p08_three_eight', 88, 'fairytale', 'simple', ''),
        ('이하은', 'p01_block_c', 76, 'strings', 'simple', '첫 무대'),
        ('정도윤', 'p07_minuet_g', 104, 'chamber', 'normal', ''),
        ('최서아', 'p12_minor_dm_waltz', 92, 'warm', 'normal', ''),
        ('강민준', 'p03_scale_g', 112, 'march', 'normal', ''),
        ('윤채원', 'bach_bwv846_prelude', 72, 'chamber', 'normal', '반주 볼륨 낮게'),
        ('임시우', 'p20_secondary_f', 96, 'orchestra', 'normal', ''),
        ('한지호', 'cschumann_op1n2', 104, 'chamber', 'rich', ''),
        ('오예린', 'mozart_k545_1_exp', 120, 'orchestra', 'rich', '마지막 순서'),
    ])


def seed_program(st: store.CatalogStore, verbose=True) -> int:
    from piano_mr import catalog as cat
    if any(p.id == PROGRAM['id'] for p in st.catalog.programs):
        return 0
    items = []
    for n, (student, song_id, bpm, style, level, note) in enumerate(PROGRAM['queue'], 1):
        if song_id not in st.catalog.songs:
            if verbose:
                print(f'  건너뜀 {student}: 카탈로그에 {song_id} 가 없습니다')
            continue
        items.append(cat.QueueItem(order=n, student=student, song_id=song_id,
                                   bpm=bpm, style=style, level=level, note=note))
    if not items:
        return 0
    prog = cat.Program(id=PROGRAM['id'], event=PROGRAM['event'], date=PROGRAM['date'],
                       venue=PROGRAM['venue'], queue=items)
    st.catalog.add_program(prog)
    st.save()
    if verbose:
        print(f"  {prog.event} — {len(items)}곡 · 약 {prog.minutes}분")
        for line in prog.cue_lines()[:3]:
            print(f'    {line}')
        print('    ...')
    return 1


def shown_path(path: str) -> str:
    """안내 문구에 넣을 경로. 현재 위치 밖이면 `../../..` 대신 절대경로를 쓴다."""
    rel = os.path.relpath(path)
    return path if rel.startswith('..') else rel


def main():
    ap = argparse.ArgumentParser(description='카탈로그 씨앗 넣기')
    ap.add_argument('--catalog', default='catalog')
    ap.add_argument('--skip-corpus', action='store_true')
    ap.add_argument('--skip-originals', action='store_true')
    ap.add_argument('--skip-program', action='store_true')
    a = ap.parse_args()

    st = store.CatalogStore(a.catalog)
    total = 0
    if not a.skip_originals:
        print('오리지널 연습곡:')
        total += seed_originals(st)
    if not a.skip_corpus:
        print('\n퍼블릭도메인 코퍼스:')
        total += seed_corpus(st)
    if not a.skip_program:
        print('\n발표회 프로그램:')
        seed_program(st)

    s = st.stats()
    print(f'\n{total}곡 추가 — 카탈로그 총 {s["total"]}곡, 확인 대기 {s["analyzed"]}곡')
    print(f'카탈로그: {st.root}')
    print(f'\n다음: python3 serve.py --catalog {shown_path(st.root)}')
    print('  화성 확인 화면   http://127.0.0.1:8765/')
    print('  발표회 운영 화면 http://127.0.0.1:8765/static/program.html')
    print('지시서 9장 2단계 목표인 약 150곡을 채우려면 체르니 100 / 바이엘 후반 /')
    print('부르크뮐러 25 의 MusicXML 을 확보해 catalog_cli.py import 로 넣으세요.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
