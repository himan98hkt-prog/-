# -*- coding: utf-8 -*-
"""CLI — 지시서 9장 1단계 완료 항목.

    python mr.py score.mxl --style chamber --level normal --bpm 84 -o out.mp3
    python mr.py score.mxl --analyze-only
    python mr.py --styles
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import List, Optional

from . import __version__, harmony, orchestration as orch, render, score_loader


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='mr.py',
        description='피아노 악보 -> 오케스트라 반주. 전 과정 로컬 연산, API 호출 0회.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""예시
  python mr.py score.mxl --style chamber --level normal --bpm 84 -o out.mp3
  python mr.py score.mxl --analyze-only            # 화성만 확인 (음원 안 만듦)
  python mr.py score.mxl --all-formats --stems     # 연습용/무대용/영상편집용 전부
  python mr.py --styles                            # 스타일 7종 목록
""")
    p.add_argument('score', nargs='?', help='MusicXML(.xml/.mxl) 또는 MIDI(.mid)')
    p.add_argument('-o', '--out', help='출력 파일 (.mp3 / .wav / .mid)')
    p.add_argument('--out-dir', default='.', help='출력 디렉터리 (기본: 현재 위치)')
    p.add_argument('--tag', help='출력 파일 이름의 앞부분 (기본: 악보 파일명)')

    g = p.add_argument_group('반주')
    g.add_argument('--style', default=orch.DEFAULT_STYLE, choices=sorted(orch.STYLES),
                   help='편성 스타일 (기본: strings — 가장 안전)')
    g.add_argument('--level', default='rich', choices=list(orch.LEVELS),
                   help='반주 두께의 상한 (기본: rich)')
    g.add_argument('--curve', default='build',
                   help='연출 곡선: build(기본, off->simple->normal->rich) 또는 flat')
    g.add_argument('--bpm', type=float, default=96.0, help='템포 (기본: 96)')
    g.add_argument('--transpose', type=int, default=0, help='조옮김 (반음, -12~+12)')
    g.add_argument('--key', help="조성을 직접 지정 ('C' 장조 / 'a' 단조 / 'Bb' / 'f#'). "
                                 '짧고 성긴 악보에서 자동 판정이 흔들릴 때만 쓴다')
    g.add_argument('--count-in', type=int, default=0, metavar='N',
                   help='카운트인 N마디를 앞에 붙인다')
    g.add_argument('--seg-target', type=float, default=2.0,
                   help='세그먼트 목표 길이 (4분음표 단위, 기본 2박)')
    g.add_argument('--no-adaptive', action='store_true',
                   help='적응형 분할을 끄고 고정 분할만 쓴다')
    g.add_argument('--no-expand-repeats', action='store_true',
                   help='반복기호를 펼치지 않는다')

    o = p.add_argument_group('출력')
    o.add_argument('--all-formats', action='store_true',
                   help='연습용 192k + 무대용 320k + 영상편집용 WAV 전부')
    o.add_argument('--format', dest='formats', action='append',
                   choices=sorted(render.FORMATS), help='출력 형식 (여러 번 지정 가능)')
    o.add_argument('--stems', action='store_true',
                   help='파트별 스템(피아노/현악/저음) WAV 추가')
    o.add_argument('--keep-midi', action='store_true',
                   help='합친 MIDI 와 반주 MIDI 를 남긴다 (카탈로그 저장용)')

    a = p.add_argument_group('분석')
    a.add_argument('--analyze-only', action='store_true', help='화성만 출력하고 끝낸다')
    a.add_argument('--harmony-json', help='분석된 화성을 JSON 으로 저장')
    a.add_argument('--use-harmony', help='확인 화면에서 교정된 화성 JSON 을 쓴다')
    a.add_argument('--json', action='store_true', help='결과를 JSON 으로 출력')
    a.add_argument('--quiet', action='store_true', help='진행 메시지를 줄인다')

    p.add_argument('--styles', action='store_true', help='편성 스타일 목록')
    p.add_argument('--version', action='version', version=f'piano-mr {__version__}')
    return p


def print_styles() -> None:
    print('편성 스타일 7종 (지시서 5장 모듈 ③)\n')
    for key, lab, desc in orch.list_styles():
        roles = orch.resolve(key, 'rich')
        inst = ', '.join(f"{orch.ROLE_LABEL[r]}={v['label']}" for r, v in roles.items())
        print(f'  {key:<10} {lab}\n             {desc}\n             {inst}\n')
    print('레벨 3단계: ' + ' / '.join(
        f'{k}({orch.LEVEL_LABEL[k]})' for k in orch.LEVELS))


def print_harmony(segs, ls, low_conf_threshold: float = 0.15) -> None:
    print(f'조성: {ls.key}   박자: {ls.time_signature.ratioString}   '
          f'마디: {len(ls.bars)}   세그먼트: {len(segs)}')
    if ls.repeats_expanded:
        print('(반복기호를 펼쳐서 분석했습니다)')
    print()
    print(harmony.to_grid(segs))
    weak = harmony.low_confidence(segs, low_conf_threshold)
    if weak:
        print(f'\n확인 필요 {len(weak)}곳 (2위 후보와 점수 차가 작음 — '
              '화성 확인 화면에서 노란색이 될 구간):')
        for s in weak[:20]:
            alts = ' / '.join(harmony.label(a['root'], a['qual']) for a in s['alts'][:2])
            print(f"   m{s['m']}-{s['i'] + 1}  {s['label']:<4} "
                  f"(다음 후보: {alts or '—'})")
        if len(weak) > 20:
            print(f'   ... 외 {len(weak) - 20}곳')
    else:
        print('\n확신이 약한 구간 없음.')


def main(argv: Optional[List[str]] = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)

    if args.styles:
        print_styles()
        return 0
    if not args.score:
        p.print_help()
        return 2

    t0 = time.time()
    try:
        ls = score_loader.load(args.score,
                               expand_repeats=not args.no_expand_repeats,
                               transpose=args.transpose, key_name=args.key)
    except (FileNotFoundError, ValueError) as e:
        print(f'오류: {e}', file=sys.stderr)
        return 1

    if args.use_harmony:
        with open(args.use_harmony, encoding='utf-8') as f:
            segs = json.load(f)
        if isinstance(segs, dict):
            segs = segs['segments']
    else:
        segs = harmony.analyze_segments(ls, seg_target=args.seg_target,
                                        adaptive=not args.no_adaptive)

    if args.harmony_json:
        with open(args.harmony_json, 'w', encoding='utf-8') as f:
            json.dump({'key': str(ls.key), 'time': ls.time_signature.ratioString,
                       'measures': len(ls.bars), 'segments': segs},
                      f, ensure_ascii=False, indent=2)
        if not args.quiet:
            print(f'화성 JSON: {args.harmony_json}')

    if args.analyze_only:
        if args.json:
            print(json.dumps({'key': str(ls.key),
                              'time': ls.time_signature.ratioString,
                              'measures': len(ls.bars), 'segments': segs},
                             ensure_ascii=False))
        else:
            print_harmony(segs, ls)
            print(f'\n분석 {time.time() - t0:.2f}초')
        return 0

    tag = args.tag or os.path.splitext(os.path.basename(args.score))[0]
    formats = args.formats or (['practice', 'stage', 'master'] if args.all_formats
                               else ['practice'])

    try:
        res = render.render(ls, style=args.style, level=args.level, bpm=args.bpm,
                            curve=args.curve, tag=tag, out_dir=args.out_dir,
                            formats=formats, stems=args.stems,
                            keep_midi=args.keep_midi, count_in=args.count_in,
                            harmony_override=segs, outfile=args.out)
    except (render.ToolMissingError, ValueError, RuntimeError) as e:
        print(f'오류: {e}', file=sys.stderr)
        return 1

    elapsed = time.time() - t0
    res.info['elapsed_sec'] = round(elapsed, 2)
    if args.json:
        print(json.dumps(res.info, ensure_ascii=False))
        return 0

    if not args.quiet:
        print(f'{orch.describe(args.style, args.level)}')
        print(f'조성 {res.info["key"]} · 박자 {res.info["time"]} · '
              f'{res.info["bars"]}마디 · ♩={args.bpm:g}')
    for kind, path in res.files.items():
        lab = render.FORMATS.get(kind, {}).get('label', kind)
        size = os.path.getsize(path) / 1024
        print(f'  [{lab}] {path}  ({size:,.0f} KB)')
    for name, path in res.stems.items():
        print(f'  [스템·{name}] {path}')
    if args.keep_midi:
        print(f'  [반주 MIDI] {res.accomp_mid}  '
              f'({os.path.getsize(res.accomp_mid) / 1024:.1f} KB)')
    print(f'{elapsed:.2f}초')
    return 0
