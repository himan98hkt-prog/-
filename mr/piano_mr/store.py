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
               pdf, provenance as prov, render, roster, score_loader, uploads)

SCORE_SUFFIXES = score_loader.SUPPORTED_SUFFIXES

# 꾸러미를 받은 원장님이 제일 먼저 여는 파일. 기술 용어를 쓰지 않는다.
STATIC_README = """{academy} 반주 플레이어
{line}

곡 {songs}개 · 발표회 프로그램 {programs}개가 들어 있습니다.

■ 어떻게 쓰나요

1. 이 폴더를 통째로 홈페이지(웹호스팅)에 올립니다.
   - 관리노트를 올려 둔 그 자리에 나란히 올리면 됩니다.
   - **https 로 열려야 합니다.** http 로는 오프라인 기능이 켜지지 않습니다.

2. 태블릿·휴대폰에서 그 주소를 열고 「홈 화면에 추가」를 누릅니다.
   앱처럼 설치됩니다.

3. 첫 화면 오른쪽 위 ⤓ 를 한 번 누르면 전곡을 내려받습니다.
   **이 다음부터는 인터넷이 없어도 됩니다.** 연주홀 와이파이를 믿지 않아도 됩니다.

■ 무엇이 되나요

  · 곡을 고르고 반주를 재생 (원곡 피아노는 빠져 있습니다 — 피아노는 아이가 칩니다)
  · 템포·조옮김을 그 자리에서 바꾸기 (다시 받지 않습니다)
  · 반주 페이드아웃 — 아이가 멈췄을 때 3초 안에 반주만 사라집니다
  · 발표회 프로그램 순서대로 진행
  · 카운트인 (원장님 이어폰으로만 들리게도 됩니다 — 크롬에서)
  · 집 연습 링크 — 카톡으로 보내면 학부모님은 설치도 로그인도 없이 그대로 재생됩니다

■ 곡을 더 넣으려면

이 꾸러미는 만들어진 시점의 곡만 들어 있습니다. 곡이 추가되면 새 꾸러미를
받아 같은 자리에 덮어써 주세요. 태블릿에서 한 번 새로고침하면 최신으로 바뀝니다.

■ 안 될 때

  · 소리가 안 나요        → 화면을 한 번 눌러 보세요 (브라우저가 첫 소리를 막습니다)
  · 오프라인이 안 돼요     → 주소가 https 인지 확인해 주세요
  · 목록이 비어 있어요     → 새로고침 한 번. 그래도 비면 꾸러미가 덜 올라간 것입니다
"""


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
                     owner: str = '', score_source: str = '',
                     score_license: str = '',
                     time_name: Optional[str] = None) -> cat.Song:
        """악보 파일을 카탈로그로 들인다. 저작권 확인을 통과해야 들어온다.

        `public_domain` 은 **곡**이 만료됐는가고, `score_license` 는 **그 파일을
        쳐 넣은 사람**의 조건이다. 둘은 별개다 — 만료된 곡이어도 남의 입력본에는
        약정이 붙어 있을 수 있다 (`piano_mr/provenance.py`).
        """
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
        # 출처 키의 오타는 **여기서** 잡는다. 안 그러면 모르는 키가 조용히
        # 'unknown' 으로 떨어져, 팔 수 있는 악보가 이유도 없이 꾸러미에서 빠진다.
        if score_license and not prov.known(score_license):
            raise ValueError(
                f'모르는 입력본 출처입니다: {score_license!r} '
                f'(가능: {", ".join(sorted(prov.TERMS))})')

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
            time_locked=bool(time_name), time=time_name or '',
            owner=owner, source='upload' if owner else 'catalog',
            score_source=score_source, score_license=score_license)
        song.validate()
        self.catalog.songs[song_id] = song
        if analyze:
            self.analyze(song_id, key_name=key_name)
        self.save()
        return song

    # --- 분석 -------------------------------------------------------------
    def load_score(self, song_id: str) -> score_loader.LoadedScore:
        song = self.catalog.get(song_id)
        return score_loader.load(
            self.score_path(song_id),
            key_name=song.key if song.key_locked else None,
            time_name=song.time if song.time_locked else None)

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
        ls = score_loader.load(
            os.path.join(self.scores_dir, song.source_xml),
            key_name=song.key if song.key_locked else None,
            time_name=song.time if song.time_locked else None)
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

    # 내보내기는 캐시와 다른 일이다.
    #
    # `audio()` 는 **화면에서 바로 듣는** 것이라 결과를 캐시에 남긴다. 내보내기는
    # **가져가는** 것이라 안 남긴다 — 편성·두께·템포 조합마다 영상편집용 WAV 가
    # 쌓이면 원장님 디스크가 먼저 찬다. 부르는 쪽이 받아 가면 지운다.
    EXPORT_MIXES = ('mr', 'full', 'piano')

    def export(self, song_id: str, out_dir: str, *, formats: Sequence[str],
               style: Optional[str] = None, level: Optional[str] = None,
               bpm: Optional[int] = None, mix: str = render.DEFAULT_MIX,
               count_in: Optional[int] = None, stems: bool = False) -> dict:
        """고른 형식들로 한 번에 굽는다. **사람이 고친 화성이 그대로 들어간다.**

        화성 확인 화면에서 칸을 고쳐 놓고 내보냈는데 기계가 처음 분석한 화성이
        나가면, 그 화면에서 쓴 시간이 통째로 버려진다.
        """
        if not formats:
            raise ValueError('내보낼 형식을 하나는 고르셔야 합니다.')
        song = self.catalog.get(song_id)
        style = orch.check_style(style or song.default_style)
        level = orch.check_level(level or song.default_level)
        bpm = int(bpm or song.default_bpm)
        count_in = song.count_in if count_in is None else int(count_in)
        if mix not in render.MIXES:
            raise ValueError(f"모르는 mix 입니다: {mix} (가능: {', '.join(render.MIXES)})")

        res = render.render(self.load_score(song_id), style=style, level=level,
                            bpm=bpm, curve=song.default_curve, count_in=count_in,
                            tag=self.export_tag(song, style, level, bpm, mix),
                            out_dir=out_dir, formats=tuple(formats), stems=stems,
                            mix=mix, harmony_override=self._segments(song))
        return {'files': dict(res.files), 'stems': dict(res.stems),
                'style': style, 'level': level, 'bpm': bpm, 'mix': mix,
                'count_in': count_in, 'seconds': res.info.get('seconds')}

    @staticmethod
    def export_tag(song, style: str, level: str, bpm: int, mix: str) -> str:
        """파일 이름. 원장님이 폴더에서 보고 무엇인지 알 수 있어야 한다.

        `작은 왈츠 (C장조) — 동화풍 보통 96 반주만` 처럼 나간다. 한글을 그대로
        쓰되 폴더 구분자와 따옴표만 뺀다 — 윈도·맥 양쪽에서 열려야 한다.
        """
        mix_label = {'mr': '반주만', 'full': '피아노+반주', 'piano': '피아노만'}
        raw = (f'{song.title} — {orch.STYLES[style]["label"]} '
               f'{orch.LEVEL_LABEL.get(level, level)} {bpm} {mix_label.get(mix, mix)}')
        bad = '/\\:*?"<>|\n\r\t'
        return ''.join(' ' if c in bad else c for c in raw).strip() or song.id

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
    @staticmethod
    def _chord_track(song: cat.Song) -> list:
        """[[박, '화음'], …] — 화음이 **바뀌는 지점만**.

        박은 4분음표 기준 절대 위치다. 플레이어 엔진이 `beatsPerBar =
        분자 × 4/분모` 로 세므로 같은 자로 재야 눈금이 안 어긋난다.
        """
        try:
            num, den = (int(x) for x in (song.time or '4/4').split('/'))
            per_bar = num * (4 / den)
        except (ValueError, ZeroDivisionError):
            per_bar = 4.0

        track, last = [], None
        for h in song.harmony:
            name = harmony.label(h.get('root'), h.get('qual'))
            if name == last:
                continue
            bar = h.get('bar', h.get('m', 1)) or 1
            beat = (bar - 1) * per_bar + float(h.get('off', 0.0))
            track.append([round(beat, 3), name])
            last = name
        return track

    def song_row(self, song: cat.Song,
                 variants: Optional[Sequence] = None) -> dict:
        """플레이어가 받아 가는 곡 한 줄.

        `variants` 는 **정적 배포**에서만 채운다. 서버가 있으면 어떤 편성이든 그
        자리에서 구우므로 목록이 필요 없지만, 정적 호스트는 미리 구워 둔 것밖에
        못 준다. 그런데 정적 호스트는 쿼리스트링을 무시하기 때문에, 없는 편성을
        골라도 **같은 파일이 조용히 돌아온다** — 화면엔 「실내악」인데 스피커에서는
        기본 편성이 나오는, 3단계에서 오프라인에 대해 고쳤던 바로 그 버그다.
        그래서 꾸러미에 실제로 들어 있는 편성을 알려 주고 화면이 그것만 보여 준다.
        """
        row = {'id': song.id, 'title': song.title, 'composer': song.composer,
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
        # 지금 울리는 화음을 화면에 띄우려고 싣는다.
        #
        # 이 제품이 파는 것은 **화성을 정확히 읽는 것**이다(99.5%). 그게 화면에
        # 안 보이면 원장님에게는 그냥 반주가 나오는 프로그램이다. 무대에서도
        # 쓸모가 있다 — 아이가 멈췄을 때 몇 마디 몇 화음인지 바로 보인다.
        #
        # 바뀌는 지점만 싣는다. 같은 화음이 이어지는 마디가 많아 26곡에 17KB 다.
        row['chords'] = self._chord_track(song)
        if variants is not None:
            row['variants'] = [{'style': st, 'level': lv, 'url': url}
                               for st, lv, url in variants]
        return row

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

    # --- 배포 꾸러미 (원장님 PC 에는 파이썬이 없다) --------------------------
    def export_static(self, out_dir: str, *, styles: Sequence[str] = (),
                      levels: Sequence[str] = (), only_verified: bool = False,
                      academy: str = '', for_sale: bool = True) -> dict:
        """플레이어를 **서버 없이 도는 정적 파일 한 벌**로 내보낸다.

        원장님 PC 에 파이썬·fluidsynth·SoundFont 를 깔게 할 수는 없다. 그런데
        플레이어가 런타임에 부르는 건 곡 목록과 반주 MIDI 둘뿐이고, 둘 다 그냥
        파일이다 (지시서 8.4 — "MIDI 를 클라이언트에 내려주고 브라우저에서 재생하면
        서버 렌더링조차 불필요하다"). 그래서 앱이 부르는 **그 경로 그대로** 파일을
        깔아 두면 코드를 한 줄도 안 고치고 정적 호스트에서 돈다.

        카탈로그 제작 서버(화성 확인·PDF 업로드)는 우리 쪽 도구로 남는다.
        `scores/` 와 `cache/` 는 꾸러미에 들어가지 않는다 — 원장님께 필요 없고,
        악보 원본을 재배포하는 모양이 되어서도 안 된다 (지시서 7장).

        **`for_sale` 이 기본값 True 인 이유.** 이 꾸러미는 파는 물건이다. 입력본
        출처가 확인 안 된 악보(`unknown`)나 비영리 조건이 붙은 악보로 만든 반주가
        섞여 들어가면 **파는 순간 문제가 된다.** 그래서 기본은 빼는 쪽이고, 뺀
        것은 결과에 `dropped` 로 알려 준다. 원장님이 **자기 학원에서만** 쓰실
        거라면 `for_sale=False` 로 전부 담는다 (`piano_mr/provenance.py`).
        """
        out_dir = os.path.abspath(out_dir)
        player_src = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'server', 'static', 'player')
        if not os.path.isdir(player_src):
            raise FileNotFoundError(f'플레이어 파일을 못 찾았습니다: {player_src}')
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        shutil.copytree(player_src, out_dir)

        # 주소를 상대경로로 돌린다. 원장님은 도메인 루트에 올릴 수도, `/반주/` 같은
        # 하위 폴더에 올릴 수도 있다. 절대경로면 하위 폴더에서 전부 404 가 된다.
        index = os.path.join(out_dir, 'index.html')
        with open(index, encoding='utf-8') as f:
            html = f.read()
        if 'data-api="/"' not in html:
            raise ValueError('index.html 에 data-api="/" 가 없습니다 — '
                             '정적 배포에서 주소를 상대경로로 못 돌립니다.')
        with open(index, 'w', encoding='utf-8') as f:
            f.write(html.replace('data-api="/"', 'data-api="./"'))

        midi_dir = os.path.join(out_dir, 'api', 'player', 'midi')
        os.makedirs(midi_dir, exist_ok=True)

        songs = [s for s in self.catalog.songs.values()
                 if s.harmony_verified or not only_verified]

        # 파는 꾸러미면 입력본 출처를 본다. 곡이 만료됐는지(`public_domain`)와는
        # 다른 질문이다 — 위 설명 참고.
        dropped: List[dict] = []
        if for_sale:
            songs, blocked = prov.split(songs)
            dropped = [{'id': s.id, 'title': s.title, 'source': s.score_source,
                        'license': prov.term(s.score_license).label}
                       for s in sorted(blocked, key=lambda x: x.id)]

        songs.sort(key=lambda x: (x.book, x.level, x.id))

        rows, total = [], 0
        for song in songs:
            wanted = [(song.default_style, song.default_level)]
            for st in styles:
                for lv in (levels or [song.default_level]):
                    if (st, lv) not in wanted:
                        wanted.append((st, lv))
            made = []
            for st, lv in wanted:
                data = self.accomp_midi_bytes(song.id, style=st, level=lv)
                default = (st, lv) == (song.default_style, song.default_level)
                name = song.id if default else f'{song.id}__{st}_{lv}'
                with open(os.path.join(midi_dir, name), 'wb') as f:
                    f.write(data)
                total += len(data)
                made.append((st, lv, f'api/player/midi/{name}'))
            rows.append(self.song_row(song, variants=made))

        bundle = {
            'version': 2,
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'static': True,            # 서버가 없다 — 화면이 이걸 보고 판단한다
            'academy': academy or self.roster.academy,
            'songs': rows,
            'assignments': [asdict(a) for a in self.catalog.assignments],
            'programs': self.programs(),
        }
        bundle_path = os.path.join(out_dir, 'api', 'player', 'bundle')
        with open(bundle_path, 'w', encoding='utf-8') as f:
            json.dump(bundle, f, ensure_ascii=False)

        readme = os.path.join(out_dir, '읽어보세요.txt')
        with open(readme, 'w', encoding='utf-8') as f:
            name = bundle['academy'] or '학원'
            f.write(STATIC_README.format(
                academy=name, line='=' * (len(name) * 2 + 16),
                songs=len(rows), programs=len(bundle['programs'])))

        return {'out': out_dir, 'songs': len(rows),
                'files': sum(len(fs) for _, _, fs in os.walk(out_dir)),
                'midi_bytes': total,
                'for_sale': for_sale,
                'dropped': dropped,
                # 팔 수는 있지만 조건이 붙는 것들 (예: 동일조건변경허락)
                'cautions': [r for r in prov.summary(songs) if r['caution']],
                'total_bytes': sum(os.path.getsize(os.path.join(r, n))
                                   for r, _, fs in os.walk(out_dir) for n in fs)}
