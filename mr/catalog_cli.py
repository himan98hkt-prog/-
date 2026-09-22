#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카탈로그 관리 CLI — 지시서 9장 2단계.

    python3 catalog_cli.py import score.mxl --title "체르니 100번 5번" --book "체르니 100"
    python3 catalog_cli.py status
    python3 catalog_cli.py list
    python3 catalog_cli.py show czerny100_05
    python3 catalog_cli.py reanalyze --all
    python3 catalog_cli.py build --all --styles strings,chamber,march --audio
    python3 catalog_cli.py export player.json
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time  # noqa: E402

from piano_mr import (catalog as cat, harmony, orchestration as orch,  # noqa: E402
                      render, store)

STATUS_LABEL = {'verified': '확인 완료', 'analyzed': '확인 대기', 'new': '분석 전'}


def mmss(sec: int) -> str:
    return f'{sec // 60}분 {sec % 60:02d}초' if sec else '—'


def cmd_import(st: store.CatalogStore, a) -> int:
    try:
        song = st.import_score(
            a.score, a.title, song_id=a.id, composer=a.composer, book=a.book,
            level=a.level, public_domain=a.public_domain, default_style=a.style,
            default_level=a.level_name, default_bpm=a.bpm, key_name=a.key,
            recommended_bpm=a.recommended_bpm or [], default_curve=a.curve,
            count_in=a.count_in, note=a.note)
    except cat.CopyrightError as e:
        print(f'저작권 확인 실패: {e}', file=sys.stderr)
        print('  화이트리스트(지시서 7장)에 있는 곡만 넣고, --public-domain 을 붙이세요.',
              file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as e:
        print(f'오류: {e}', file=sys.stderr)
        return 1
    weak = song.low_confidence_count
    print(f'{song.id}  {song.title}')
    print(f'  조성 {song.key} · 박자 {song.time} · {song.measures}마디 · '
          f'세그먼트 {len(song.harmony)}개')
    print(f'  확인 필요 {weak}곳' if weak else '  확신이 약한 구간 없음')
    if not cat.looks_whitelisted(song.title, song.composer, song.book):
        print('  ⚠ 화이트리스트 문구가 안 보입니다. 퍼블릭도메인이 맞는지 확인하세요.')
    return 0


def cmd_list(st: store.CatalogStore, a) -> int:
    rows = st.rows()
    if a.status:
        rows = [r for r in rows if r['status'] == a.status]
    if not rows:
        print('곡이 없습니다.')
        return 0
    print(f'{"id":<24} {"상태":<10} {"난이도":>5} {"마디":>5} {"확인필요":>7} '
          f'{"검수":>10}  제목')
    for r in rows:
        print(f'{r["id"]:<24} {STATUS_LABEL[r["status"]]:<10} {r["level"]:>5} '
              f'{r["measures"]:>5} {r["low"]:>7} {mmss(r["verify_seconds"]):>10}  '
              f'{r["title"]}')
    return 0


def cmd_status(st: store.CatalogStore, a) -> int:
    s = st.stats()
    done = (s['verified'] / s['total'] * 100) if s['total'] else 0
    print(f'카탈로그: {st.root}\n')
    print(f'  곡          {s["total"]}')
    print(f'  확인 완료   {s["verified"]} ({done:.0f}%)')
    print(f'  확인 대기   {s["analyzed"]}')
    print(f'  분석 전     {s["new"]}')
    print(f'  확인 필요 칸 {s["low_confidence_cells"]}')
    print(f'  평균 검수   {mmss(s["avg_verify_seconds"])}  '
          f'(목표 20분 이내 · 초과 {s["over_20min"]}곡)')
    print(f'  반주 MIDI   {s["midi_files"]}개 · {s["midi_kb"]} KB '
          f'(미리 구운 곡 {s["prebuilt"]}/{s["total"]})')
    print(f'  캐시된 음원 {s["cached_audio"]}개 (지워도 되는 파생물)')
    print('\n지시서 9장 2단계 목표: 약 150곡 · 곡당 검수 20분 이내')
    return 0


def cmd_show(st: store.CatalogStore, a) -> int:
    try:
        song = st.catalog.get(a.id)
    except KeyError as e:
        print(f'오류: {e}', file=sys.stderr)
        return 1
    print(f'{song.title}  [{STATUS_LABEL[song.status]}]')
    print(f'{song.composer} · {song.book} · 난이도 {song.level}')
    print(f'조성 {song.key} · 박자 {song.time} · {song.measures}마디 · '
          f'검수 {mmss(song.verify_seconds)}\n')
    segs = [{'m': h['m'], 'i': h['i'], 'root': h['root'], 'qual': h['qual'],
             'label': harmony.label(h['root'], h['qual'])} for h in song.harmony]
    print(harmony.to_grid(segs))
    weak = [h for h in song.harmony if h.get('conf', 1.0) < cat.LOW_CONF]
    if weak:
        print(f'\n확인 필요 {len(weak)}곳:')
        for h in weak[:20]:
            print(f'   m{h["m"]}-{h["i"] + 1}  {harmony.label(h["root"], h["qual"]):<5}'
                  f' 다음 후보: {", ".join(h.get("alts", [])[:2]) or "—"}')
    changed = [h for h in song.harmony
               if h.get('auto') and h['auto'] != harmony.label(h['root'], h['qual'])]
    if changed:
        print(f'\n사람이 고친 칸 {len(changed)}곳:')
        for h in changed[:20]:
            print(f'   m{h["m"]}-{h["i"] + 1}  {h["auto"]} -> '
                  f'{harmony.label(h["root"], h["qual"])}')
    return 0


def _targets(st, a):
    return list(st.catalog.songs) if a.all else ([a.id] if a.id else [])


def cmd_reanalyze(st: store.CatalogStore, a) -> int:
    ids = _targets(st, a)
    if not ids:
        print('--all 이나 --id 를 주세요.', file=sys.stderr)
        return 1
    for i in ids:
        song = st.reanalyze(i)
        print(f'{i}: {song.measures}마디 · 확인 필요 {song.low_confidence_count}곳')
    return 0


def cmd_build(st: store.CatalogStore, a) -> int:
    """미리 만들어 둘 수 있는 것을 다 만든다.

    반주 MIDI 는 항상. 편성 변형과 MR mp3 는 요청하면.
    """
    ids = _targets(st, a)
    if not ids:
        print('--all 이나 --id 를 주세요.', file=sys.stderr)
        return 1
    styles = [orch.check_style(x) for x in (a.styles or '').split(',') if x.strip()]
    levels = [orch.check_level(x) for x in (a.levels or '').split(',') if x.strip()]

    total = nvar = 0
    t0 = time.time()
    for n, i in enumerate(ids, 1):
        made = st.prebuild(i, styles=styles, levels=levels, audio=a.audio,
                           mix=a.mix, count_in=a.count_in)
        size = os.path.getsize(made['midi'])
        total += size
        for v in made['variants']:
            total += os.path.getsize(v)
            nvar += 1
        extra = f" + 변형 {len(made['variants'])}" if made['variants'] else ''
        extra += '  [mp3 준비됨]' if made['audio'] else ''
        print(f"[{n}/{len(ids)}] {i}: {size:,} bytes{extra}")

    print(f'\n반주 MIDI {len(ids)}개' + (f' + 편성 변형 {nvar}개' if nvar else '')
          + f' = {total / 1024:.1f} KB · {time.time() - t0:.1f}초')
    print(f'같은 것을 오디오로 저장했다면 약 {total / 1024 / 1024 * 2300:.0f} MB '
          '였습니다 (지시서 2.4 — 그래서 MIDI 만 보관합니다)')
    if a.audio:
        print(f'MR mp3 는 캐시에 있습니다: {os.path.join(st.root, "cache")}')
        if a.mix == 'mr' and not a.count_in and not any(
                st.catalog.get(i).count_in for i in ids):
            print('참고: MR 에는 원곡 피아노가 없어 시작 신호가 없습니다. '
                  '혼자 연습할 음원이면 --count-in 1 을 권합니다.')
    return 0


def cmd_export(st: store.CatalogStore, a) -> int:
    path = st.export_player(a.out)
    n = sum(1 for s in st.catalog.songs.values() if s.harmony_verified)
    print(f'{path} — 확인 완료 {n}곡 (오디오 없음)')
    return 0


def cmd_cache(st: store.CatalogStore, a) -> int:
    print(f'렌더 캐시 {st.clear_cache()}개 삭제')
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog='catalog_cli.py', description='카탈로그 관리')
    p.add_argument('--catalog', default='catalog', help='카탈로그 디렉터리 (기본: ./catalog)')
    sub = p.add_subparsers(dest='cmd', required=True)

    i = sub.add_parser('import', help='악보를 카탈로그에 넣는다')
    i.add_argument('score')
    i.add_argument('--title', required=True)
    i.add_argument('--id')
    i.add_argument('--composer', default='')
    i.add_argument('--book', default='')
    i.add_argument('--level', type=int, default=1, help='1~10 학원 기준 난이도')
    i.add_argument('--public-domain', action='store_true',
                   help='퍼블릭도메인임을 확인했다 (지시서 7장 — 없으면 거부)')
    i.add_argument('--style', default=orch.DEFAULT_STYLE, choices=sorted(orch.STYLES))
    i.add_argument('--level-name', default='normal', choices=list(orch.LEVELS))
    i.add_argument('--bpm', type=int, default=96)
    i.add_argument('--key', help='조성을 확정해 둔다 (짧은 악보에서 자동 판정이 흔들릴 때)')
    i.add_argument('--curve', default='flat', choices=['flat', 'build'],
                   help='flat(기본, 곡 전체에 깔린다) / build(발표회용)')
    i.add_argument('--count-in', type=int, default=0, metavar='N',
                   help='음원에 카운트인 N마디를 구워 넣는다 (MR 은 시작 신호가 없다)')
    i.add_argument('--recommended-bpm', type=int, nargs='*')
    i.add_argument('--note', default='')
    i.set_defaults(fn=cmd_import)

    l = sub.add_parser('list', help='곡 목록')
    l.add_argument('--status', choices=['new', 'analyzed', 'verified'])
    l.set_defaults(fn=cmd_list)

    s = sub.add_parser('status', help='제작 현황')
    s.set_defaults(fn=cmd_status)

    sh = sub.add_parser('show', help='한 곡의 화성 격자')
    sh.add_argument('id')
    sh.set_defaults(fn=cmd_show)

    r = sub.add_parser('reanalyze', help='엔진으로 다시 분석 (사람이 고친 값은 사라진다)')
    r.add_argument('--id')
    r.add_argument('--all', action='store_true')
    r.set_defaults(fn=cmd_reanalyze)

    m = sub.add_parser('build', help='반주를 미리 만들어 둔다 (MIDI · 편성 변형 · MR mp3)')
    m.add_argument('--id')
    m.add_argument('--all', action='store_true')
    m.add_argument('--styles', help='편성 변형도 함께 (쉼표로: strings,chamber,march)')
    m.add_argument('--levels', help='변형의 두께 (쉼표로: simple,normal,rich)')
    m.add_argument('--audio', action='store_true',
                   help='MR mp3 까지 미리 구워 캐시에 넣는다 (현장에서 안 기다리게)')
    m.add_argument('--mix', default=render.DEFAULT_MIX, choices=list(render.MIXES),
                   help='--audio 로 구울 음원 종류 (기본: mr — 반주만)')
    m.add_argument('--count-in', type=int, default=None, metavar='N',
                   help='--audio 로 구울 음원에 카운트인 N마디를 넣는다. '
                        'MR 은 피아노가 없어서 시작 신호가 없다 (곡 설정값이 기본)')
    m.set_defaults(fn=cmd_build)

    e = sub.add_parser('export', help='3단계 플레이어용 번들 내보내기')
    e.add_argument('out')
    e.set_defaults(fn=cmd_export)

    c = sub.add_parser('cache', help='렌더 캐시 비우기')
    c.set_defaults(fn=cmd_cache)
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    st = store.CatalogStore(a.catalog)
    return a.fn(st, a)


if __name__ == '__main__':
    raise SystemExit(main())
