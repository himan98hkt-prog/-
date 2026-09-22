# -*- coding: utf-8 -*-
"""데이터 모델 — 곡(catalog) / 배정(assignment) / 발표회 프로그램(queue).

지시서 6장 그대로. 저장 원칙은 하나다:

    **오디오를 저장하지 않는다.** MIDI(2.4 KB) + 설정만 저장하고 요청 시 렌더한다.
    100곡 × 10개 버전 기준 26 GB -> 2 MB.

7장(저작권)이 "위반 시 사업 전체가 무너짐"이라고 못 박았기 때문에
카탈로그에 넣는 순간 화이트/블랙리스트를 강제로 확인한다. 편곡은 2차적저작물이고,
비영리 예외는 판매 제품에 적용되지 않는다.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence

from . import harmony, orchestration as orch

# --- 지시서 7장 -------------------------------------------------------------
WHITELIST_HINTS = (
    '바이엘', 'beyer', '체르니', 'czerny', '하농', 'hanon',
    '부르크뮐러', 'burgmuller', 'burgmüller', '소나티네', 'sonatine', 'sonatina',
    '클레멘티', 'clementi', '쿨라우', 'kuhlau', '디아벨리', 'diabelli',
    '모차르트', 'mozart', '하이든', 'haydn', '바흐', 'bach',
    '미뉴에트', 'minuet', '인벤션', 'invention', '안나 막달레나', 'anna magdalena',
    '슈만', 'schumann', '어린이 정경', 'kinderszenen',
    '차이콥스키', 'tchaikovsky', '어린이 앨범', 'children',
    '오리지널', 'original', '자사',
)
BLACKLIST = (
    '바스티앙', 'bastien', '알프레드', 'alfred',
    '피아노 어드벤처', 'piano adventures', 'faber',
    '이루마', 'yiruma', '지브리', 'ghibli', '히사이시', 'hisaishi',
    '디즈니', 'disney', 'ost', 'k-pop', 'kpop', '뉴에이지',
)


LOW_CONF = 0.15          # 이보다 확신이 약하면 확인 화면에서 노란색 (지시서 10장)


# music21 은 조성을 'E- major' / 'f# minor' 처럼 쓴다. 원장님 화면에 그대로 내보내면
# 「E- major」 가 뜬다 — 학원에서 쓰는 말은 「E♭장조」다.
_KEY_RE = re.compile(r'^([A-Ga-g])([#b\-]*)\s+(major|minor)$')
_ACCIDENTAL = {'': '', '#': '♯', 'b': '♭', '-': '♭',
               '##': '𝄪', 'bb': '♭♭', '--': '♭♭'}


def key_label(name: Optional[str]) -> str:
    """'E- major' → 'E♭장조'. 못 알아보면 원문 그대로 돌려준다."""
    if not name:
        return ''
    m = _KEY_RE.match(name.strip())
    if not m:
        return name
    letter, acc, mode = m.groups()
    sign = _ACCIDENTAL.get(acc.replace('-', 'b'), acc)
    return f'{letter.upper()}{sign}{"장조" if mode == "major" else "단조"}'


def segment_record(seg: dict) -> dict:
    """분석 세그먼트 -> 카탈로그에 저장할 화성 레코드.

    `conf`/`alts` 를 같이 남긴다. 확인 화면이 노란색을 칠하고 드롭다운의
    다음 후보를 보여주는 근거이고, 사람이 고친 뒤에도 "원래 뭐였는지"가 남는다.
    """
    return {
        'm': seg['m'], 'i': seg['i'],
        'bar': seg.get('bar', seg['m']),
        'off': seg.get('off', 0.0), 'len': seg.get('len', 0.0),
        'root': seg['root'], 'qual': seg['qual'],
        'conf': seg.get('conf', 1.0),
        'alts': [harmony.label(a['root'], a['qual']) for a in seg.get('alts', [])],
        'auto': harmony.label(seg['root'], seg['qual']),   # 엔진이 처음 낸 값
    }


class CopyrightError(ValueError):
    """화이트리스트 밖의 곡을 카탈로그에 넣으려 할 때."""


def check_copyright(*texts: Optional[str], public_domain: bool = False,
                    owner: str = '') -> None:
    """블랙리스트 문구가 있으면 거부. 카탈로그 곡은 퍼블릭도메인이어야 한다.

    `owner` 가 있으면 **그 계정이 올린 악보**다 (지시서 7장). 이 경우 퍼블릭도메인을
    요구하지 않는다 — 약관으로 생성 책임이 사용자에게 귀속되기 때문이다. 대신
    카탈로그로 팔 수 없고, 그 계정에서만 쓴다.

    **블랙리스트는 어느 경로든 예외가 없다.** 지시서 7장이 "절대 금지"라고 적었고,
    약관으로도 면책되지 않는 쪽이다.
    """
    blob = ' '.join(t for t in texts if t).lower()
    for bad in BLACKLIST:
        if bad in blob:
            raise CopyrightError(
                f'저작권 블랙리스트에 걸렸습니다: {bad!r} — 지시서 7장. '
                '편곡은 2차적저작물이라 작곡가·출판사와 직접 계약이 필요합니다.')
    if owner:
        return
    if not public_domain:
        raise CopyrightError(
            'public_domain=True 가 아닌 곡은 카탈로그에 넣을 수 없습니다 (지시서 7장). '
            '사용자가 올린 악보는 카탈로그가 아니라 해당 계정 전용으로 두세요.')


def looks_whitelisted(*texts: Optional[str]) -> bool:
    blob = ' '.join(t for t in texts if t).lower()
    return any(h in blob for h in WHITELIST_HINTS)


# --- 곡 ---------------------------------------------------------------------

@dataclass
class Song:
    id: str
    title: str
    composer: str = ''
    book: str = ''
    level: int = 1                       # 1~10 학원 기준 난이도
    public_domain: bool = False
    source_xml: str = ''
    key: str = ''
    time: str = ''
    measures: int = 0
    harmony: List[dict] = field(default_factory=list)
    harmony_verified: bool = False       # 사람이 화성 확인 화면에서 확인했는가
    default_style: str = orch.DEFAULT_STYLE
    recommended_bpm: List[int] = field(default_factory=list)
    accomp_midi: str = ''                # 반주 MIDI 경로 (오디오는 저장하지 않는다)

    # --- 2단계 카탈로그 제작 관리용 -------------------------------------
    default_level: str = 'normal'
    default_curve: str = 'flat'   # flat=곡 전체에 깔린다 / build=발표회용
    default_bpm: int = 96
    count_in: int = 0             # 음원에 구워 넣을 카운트인 마디 수
    # 지시서 7장 "업로드본은 해당 계정에서만 사용".
    # 빈 값 = 우리가 넣은 카탈로그 곡(퍼블릭도메인이어야 한다).
    # 값이 있으면 = 그 계정이 올린 악보. 카탈로그로 팔 수 없다.
    owner: str = ''
    source: str = ''                     # 'catalog' | 'upload'
    key_locked: bool = False             # 조성을 사람이 확정했는가 (자동 판정 무시)
    verify_seconds: int = 0              # 화성 확인 화면에서 실제로 쓴 시간
    verified_at: str = ''
    note: str = ''

    @property
    def status(self) -> str:
        if self.harmony_verified:
            return 'verified'
        return 'analyzed' if self.harmony else 'new'

    @property
    def low_confidence_count(self) -> int:
        return sum(1 for h in self.harmony if h.get('conf', 1.0) < LOW_CONF)

    def validate(self) -> None:
        orch.check_level(self.default_level)
        if self.default_curve not in ('flat', 'build') and \
                self.default_curve not in orch.LEVELS:
            raise ValueError(f'모르는 연출 곡선입니다: {self.default_curve!r}')
        if not 0 <= int(self.count_in) <= 8:
            raise ValueError('count_in 은 0~8 마디입니다.')
        if not 20 <= int(self.default_bpm) <= 240:
            raise ValueError('default_bpm 은 20~240 입니다.')
        if not self.id or not re.fullmatch(r'[a-z0-9_\-]+', self.id):
            raise ValueError(f'곡 id 는 소문자·숫자·_- 만 씁니다: {self.id!r}')
        if not self.title:
            raise ValueError('곡 제목이 비어 있습니다.')
        if not 1 <= int(self.level) <= 10:
            raise ValueError('level 은 1~10 입니다.')
        orch.check_style(self.default_style)
        check_copyright(self.title, self.composer, self.book,
                        public_domain=self.public_domain, owner=self.owner)

    def harmony_labels(self) -> List[str]:
        return [harmony.label(h.get('root'), h.get('qual')) for h in self.harmony]

    @classmethod
    def from_analysis(cls, song_id: str, title: str, ls, segs: Sequence[dict], **kw):
        """분석 결과로 곡 레코드를 만든다. harmony 는 확인 화면에서 교정될 초안."""
        s = cls(id=song_id, title=title,
                key=str(ls.key), time=ls.time_signature.ratioString,
                measures=len(ls.bars),
                harmony=[segment_record(x) for x in segs],
                **kw)
        return s


# --- 배정 (학생별) -----------------------------------------------------------

@dataclass
class Assignment:
    student_id: str
    song_id: str
    bpm: int = 84
    style: str = orch.DEFAULT_STYLE
    level: str = 'normal'
    transpose: int = 0
    volume: float = 0.7
    use_accompaniment: bool = True       # 박자 불안한 저학년은 False

    def validate(self) -> None:
        if not self.student_id or not self.song_id:
            raise ValueError('student_id 와 song_id 는 필수입니다.')
        if not 20 <= int(self.bpm) <= 240:
            raise ValueError('bpm 은 20~240 입니다.')
        if not -12 <= int(self.transpose) <= 12:
            raise ValueError('transpose 는 -12~+12 반음입니다.')
        if not 0.0 <= float(self.volume) <= 1.0:
            raise ValueError('volume 은 0.0~1.0 입니다.')
        orch.check_style(self.style)
        orch.check_level(self.level)


# --- 발표회 프로그램 (큐) -----------------------------------------------------

@dataclass
class QueueItem:
    order: int
    student: str
    song_id: str
    bpm: int = 84
    style: str = orch.DEFAULT_STYLE
    level: str = 'normal'
    note: str = ''

    def validate(self) -> None:
        if int(self.order) < 1:
            raise ValueError('order 는 1부터입니다.')
        orch.check_style(self.style)
        orch.check_level(self.level)


@dataclass
class Program:
    event: str
    date: str = ''
    id: str = ''
    venue: str = ''
    queue: List[QueueItem] = field(default_factory=list)

    def validate(self) -> None:
        if not self.event:
            raise ValueError('event 이름이 비어 있습니다.')
        if self.id and not re.fullmatch(r'[a-z0-9_\-]+', self.id):
            raise ValueError(f'프로그램 id 는 소문자·숫자·_- 만 씁니다: {self.id!r}')
        seen = set()
        for q in self.queue:
            q.validate()
            if q.order in seen:
                raise ValueError(f'순서가 겹칩니다: {q.order}')
            seen.add(q.order)

    def sorted_queue(self) -> List[QueueItem]:
        return sorted(self.queue, key=lambda q: q.order)

    def cue_lines(self) -> List[str]:
        """원장님 화면에 뜨는 큐 목록 — `1. 김지우 — 아라베스크 (♩=84, 실내악, 보통)`"""
        out = []
        for q in self.sorted_queue():
            style = orch.STYLES[q.style]['label']
            out.append(f"{q.order}. {q.student} — {q.song_id} "
                       f"(♩={q.bpm}, {style}, {orch.LEVEL_LABEL[q.level]})")
        return out

    @property
    def minutes(self) -> int:
        """대략의 진행 시간(분). 곡 길이를 모르니 곡당 3분으로 잡는다."""
        return len(self.queue) * 3


# --- 저장소 ------------------------------------------------------------------

class Catalog:
    """곡·배정·프로그램을 JSON 한 벌로 보관한다. 오디오는 절대 넣지 않는다."""

    def __init__(self, root: str):
        self.root = root
        self.songs: Dict[str, Song] = {}
        self.assignments: List[Assignment] = []
        self.programs: List[Program] = []

    # 곡
    def add(self, song: Song, allow_unverified: bool = True) -> Song:
        song.validate()
        if not allow_unverified and not song.harmony_verified:
            raise ValueError(f'{song.id}: 화성 확인 전에는 카탈로그에 넣지 않습니다.')
        self.songs[song.id] = song
        return song

    def get(self, song_id: str) -> Song:
        if song_id not in self.songs:
            raise KeyError(f'카탈로그에 없는 곡입니다: {song_id}')
        return self.songs[song_id]

    def assign(self, a: Assignment) -> Assignment:
        a.validate()
        self.get(a.song_id)
        self.assignments = [x for x in self.assignments
                            if not (x.student_id == a.student_id and x.song_id == a.song_id)]
        self.assignments.append(a)
        return a

    def add_program(self, p: Program) -> Program:
        p.validate()
        for q in p.queue:
            self.get(q.song_id)
        self.programs.append(p)
        return p

    # 화성 교정 (확인 화면에서 넘어온 값)
    def apply_corrections(self, song_id: str, corrections: Sequence[dict],
                          verified: bool = True) -> Song:
        """`[{'bar':1,'i':0,'label':'G7'}, ...]` 를 곡의 화성에 반영한다.

        `bar`(연주 순서)로 찍으면 그 한 칸만, `m`(인쇄된 마디 번호)으로 찍으면
        같은 번호의 칸 전부에 적용한다. 반복기호를 펼친 곡은 같은 `m` 이
        여러 번 나오기 때문에 이 구분이 필요하다.
        """
        song = self.get(song_id)
        by_bar: Dict[tuple, dict] = {}
        by_m: Dict[tuple, List[dict]] = {}
        for h in song.harmony:
            by_bar[(h.get('bar', h['m']), h['i'])] = h
            by_m.setdefault((h['m'], h['i']), []).append(h)

        for c in corrections:
            if 'bar' in c:
                hit = by_bar.get((c['bar'], c['i']))
                targets = [hit] if hit else []
                where = f'bar={c["bar"]}, i={c["i"]}'
            else:
                targets = by_m.get((c['m'], c['i']), [])
                where = f'm={c["m"]}, i={c["i"]}'
            if not targets:
                raise KeyError(f'{song_id}: 없는 세그먼트입니다 ({where})')
            if 'label' in c:
                parsed = harmony.parse_label(c['label'])
                if parsed is None:
                    raise ValueError(f'화음 이름을 알아볼 수 없습니다: {c["label"]!r}')
                root, qual = parsed
            else:
                root, qual = c['root'], c['qual']
            for h in targets:
                h['root'], h['qual'] = root, qual
        song.harmony_verified = verified
        return song

    # 직렬화
    def to_dict(self) -> dict:
        return {
            'version': 1,
            'songs': [asdict(s) for s in self.songs.values()],
            'assignments': [asdict(a) for a in self.assignments],
            'programs': [{'event': p.event, 'date': p.date, 'id': p.id,
                          'venue': p.venue,
                          'queue': [asdict(q) for q in p.queue]} for p in self.programs],
        }

    def save(self, path: Optional[str] = None) -> str:
        path = path or os.path.join(self.root, 'catalog.json')
        os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> 'Catalog':
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        c = cls(os.path.dirname(os.path.abspath(path)))
        for s in data.get('songs', []):
            c.songs[s['id']] = Song(**s)
        for a in data.get('assignments', []):
            c.assignments.append(Assignment(**a))
        for p in data.get('programs', []):
            c.programs.append(Program(
                event=p['event'], date=p.get('date', ''), id=p.get('id', ''),
                venue=p.get('venue', ''),
                queue=[QueueItem(**q) for q in p.get('queue', [])]))
        return c

    def storage_note(self) -> str:
        n = len(self.songs)
        midi_kb = n * 2.4
        wav_mb = n * 5.56 * 10
        return (f'곡 {n}개 · 반주 MIDI {midi_kb:.1f} KB 보관 '
                f'(같은 곡을 WAV 10버전으로 저장했다면 {wav_mb:.0f} MB)')
