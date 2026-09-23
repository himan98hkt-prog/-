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
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time  # noqa: E402

from piano_mr import (catalog as cat, harmony, orchestration as orch,  # noqa: E402
                      render, repertoire as rep, store, uploads)

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


def cmd_repertoire(st: store.CatalogStore, a) -> int:
    """콩쿨 레퍼토리 목록을 보거나, 악보가 있는 것을 한 번에 넣는다.

    `--scores` 없이 부르면 **아무것도 안 넣고** 현황만 말한다 — 무엇을 더 구해야
    하는지가 이 명령의 절반이다.
    """
    try:
        data = rep.load(a.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f'목록을 못 읽었습니다: {e}', file=sys.stderr)
        return 1

    works = data['works']
    if a.grade:
        works = [w for w in works if w.get('grade') == a.grade]
    if a.book:
        works = [w for w in works if a.book in (w.get('book') or '')]
    if not works:
        print('조건에 맞는 곡이 없습니다.')
        return 0

    ready, missing, blocked = rep.survey(works, a.scores or os.devnull)
    have = {s.id for s in st.catalog.songs.values()}

    print(f'{data["title"]} — {len(works)}곡')
    print(f'  이미 카탈로그에 있음 {sum(1 for w in works if w["id"] in have)}')
    print(f'  악보가 있어 넣을 수 있음 {len(ready)}')
    print(f'  악보를 더 구해야 함 {len(missing)}')
    if blocked:
        print(f'  저작권에 걸려 못 넣음 {len(blocked)}')

    if not a.scores:
        print()
        for w in missing:
            mark = '있음' if w['id'] in have else '없음'
            print(f'  [{mark}] {w["id"]:<26} {w.get("grade",""):<4} {w["title"]}')
        print()
        print('악보(MusicXML)를 한 폴더에 모으고 파일 이름을 위 id 로 맞춘 뒤')
        print(f'  python3 catalog_cli.py repertoire --scores <폴더>')
        print('판본 주의: 곡이 퍼블릭도메인이어도 **출판사 편집판에는 편집자의 권리가**')
        print('따로 붙을 수 있습니다. 원전판이나 직접 입력한 것을 쓰세요.')
        return 0

    added = failed = 0
    for w in ready:
        if w['id'] in have:
            continue
        try:
            song = st.import_score(
                w['path'], w['title'], song_id=w['id'], composer=w.get('composer', ''),
                book=w.get('book', ''), level=int(w.get('level', 5)),
                public_domain=True, default_style=w.get('style', orch.DEFAULT_STYLE),
                default_bpm=int(w.get('bpm', 96)), count_in=1,
                note=w.get('note', ''))
        except (cat.CopyrightError, FileNotFoundError, ValueError) as e:
            print(f'  ✗ {w["id"]:<26} {e}', file=sys.stderr)
            failed += 1
            continue
        added += 1
        print(f'  ✓ {song.id:<26} {song.key:<10} {song.measures:>3}마디 '
              f'확인필요 {song.low_confidence_count}')
    print(f'\n{added}곡 추가' + (f' · {failed}곡 실패' if failed else ''))
    for w in blocked:
        print(f'  ✗ {w["id"]}: {w["why"]}', file=sys.stderr)
    return 1 if failed else 0


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


# --- 4단계 PDF 업로드 (지시서 9장 4단계) ---------------------------------------

def cmd_uploads(st: store.CatalogStore, a) -> int:
    """신청제 운영자 화면. 지금 무엇을 처리해야 하는지 한눈에 (지시서 8.3 ③)."""
    v = st.uploads_view(a.account)
    q = v['quota']
    print(f"{q['month']}  {q['used']}/{q['limit']}쪽 사용 · "
          f"남은 몫 {q['remaining']}쪽 · 이번 달 {q['spent_won']:,}원 · 인식 {v['provider']}")
    if not v['jobs']:
        print('올라온 악보가 없습니다.')
        return 0
    print()
    for j in v['jobs']:
        mark = '★' if j['state'] == uploads.RUNNING else ' '
        print(f"{mark} {j['id']}  {j['label']:<8} {j['pages']}쪽  "
              f"{j['title'] or j['filename']}")
        if j['detail']:
            print(f"      {j['detail']}")
        if j['song_id']:
            print(f"      곡 {j['song_id']} — {j['verify_url']}")
    todo = [j for j in v['jobs'] if j['state'] == uploads.RUNNING]
    if todo:
        print(f"\n★ {len(todo)}건이 인식을 기다립니다. PDF 는 {st.incoming_dir} 에 있습니다.")
        print('   MusicXML 을 만들어 넣으세요:')
        print(f"   python3 catalog_cli.py --catalog {a.catalog} "
              f"deliver {todo[0]['id']} 결과.musicxml")
    return 0


def cmd_deliver(st: store.CatalogStore, a) -> int:
    """사람이 만든 MusicXML 을 그 작업에 붙인다 (신청제 납품)."""
    with open(a.musicxml, 'rb') as f:
        data = f.read()
    j = st.adopt_musicxml(a.job_id, data, song_id=a.id)
    print(f"{j['id']} → {j['label']} · 곡 {j['song_id']}")
    print(f"화성 확인 화면: {j['verify_url']}")
    print('OMR 은 90~95% 입니다 — 32마디에 2~6마디가 틀립니다 (지시서 2.2). '
          '확인 화면을 꼭 거치세요.')
    return 0


def cmd_poll(st: store.CatalogStore, a) -> int:
    """OMR 서비스에 끝났는지 물어본다."""
    ids = [a.job_id] if a.job_id else [
        j['id'] for j in st.ledger.rows(state=uploads.RUNNING)]
    if not ids:
        print('인식 중인 작업이 없습니다.')
        return 0
    for jid in ids:
        j = st.poll_upload(jid)
        print(f"{jid}  {j['label']}  {j['detail'] or ''}".rstrip())
    return 0


def cmd_sweep(st: store.CatalogStore, a) -> int:
    """오래 들고 있던 PDF 를 지운다 (지시서 7장 — 서버 영구 저장 금지)."""
    out = st.sweep(older_than_hours=a.hours)
    print(f"{a.hours}시간 넘은 작업 {len(out['swept'])}건 정리 · "
          f"주인 없는 파일 {out['orphans']}개 삭제 · 남은 PDF {out['held']}개")
    return 0


def cmd_limit(st: store.CatalogStore, a) -> int:
    """월 업로드 제한을 바꾼다 (지시서 8.3 ① — 변동비를 묶는 손잡이)."""
    if a.pages is not None:
        st.ledger.monthly_pages = int(a.pages)
        st.ledger.save()
    q = st.ledger.quota(a.account)
    print(f"월 {q['limit']}쪽 (쪽당 {q['won_per_page']}원 → 최대 "
          f"월 {q['limit'] * q['won_per_page']:,}원)")
    return 0


# --- 5단계 관리노트 연동 (지시서 9장 5단계) -----------------------------------

def cmd_roster(st: store.CatalogStore, a) -> int:
    """관리노트 명단을 받거나, 지금 들고 있는 명단을 보여 준다."""
    if a.file:
        with open(a.file, 'rb') as f:
            out = st.import_roster(f.read())
        print(f"{out['academy'] or '학원'} 명단 {out['count']}명을 받았습니다.")
        if out['added']:
            print(f"  새로 들어온 학생 {len(out['added'])}명")
        if out['removed']:
            print(f"  명단에서 빠진 학생 {len(out['removed'])}명 "
                  "(발표회 큐에 남아 있으면 이름이 그대로 보입니다)")
        return 0
    v = st.roster.view()
    if not v['count']:
        print('아직 명단을 받지 않았습니다.')
        print('  관리노트 → 설정 → 백업·복원·내보내기 → 「피아노 반주(MR) 연동」')
        print('  거기서 내려받은 파일을 이 명령에 넘기세요:')
        print(f'  python3 catalog_cli.py --catalog {a.catalog} roster 명단.json')
        return 0
    print(f"{v['academy'] or '학원'} · {v['count']}명 (재원 {v['active']}명) "
          f"· 받은 날 {v['imported_at'][:10]}")
    for s_ in v['students']:
        mark = ' ' if s_['active'] else '·'
        print(f"{mark} {s_['id']:<14} {s_['name']:<10} {s_['class']}")
    return 0


# --- 배포 꾸러미 -----------------------------------------------------------

def cmd_package(st: store.CatalogStore, a) -> int:
    """원장님 PC 에 파이썬 없이 올릴 수 있는 정적 꾸러미를 만든다."""
    styles = [x.strip() for x in (a.styles or '').split(',') if x.strip()]
    levels = [x.strip() for x in (a.levels or '').split(',') if x.strip()]
    for x in styles:
        orch.check_style(x)
    for x in levels:
        orch.check_level(x)
    out = st.export_static(a.out, styles=styles, levels=levels,
                           only_verified=a.verified_only, academy=a.academy)
    kb = out['total_bytes'] / 1024
    print(f"{out['out']}")
    print(f"  곡 {out['songs']}개 · 파일 {out['files']}개 · "
          f"전체 {kb:.0f} KB (반주 {out['midi_bytes'] / 1024:.0f} KB)")
    if styles:
        print(f"  편성 변형: {', '.join(styles)} × {', '.join(levels) or '기본 두께'}")
    print('  이 폴더를 통째로 웹호스팅에 올리면 됩니다. https 여야 오프라인이 켜집니다.')
    print('  악보 원본(scores/)과 렌더 캐시는 들어가지 않습니다.')
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

    rp = sub.add_parser('repertoire', help='콩쿨 레퍼토리 목록 보기 / 한 번에 넣기')
    rp.add_argument('--manifest', help='목록 파일 (기본: repertoire/competition.json)')
    rp.add_argument('--scores', help='MusicXML 이 모여 있는 폴더. 없으면 현황만 말한다')
    rp.add_argument('--grade', choices=['초급', '중급', '상급'])
    rp.add_argument('--book', help='교재 이름으로 거르기 (예: 부르크뮐러)')
    rp.set_defaults(fn=cmd_repertoire)

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

    # 4단계 PDF 업로드
    u = sub.add_parser('uploads', help='올라온 PDF 악보와 이번 달 몫')
    u.add_argument('--account', default='', help='이 계정 것만')
    u.set_defaults(fn=cmd_uploads)

    d = sub.add_parser('deliver', help='신청제 납품 — MusicXML 을 작업에 붙인다')
    d.add_argument('job_id')
    d.add_argument('musicxml')
    d.add_argument('--id', help='곡 id 를 직접 지정')
    d.set_defaults(fn=cmd_deliver)

    pl = sub.add_parser('poll', help='OMR 서비스에 끝났는지 물어본다')
    pl.add_argument('job_id', nargs='?', help='생략하면 인식 중인 것 전부')
    pl.set_defaults(fn=cmd_poll)

    sw = sub.add_parser('sweep', help='오래 들고 있던 PDF 삭제 (지시서 7장)')
    sw.add_argument('--hours', type=float, default=72.0)
    sw.set_defaults(fn=cmd_sweep)

    pk = sub.add_parser('package', help='원장님께 드릴 정적 꾸러미 만들기 (배포)')
    pk.add_argument('out', help='만들 폴더 (있으면 지우고 다시 만든다)')
    pk.add_argument('--styles', help='같이 구울 편성 (쉼표로, 예: chamber,march)')
    pk.add_argument('--levels', help='같이 구울 두께 (쉼표로, 예: simple,normal)')
    pk.add_argument('--verified-only', action='store_true',
                    help='화성 확인이 끝난 곡만')
    pk.add_argument('--academy', default='', help='꾸러미에 적을 학원명')
    pk.set_defaults(fn=cmd_package)

    ro = sub.add_parser('roster', help='관리노트 학생 명단 받기/보기 (5단계)')
    ro.add_argument('file', nargs='?', help='관리노트가 내보낸 명단 JSON')
    ro.set_defaults(fn=cmd_roster)

    lm = sub.add_parser('limit', help='월 업로드 제한 보기/바꾸기')
    lm.add_argument('pages', nargs='?', type=int, help='생략하면 현재 값만 본다')
    lm.add_argument('--account', default='')
    lm.set_defaults(fn=cmd_limit)
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    st = store.CatalogStore(a.catalog)
    return a.fn(st, a)


if __name__ == '__main__':
    raise SystemExit(main())
