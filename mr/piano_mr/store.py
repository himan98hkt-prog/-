# -*- coding: utf-8 -*-
"""카탈로그 저장소 — 지시서 9장 2단계.

디스크 배치:

    catalog/
      catalog.json          곡 메타 + 확정된 화성 + 검수 상태
      scores/<id>.musicxml  원본 악보
      midi/<id>.mid         반주 MIDI (2.4 KB)
      cache/<key>.mp3       렌더 캐시 — 언제든 지워도 되는 파생물

**오디오는 카탈로그가 아니다** (지시서 6장). `cache/` 는 확인 화면이 소리를 내기
위한 임시 파생물이고, 지워도 2.2초면 다시 만들어진다. 백업·배포 대상은
`catalog.json` + `scores/` + `midi/` 뿐이다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from urllib.parse import quote
from dataclasses import asdict

from typing import Dict, List, Optional, Sequence

from . import (arranger, catalog as cat, harmony, omr, orchestration as orch,
               pdf, render, roster, score_loader, uploads)

SCORE_SUFFIXES = score_loader.SUPPORTED_SUFFIXES


def slugify(text: str) -> str:
    """제목 -> 곡 id 후보. 쓸 만한 게 안 나오면 빈 문자열.

    한글 제목은 ASCII 로 남는 게 숫자뿐이라 '체르니 100번 5번' -> '100_5' 같은
    쓰레기 id 가 나온다. 곡 id 는 한 번 정하면 배정·발표회 큐가 물고 가는
    영구 식별자다. 엉뚱한 걸 지어내느니 사람에게 물어보는 편이 낫다.
    """
    t = re.sub(r'[^a-z0-9]+', '_', (text or '').lower()).strip('_')
    if len(t) < 2 or not re.search(r'[a-z]', t):
        return ''
    return t


class CatalogStore:
    """카탈로그 한 벌을 디렉터리 하나로 다룬다."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.scores_dir = os.path.join(self.root, 'scores')
        self.midi_dir = os.path.join(self.root, 'midi')
        self.cache_dir = os.path.join(self.root, 'cache')
        self.json_path = os.path.join(self.root, 'catalog.json')
        for d in (self.root, self.scores_dir, self.midi_dir, self.cache_dir):
            os.makedirs(d, exist_ok=True)
        self.catalog = (cat.Catalog.load(self.json_path)
                        if os.path.exists(self.json_path) else cat.Catalog(self.root))

    # --- 경로 ------------------------------------------------------------
    def score_path(self, song_id: str) -> str:
        song = self.catalog.get(song_id)
        return os.path.join(self.scores_dir, song.source_xml)

    def midi_path(self, song_id: str) -> str:
        return os.path.join(self.midi_dir, f'{song_id}.mid')

    def save(self) -> str:
        return self.catalog.save(self.json_path)

    # --- 곡 넣기 ----------------------------------------------------------
    def import_score(self, path: str, title: str, *, song_id: Optional[str] = None,
                     composer: str = '', book: str = '', level: int = 1,
                     public_domain: bool = False, default_style: str = orch.DEFAULT_STYLE,
                     default_level: str = 'normal', default_bpm: int = 96,
                     key_name: Optional[str] = None, recommended_bpm: Sequence[int] = (),
                     default_curve: str = 'flat', count_in: int = 0,
                     note: str = '', analyze: bool = True,
                     owner: str = '') -> cat.Song:
        """악보 파일을 카탈로그로 들인다. 저작권 확인을 통과해야 들어온다."""
        if not os.path.exists(path):
            raise FileNotFoundError(f'악보 파일이 없습니다: {path}')
        song_id = song_id or slugify(title)
        if not song_id:
            raise ValueError(
                f'제목 {title!r} 에서 쓸 만한 곡 id 를 못 만들었습니다. '
                "--id 로 직접 지정하세요 (예: --id czerny100_05).")
        # id 검사를 파일 복사보다 먼저 한다 — id 가 그대로 파일명이 되므로
        # 여기서 막지 않으면 scores/ 밖으로 쓰는 경로가 만들어질 수 있다.
        if not re.fullmatch(r'[a-z0-9_\-]+', song_id):
            raise ValueError(f'곡 id 는 소문자·숫자·_- 만 씁니다: {song_id!r}')
        if song_id in self.catalog.songs:
            raise ValueError(f'이미 있는 곡 id 입니다: {song_id}')

        # 파일을 복사하기 전에 저작권부터 본다 (지시서 7장)
        cat.check_copyright(title, composer, book,
                            public_domain=public_domain, owner=owner)

        suffix = os.path.splitext(path)[1].lower()
        if suffix not in SCORE_SUFFIXES:
            raise ValueError(f'지원하지 않는 악보 형식입니다: {suffix}')
        stored = f'{song_id}{suffix}'
        shutil.copyfile(path, os.path.join(self.scores_dir, stored))

        song = cat.Song(
            id=song_id, title=title, composer=composer, book=book, level=level,
            public_domain=public_domain, source_xml=stored,
            default_style=default_style, default_level=default_level,
            default_curve=default_curve, default_bpm=default_bpm,
            count_in=int(count_in), recommended_bpm=list(recommended_bpm),
            key_locked=bool(key_name), key=key_name or '', note=note,
            owner=owner, source='upload' if owner else 'catalog')
        song.validate()
        self.catalog.songs[song_id] = song
        if analyze:
            self.analyze(song_id, key_name=key_name)
        self.save()
        return song

    # --- 분석 -------------------------------------------------------------
    def load_score(self, song_id: str) -> score_loader.LoadedScore:
        song = self.catalog.get(song_id)
        return score_loader.load(self.score_path(song_id),
                                 key_name=song.key if song.key_locked else None)

    def analyze(self, song_id: str, key_name: Optional[str] = None) -> cat.Song:
        """엔진을 돌려 화성 초안을 만든다. 사람이 확인한 값은 덮지 않는다."""
        song = self.catalog.get(song_id)
        if song.harmony_verified:
            raise ValueError(f'{song_id}: 이미 사람이 확인한 화성입니다. '
                             'reanalyze() 로 명시적으로 다시 분석하세요.')
        return self._analyze(song, key_name)

    def reanalyze(self, song_id: str, key_name: Optional[str] = None) -> cat.Song:
        """확인 여부와 상관없이 다시 분석한다 (엔진을 고친 뒤 등)."""
        song = self.catalog.get(song_id)
        song.harmony_verified = False
        return self._analyze(song, key_name)

    def _analyze(self, song: cat.Song, key_name: Optional[str]) -> cat.Song:
        if key_name:
            song.key = key_name
            song.key_locked = True
        ls = score_loader.load(os.path.join(self.scores_dir, song.source_xml),
                               key_name=song.key if song.key_locked else None)
        segs = harmony.analyze_segments(ls)
        song.key = str(ls.key)
        song.time = ls.time_signature.ratioString
        song.measures = len(ls.bars)
        song.harmony = [cat.segment_record(s) for s in segs]
        self.save()
        return song

    # --- 확인 화면이 읽는 모양 --------------------------------------------
    def view(self, song_id: str) -> dict:
        """지시서 10장 화면이 그대로 그릴 수 있는 구조.

        음표는 보내지 않는다. **화음 이름만** 보면 3~5분, 음표까지 보면 40분이다.
        """
        song = self.catalog.get(song_id)
        bars: List[dict] = []
        by_bar: Dict[int, List[dict]] = {}
        for h in song.harmony:
            by_bar.setdefault(h.get('bar', h['m']), []).append(h)
        for bar_idx in sorted(by_bar):
            cells = []
            for h in sorted(by_bar[bar_idx], key=lambda x: x['i']):
                label = harmony.label(h['root'], h['qual'])
                cells.append({
                    'i': h['i'], 'label': label,
                    'conf': round(float(h.get('conf', 1.0)), 3),
                    'low': float(h.get('conf', 1.0)) < cat.LOW_CONF,
                    'alts': h.get('alts', []),
                    'auto': h.get('auto', label),
                    'changed': h.get('auto', label) != label,
                    'off': h.get('off', 0.0), 'len': h.get('len', 0.0),
                })
            first = by_bar[bar_idx][0]
            bars.append({'bar': bar_idx, 'm': first['m'],
                         'off': first.get('off', 0.0),
                         'end': max(c['off'] + c['len'] for c in cells),
                         'cells': cells})
        return {
            'id': song.id, 'title': song.title, 'composer': song.composer,
            'book': song.book, 'level': song.level, 'note': song.note,
            'key': song.key, 'key_label': cat.key_label(song.key),
            'key_locked': song.key_locked, 'time': song.time,
            'measures': song.measures, 'status': song.status,
            'verified': song.harmony_verified, 'verify_seconds': song.verify_seconds,
            'style': song.default_style, 'level_name': song.default_level,
            'bpm': song.default_bpm, 'recommended_bpm': song.recommended_bpm,
            'bars': bars,
            'low_count': sum(1 for b in bars for c in b['cells'] if c['low']),
            'choices': self.choices(song),
        }

    def choices(self, song: cat.Song) -> dict:
        """드롭다운 후보. 조성의 화음이 먼저, 그 외 전체가 뒤에."""
        from music21 import key as m21key
        try:
            k = m21key.Key(song.key.split()[0]) if song.key else m21key.Key('C')
            if song.key.endswith('minor'):
                k = m21key.Key(song.key.split()[0].lower())
        except Exception:
            k = m21key.Key('C')
        inkey = [harmony.label(r, q) for r, q in harmony.key_candidates(k)]
        every = [harmony.label(r, q) for q in ('M', 'm', 'd', '7') for r in range(12)]
        return {'in_key': list(dict.fromkeys(inkey)),
                'all': [x for x in dict.fromkeys(every) if x not in inkey]}

    # --- 확인 결과 저장 -----------------------------------------------------
    def save_harmony(self, song_id: str, cells: Sequence[dict], *,
                     verified: Optional[bool] = None, add_seconds: int = 0,
                     style: Optional[str] = None, level: Optional[str] = None,
                     bpm: Optional[int] = None, note: Optional[str] = None) -> cat.Song:
        """확인 화면에서 넘어온 교정을 반영한다.

        cells: `[{'m':1,'i':0,'label':'G7'}, ...]` — 바뀐 칸만 보내도 된다.
        """
        song = self.catalog.get(song_id)
        if cells:
            self.catalog.apply_corrections(song_id, list(cells), verified=False)
        if style is not None:
            song.default_style = orch.check_style(style)
        if level is not None:
            song.default_level = orch.check_level(level)
        if bpm is not None:
            song.default_bpm = int(bpm)
        if note is not None:
            song.note = note
        if add_seconds:
            song.verify_seconds += max(0, int(add_seconds))
        if verified is not None:
            song.harmony_verified = bool(verified)
            song.verified_at = (time.strftime('%Y-%m-%dT%H:%M:%S')
                                if verified else '')
        song.validate()
        self.save()
        return song

    # --- 소리 --------------------------------------------------------------
    def _segments(self, song: cat.Song) -> List[dict]:
        """저장된 화성을 편곡기가 먹는 모양으로."""
        return [{'bar': h.get('bar', h['m']), 'm': h['m'], 'i': h['i'],
                 'off': h.get('off', 0.0), 'len': h.get('len', 0.0),
                 'root': h['root'], 'qual': h['qual'],
                 'label': harmony.label(h['root'], h['qual'])}
                for h in song.harmony]

    def render_key(self, song: cat.Song, style: str, level: str, bpm: int,
                   mix: str) -> str:
        blob = json.dumps([[h['m'], h['i'], h['root'], h['qual']] for h in song.harmony])
        raw = f'{song.id}|{style}|{level}|{bpm}|{mix}|{blob}'
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    def audio(self, song_id: str, *, style: Optional[str] = None,
              level: Optional[str] = None, bpm: Optional[int] = None,
              mix: str = render.DEFAULT_MIX, count_in: Optional[int] = None,
              force: bool = False) -> dict:
        """음원을 만든다 (캐시 적중이면 즉시).

        화음을 하나 바꾸면 키가 달라지므로 자동으로 다시 렌더된다 — 지시서 10장의
        "바꾸면 즉시 반주 재생성".

        mix 기본값은 `mr`(반주만)이다. 다만 **화성 확인 화면은 `full` 로 부른다** —
        선율 없이 화음만 들어서는 그 화음이 이 곡에 맞는지 판단할 수 없기 때문이다.
        """
        song = self.catalog.get(song_id)
        style = orch.check_style(style or song.default_style)
        level = orch.check_level(level or song.default_level)
        bpm = int(bpm or song.default_bpm)
        if mix not in render.MIXES:
            raise ValueError(f"모르는 mix 입니다: {mix} (가능: {', '.join(render.MIXES)})")
        curve = song.default_curve
        count_in = song.count_in if count_in is None else int(count_in)
        key = self.render_key(song, style, level, bpm, f'{mix}|{curve}|{count_in}')
        path = os.path.join(self.cache_dir, f'{song.id}_{key}.mp3')
        hit = os.path.exists(path) and not force
        t0 = time.time()
        if not hit:
            res = render.render(self.load_score(song_id), style=style, level=level,
                                bpm=bpm, curve=curve, count_in=count_in,
                                tag=f'{song.id}_{key}', out_dir=self.cache_dir,
                                formats=('practice',), keep_midi=False, mix=mix,
                                harmony_override=self._segments(song),
                                outfile=path)
            if not os.path.exists(path):          # 안전망
                path = res.first()
        # 카운트인을 구워 넣으면 곡이 그만큼 뒤로 밀린다. 구간 재생이 이걸 모르면
        # 마디를 눌렀을 때 엉뚱한 자리가 나온다.
        lead_ql = (self.bar_length(song_id) * count_in) if count_in else 0.0
        return {'path': path, 'cached': hit, 'seconds': round(time.time() - t0, 2),
                'style': style, 'level': level, 'bpm': bpm, 'mix': mix,
                'curve': curve, 'count_in': count_in,
                'lead_seconds': round(lead_ql * 60.0 / bpm, 4),
                'ql_per_second': bpm / 60.0}

    def bar_length(self, song_id: str) -> float:
        """첫 마디의 길이 (4분음표 단위). 카운트인 길이 계산에 쓴다."""
        ls = self.load_score(song_id)
        return ls.bars[0].bar_length if ls.bars else 4.0

    def build_midi(self, song_id: str, *, style: Optional[str] = None,
                   level: Optional[str] = None, bpm: Optional[int] = None,
                   variant: bool = False) -> str:
        """카탈로그에 보관할 반주 MIDI 를 굽는다. 저장하는 건 이것뿐이다.

        `variant=True` 면 기본 설정이 아니라 편성별 파일로 따로 남긴다.
        MIDI 는 1 KB 안팎이라 스타일을 여러 벌 구워 둬도 부담이 없고,
        템포는 재생할 때 바꾸면 되므로 bpm 별로는 굽지 않는다 (지시서 8.4).
        """
        song = self.catalog.get(song_id)
        style = orch.check_style(style or song.default_style)
        level = orch.check_level(level or song.default_level)
        arr, _ls, _segs = arranger.arrange(
            self.load_score(song_id), style=style, level=level,
            curve=song.default_curve, bpm=int(bpm or song.default_bpm),
            harmony_override=self._segments(song))
        out = (self.variant_path(song_id, style, level) if variant
               else self.midi_path(song_id))
        arr.save(out)
        if not variant:
            song.accomp_midi = os.path.relpath(out, self.root)
            self.save()
        return out

    def variant_path(self, song_id: str, style: str, level: str) -> str:
        return os.path.join(self.midi_dir, f'{song_id}__{style}_{level}.mid')

    def prebuild(self, song_id: str, *, styles: Sequence[str] = (),
                 levels: Sequence[str] = (), audio: bool = False,
                 mix: str = render.DEFAULT_MIX,
                 count_in: Optional[int] = None) -> dict:
        """미리 만들어 둘 수 있는 것을 다 만든다.

        기본 설정 반주 MIDI 는 항상. 편성 변형을 요청하면 그것도. `audio=True` 면
        MR mp3 까지 캐시에 구워 둔다 — 현장에서 기다리지 않게.
        """
        made = {'midi': self.build_midi(song_id), 'variants': [], 'audio': None}
        song = self.catalog.get(song_id)
        for st in styles:
            for lv in (levels or [song.default_level]):
                made['variants'].append(self.build_midi(song_id, style=st, level=lv,
                                                        variant=True))
        if audio:
            made['audio'] = self.audio(song_id, mix=mix, count_in=count_in)['path']
        return made

    def clear_cache(self) -> int:
        n = 0
        for f in os.listdir(self.cache_dir):
            os.remove(os.path.join(self.cache_dir, f))
            n += 1
        return n

    # --- 현황 --------------------------------------------------------------
    def stats(self) -> dict:
        songs = list(self.catalog.songs.values())
        verified = [s for s in songs if s.harmony_verified]
        times = [s.verify_seconds for s in verified if s.verify_seconds > 0]
        midi_kb = sum(os.path.getsize(os.path.join(self.midi_dir, f))
                      for f in os.listdir(self.midi_dir)
                      if f.endswith('.mid')) / 1024
        return {
            'total': len(songs),
            'verified': len(verified),
            'analyzed': sum(1 for s in songs if s.status == 'analyzed'),
            'new': sum(1 for s in songs if s.status == 'new'),
            'low_confidence_cells': sum(s.low_confidence_count for s in songs),
            'avg_verify_seconds': round(sum(times) / len(times)) if times else 0,
            'over_20min': sum(1 for t in times if t > 20 * 60),
            'midi_kb': round(midi_kb, 1),
            'midi_files': sum(1 for f in os.listdir(self.midi_dir)
                              if f.endswith('.mid')),
            'prebuilt': sum(1 for s in songs
                            if os.path.exists(self.midi_path(s.id))),
            'cached_audio': sum(1 for f in os.listdir(self.cache_dir)
                                if f.endswith('.mp3')),
        }

    def rows(self) -> List[dict]:
        out = []
        for s in sorted(self.catalog.songs.values(), key=lambda x: (x.book, x.level, x.id)):
            out.append({'id': s.id, 'title': s.title, 'composer': s.composer,
                        'book': s.book, 'level': s.level, 'key': s.key,
                        'key_label': cat.key_label(s.key), 'time': s.time,
                        'measures': s.measures, 'status': s.status,
                        'low': s.low_confidence_count,
                        'verify_seconds': s.verify_seconds,
                        'style': s.default_style, 'bpm': s.default_bpm})
        return out

    # --- 발표회 프로그램 (지시서 모듈 ⑤-3) ---------------------------------
    def programs(self) -> List[dict]:
        return [self.program_view(i) for i in range(len(self.catalog.programs))]

    def program_view(self, index: int) -> dict:
        """운영 화면이 그대로 그릴 수 있는 프로그램 한 벌.

        큐의 각 줄에 곡 제목까지 붙여 준다. 원장님 화면에서 song_id 를 보여 줄 수는
        없기 때문이다.
        """
        if not 0 <= index < len(self.catalog.programs):
            raise KeyError(f'없는 프로그램입니다: {index}')
        p = self.catalog.programs[index]
        items = []
        for q in p.sorted_queue():
            song = self.catalog.songs.get(q.song_id)
            # 이름은 명단에서 찾아 쓴다 — 관리노트에서 개명하면 여기도 따라 바뀐다.
            # 명단이 없거나 그 학생이 빠졌으면 저장해 둔 이름을 그대로 (화면이 비면 안 된다).
            who = self.roster.name_of(q.student_id, q.student) if q.student_id \
                else q.student
            items.append({
                'order': q.order, 'student': who, 'song_id': q.song_id,
                'student_id': q.student_id,
                'linked': bool(q.student_id and self.roster.get(q.student_id)),
                'title': song.title if song else q.song_id,
                'composer': song.composer if song else '',
                'book': song.book if song else '',
                'measures': song.measures if song else 0,
                'missing': song is None,
                'verified': bool(song and song.harmony_verified),
                'bpm': q.bpm, 'style': q.style, 'level': q.level, 'note': q.note,
                'style_label': orch.STYLES[q.style]['label'],
                'level_label': orch.LEVEL_LABEL[q.level],
                'count_in': song.count_in if song else 0,
                'cue': f"{q.order}. {who} — {song.title if song else q.song_id} "
                       f"(♩={q.bpm}, {orch.STYLES[q.style]['label']}, "
                       f"{orch.LEVEL_LABEL[q.level]})",
            })
        return {'index': index, 'id': p.id, 'event': p.event, 'date': p.date,
                'venue': p.venue, 'count': len(items),
                'minutes': p.minutes, 'items': items,
                'ready': all(i['verified'] for i in items) if items else False}

    # --- 3단계 플레이어 ------------------------------------------------
    def song_row(self, song: cat.Song) -> dict:
        return {'id': song.id, 'title': song.title, 'composer': song.composer,
                'book': song.book, 'level': song.level, 'key': song.key,
                'key_label': cat.key_label(song.key),
                'time': song.time, 'measures': song.measures,
                'style': song.default_style, 'level_name': song.default_level,
                'bpm': song.default_bpm, 'count_in': song.count_in,
                'recommended_bpm': song.recommended_bpm,
                'verified': song.harmony_verified,
                # 플레이어가 받아 가는 주소와, 카탈로그 안의 파일 위치.
                # 이름 하나가 상황 따라 다른 뜻이 되면 나중에 꼭 틀린다.
                'midi': f'/api/player/midi/{song.id}',
                'midi_file': song.accomp_midi or None}

    def player_bundle(self, only_verified: bool = False) -> dict:
        """플레이어가 통째로 받아 오프라인에 넣어 둘 목록.

        오디오는 들어가지 않는다. 곡마다 반주 MIDI 주소 하나뿐이고 그건 1 KB 다.
        mp3 였다면 한 곡에 600 KB — 카탈로그를 오프라인에 담을 수 없다 (⑤-1).
        """
        songs = [s for s in self.catalog.songs.values()
                 if s.harmony_verified or not only_verified]
        return {
            'version': 2,
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'songs': [self.song_row(s) for s in
                      sorted(songs, key=lambda x: (x.book, x.level, x.id))],
            'assignments': [asdict(a) for a in self.catalog.assignments],
            'programs': self.programs(),
        }

    def accomp_midi_bytes(self, song_id: str, *, style: Optional[str] = None,
                          level: Optional[str] = None) -> bytes:
        """반주 MIDI 를 돌려준다. 없으면 그 자리에서 굽는다."""
        song = self.catalog.get(song_id)
        style = orch.check_style(style or song.default_style)
        level = orch.check_level(level or song.default_level)
        variant = (style != song.default_style or level != song.default_level)
        path = (self.variant_path(song_id, style, level) if variant
                else self.midi_path(song_id))
        if not os.path.exists(path):
            self.build_midi(song_id, style=style, level=level, variant=variant)
        with open(path, 'rb') as f:
            return f.read()

    def export_player(self, out_path: str) -> str:
        """플레이어 번들을 파일로. 확인된 곡만, 오디오 없이."""
        data = self.player_bundle(only_verified=True)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return out_path

    # --- 4단계 PDF 업로드 (지시서 9장 4단계 · 7장 · 8.2) ----------------------
    @property
    def incoming_dir(self) -> str:
        """올라온 PDF 를 **잠깐만** 두는 격리 폴더.

        지시서 7장: "서버 영구 저장·재배포 금지". 그래서 이 폴더는 카탈로그가 아니고,
        MusicXML 이 나오는 순간 비운다. `sweep()` 이 방치된 것도 쓸어낸다.
        """
        d = os.path.join(self.root, 'incoming')
        os.makedirs(d, exist_ok=True)
        return d

    @property
    def roster(self) -> 'roster.Roster':
        """관리노트에서 받아 온 학생 명단 (지시서 9장 5단계)."""
        if getattr(self, '_roster', None) is None:
            self._roster = roster.Roster(os.path.join(self.root, 'roster.json'))
        return self._roster

    def import_roster(self, data) -> dict:
        return self.roster.replace_with(data)

    @property
    def ledger(self) -> 'uploads.UploadLedger':
        if getattr(self, '_ledger', None) is None:
            self._ledger = uploads.UploadLedger(
                os.path.join(self.root, 'uploads.json'))
        return self._ledger

    def _pdf_path(self, job_id: str) -> str:
        return os.path.join(self.incoming_dir, f'{job_id}.pdf')

    def _drop_pdf(self, job) -> bool:
        """격리 폴더의 PDF 를 지운다. 지웠으면 True."""
        path = self._pdf_path(job.id)
        existed = os.path.exists(path)
        if existed:
            os.remove(path)
        if job.pdf_kept or existed:
            self.ledger.update(job.id, pdf_kept=False)
        return existed

    def submit_pdf(self, data: bytes, filename: str, *, account: str,
                   title: str = '', provider=None) -> dict:
        """PDF 를 받아 OMR 작업을 연다.

        순서가 중요하다. **저작권 → 형식 → 쿼터 → 그 다음에야 디스크**.
        돈이 나가거나 파일이 남는 일은 전부 검사 뒤에 온다.
        """
        title = (title or os.path.splitext(os.path.basename(filename))[0]).strip()
        # ① 저작권 — 파일이 디스크에 닿기 전에 (지시서 7장)
        cat.check_copyright(title, filename, owner=account or '_')
        if not account:
            raise ValueError('업로드는 계정이 있어야 합니다 (지시서 7장 — 계정 전용).')
        if len(data) > uploads.MAX_BYTES:
            raise ValueError(
                f'파일이 너무 큽니다 ({len(data) // 1024 // 1024} MB). '
                f'{uploads.MAX_BYTES // 1024 // 1024} MB 까지 받습니다.')
        # ② 진짜 PDF 인가, 몇 쪽인가 (쪽수가 과금 단위 — 지시서 8.2)
        info = pdf.inspect(data)
        if not info.countable:
            raise ValueError(
                '페이지 수를 읽을 수 없는 PDF 입니다. 다른 뷰어에서 '
                '다시 저장한 뒤 올려 주세요 — 몇 쪽인지 알아야 접수됩니다.')
        # ③ 쿼터 (지시서 9장 4단계 "월 업로드 제한")
        prov = provider or omr.make_provider()
        job = self.ledger.add(account=account, filename=filename,
                              pages=info.pages, provider=prov.name, title=title)
        # ④ 여기서 처음으로 디스크에 쓴다
        with open(self._pdf_path(job.id), 'wb') as f:
            f.write(data)
        self.ledger.update(job.id, pdf_kept=True,
                           pdf_at=time.strftime('%Y-%m-%dT%H:%M:%S'))
        try:
            ref = prov.submit(data, filename)
        except omr.OmrError as e:
            self._drop_pdf(job)
            self.ledger.update(job.id, state=uploads.FAILED, detail=str(e))
            raise
        self.ledger.update(job.id, state=uploads.RUNNING, job_ref=ref)
        return self.job_view(job.id)

    def poll_upload(self, job_id: str, provider=None) -> dict:
        """OMR 이 끝났는지 보고, 끝났으면 카탈로그로 들인다."""
        job = self.ledger.get(job_id)
        if job.state != uploads.RUNNING:
            return self.job_view(job_id)
        prov = provider or omr.make_provider(job.provider or None)
        try:
            result = prov.poll(job.job_ref)
        except omr.OmrError as e:
            self.ledger.update(job_id, detail=str(e))
            return self.job_view(job_id)
        if result.state == omr.FAILED:
            self._drop_pdf(job)
            self.ledger.update(job_id, state=uploads.FAILED, detail=result.detail)
            return self.job_view(job_id)
        if result.state != omr.READY:
            self.ledger.update(job_id, detail=result.detail)
            return self.job_view(job_id)
        xml = result.musicxml
        if xml is None:
            xml = prov.fetch(job.job_ref)
        return self.adopt_musicxml(job_id, xml)

    def adopt_musicxml(self, job_id: str, musicxml: bytes,
                       *, song_id: Optional[str] = None) -> dict:
        """OMR 결과(또는 사람이 만든 MusicXML)를 카탈로그로 들인다.

        여기가 지시서 7장의 핵심이다 — **MusicXML 이 들어오는 순간 PDF 를 지운다.**
        들어간 곡은 계정 전용이라 `owner` 를 달고 나간다.
        """
        job = self.ledger.get(job_id)
        if job.state in (uploads.DONE, uploads.CANCELLED):
            raise ValueError(f'이미 {job.label} 상태인 작업입니다.')
        sid = song_id or slugify(job.title) or f'upload_{job.id}'
        tmp = os.path.join(self.incoming_dir, f'{job.id}.musicxml')
        with open(tmp, 'wb') as f:
            f.write(musicxml)
        try:
            self.import_score(tmp, job.title or job.filename, song_id=sid,
                              owner=job.account, note=f'PDF 업로드 {job.filename}')
        except Exception as e:
            self.ledger.update(job_id, state=uploads.FAILED, detail=str(e))
            self._drop_pdf(job)
            raise
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        # 악보가 들어왔으니 PDF 는 더 들고 있을 이유가 없다 (지시서 7장)
        self._drop_pdf(job)
        self.ledger.update(job_id, state=uploads.REVIEW, song_id=sid, detail='')
        return self.job_view(job_id)

    def finish_upload(self, job_id: str) -> dict:
        """화성 확인까지 끝났다고 표시한다."""
        job = self.ledger.get(job_id)
        if not job.song_id:
            raise ValueError('아직 악보가 들어오지 않은 작업입니다.')
        if not self.catalog.get(job.song_id).harmony_verified:
            raise ValueError(
                '화성 확인이 아직 안 끝났습니다. OMR 은 90~95% 라서 '
                '32마디에 2~6마디가 틀립니다 (지시서 2.2) — 확인 화면을 거쳐야 합니다.')
        self.ledger.update(job_id, state=uploads.DONE)
        return self.job_view(job_id)

    def cancel_upload(self, job_id: str) -> dict:
        job = self.ledger.get(job_id)
        if job.state in uploads.CLOSED_STATES:
            raise ValueError(f'이미 {job.label} 상태입니다.')
        self._drop_pdf(job)
        self.ledger.update(job_id, state=uploads.CANCELLED)
        return self.job_view(job_id)

    def sweep(self, older_than_hours: float = 72.0) -> dict:
        """방치된 작업의 PDF 를 쓸어낸다 (지시서 7장 — 영구 보관 금지).

        원장에 없는 고아 파일도 같이 지운다. 작업이 지워졌는데 PDF 만 남는 경우다.
        """
        gone = []
        for job in self.ledger.stale(older_than_hours):
            self._drop_pdf(job)
            if job.open:
                self.ledger.update(job.id, state=uploads.FAILED,
                                   detail='시간이 지나 접수가 취소됐습니다.')
            gone.append(job.id)
        orphans = 0
        known = {f'{j}.pdf' for j in self.ledger.jobs}
        for name in os.listdir(self.incoming_dir):
            if name.endswith('.pdf') and name not in known:
                os.remove(os.path.join(self.incoming_dir, name))
                orphans += 1
        return {'swept': gone, 'orphans': orphans,
                'held': len([j for j in self.ledger.jobs.values() if j.pdf_kept])}

    def job_view(self, job_id: str) -> dict:
        job = self.ledger.get(job_id)
        d = job.view()
        d['verified'] = (bool(job.song_id) and job.song_id in self.catalog.songs
                         and self.catalog.get(job.song_id).harmony_verified)
        # 화성 확인 화면의 진짜 주소. 목록 페이지로 보내면 원장님이 곡을 다시 찾아야 한다.
        d['verify_url'] = (f'/static/verify.html?id={quote(job.song_id)}'
                           if job.song_id else '')
        return d

    def uploads_view(self, account: str = '') -> dict:
        return {'quota': self.ledger.quota(account),
                'jobs': [self.job_view(r['id']) for r in self.ledger.rows(account)],
                'provider': omr.make_provider().name,
                # 지시서 3장: "'PDF 넣으면 바로 완성'을 약속하지 말 것"
                'accuracy_note': ('악보 인식은 90~95% 입니다. 32마디 기준 2~6마디가 '
                                  '틀리므로 화성 확인 화면을 꼭 거쳐야 합니다.')}
