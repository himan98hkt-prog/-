"""§6.1 참고 악보 라이브러리 + §7.8 검색.

원장이 올린 콩쿨 명곡·교재가 스타일 프로필로 쌓이고, 요청마다 비슷한 곡을 찾아
Stage 0 컨텍스트에 주입한다 — 이것이 "자기 코퍼스 축적" 차별점의 실체다.

저작권 정책(절대 규칙 3)은 여기서 지켜진다.
- `copyrighted` 곡: StyleProfile(통계)만 저장하고 **음표열은 저장하지 않는다**.
- `public_domain`/`own`: 음표열을 저장하되 프롬프트에는 8마디까지만 나간다.

검색은 지금 코사인 유사도다. pgvector 로 옮길 때 `StyleProfile.vector()` 를 그대로
임베딩 칼럼에 넣고 이 모듈의 `search()` 만 SQL 로 바꾸면 된다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.analysis.ngram import DEFAULT_N, interval_ngrams
from app.analysis.style_profile import StyleProfile, cosine, extract
from app.generation.copyright_guard import CopyrightStatus, CorpusEntry
from app.schemas.music import Measure

log = logging.getLogger(__name__)

# 검색 결과 상한(§7.8: 상위 10 → 난이도 ±2 필터 → 상위 5)
SEARCH_POOL = 10
SEARCH_TOP = 5
DIFFICULTY_WINDOW = 2.0


@dataclass
class CorpusScore:
    id: str
    title: str
    composer: str
    copyright_status: CopyrightStatus
    era: str = ""
    source: str = ""
    division_tags: list[str] = field(default_factory=list)
    teacher_difficulty: float | None = None    # 원장이 매긴 1~10 (난이도 보정용)
    profile: StyleProfile = field(default_factory=StyleProfile)
    # 저작권곡은 항상 None 이다. 코드가 그렇게 강제한다.
    measures: list[Measure] | None = None
    needs_review: bool = False
    # 이 곡을 우리가 만들었는가. 만든 곡은 **표절 인덱스에는 들어가되**
    # 스타일 검색에서는 빠진다 — 자기가 만든 곡을 참고해 또 만들면 곡이 서로 닮는다.
    generated: bool = False

    @property
    def difficulty(self) -> float:
        return self.profile.difficulty_score

    def to_entry(self) -> CorpusEntry:
        """저작권 가드가 이해하는 형태로. 발췌 허용 여부는 가드가 상태로 판단한다."""
        return CorpusEntry(
            id=self.id,
            title=self.title,
            composer=self.composer,
            copyright_status=self.copyright_status,
            style_profile=self.profile.as_dict(),
            excerpt_measures=(
                [m.model_dump() for m in self.measures[:8]] if self.measures else None
            ),
        )

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "composer": self.composer,
            "copyright_status": self.copyright_status, "era": self.era,
            "division_tags": self.division_tags,
            "difficulty": self.difficulty,
            "teacher_difficulty": self.teacher_difficulty,
            "measures": self.profile.measures,
            "key": self.profile.key, "meter": self.profile.meter, "tempo": self.profile.tempo,
            "has_notes": self.measures is not None,
            "needs_review": self.needs_review,
            "generated": self.generated,
        }


class Corpus:
    """인메모리 코퍼스. PostgreSQL+pgvector 로 옮길 때의 경계면이다."""

    def __init__(self) -> None:
        self.scores: dict[str, CorpusScore] = {}
        self._ngrams: dict[str, set[tuple[int, ...]]] = {}

    # ── 적재 ─────────────────────────────────────────────────────────────
    def add(
        self,
        measures: list[Measure],
        *,
        score_id: str,
        title: str,
        composer: str = "",
        copyright_status: CopyrightStatus = "public_domain",
        key: str = "C",
        meter: str = "4/4",
        tempo: int = 100,
        era: str = "",
        source: str = "",
        division_tags: list[str] | None = None,
        teacher_difficulty: float | None = None,
        needs_review: bool = False,
        generated: bool = False,
    ) -> CorpusScore:
        profile = extract(measures, key=key, meter=meter, tempo=tempo)
        entry = CorpusScore(
            id=score_id, title=title, composer=composer,
            copyright_status=copyright_status, era=era, source=source,
            division_tags=division_tags or [], teacher_difficulty=teacher_difficulty,
            profile=profile,
            # 저작권곡의 음표열은 애초에 보관하지 않는다 — 새어나갈 경로를 없앤다.
            measures=None if copyright_status == "copyrighted" else list(measures),
            needs_review=needs_review,
            generated=generated,
        )
        self.scores[score_id] = entry
        # 표절 검사용 n-gram 은 저작권 상태와 무관하게 만든다(음표열을 밖으로 내보내지
        # 않으면서 "베끼지 않았는지" 는 검사해야 하기 때문이다).
        self._ngrams[score_id] = set(interval_ngrams(measures, DEFAULT_N))
        log.info("코퍼스 등록: %s (%s) 난이도 %.1f", title, copyright_status, profile.difficulty_score)
        return entry

    def add_pdf_stats(
        self,
        path: str | Path,
        *,
        score_id: str,
        title: str = "",
        composer: str = "",
        copyright_status: CopyrightStatus = "copyrighted",
        era: str = "",
        source: str = "",
        division_tags: list[str] | None = None,
        teacher_difficulty: float | None = None,
    ) -> CorpusScore:
        """PDF 악보를 **통계만** 담아 넣는다. 음표열은 없다.

        원장님 악보는 대부분 PDF 인데, PDF 는 그림이라 음표를 알 수 없다. 그렇다고
        아무것도 못 받으면 "참고 악보"라는 기능 자체가 원장님께는 없는 기능이 된다.

        그래서 확실한 것만 받는다 — 몇 쪽인지, 제목과 작곡가, 글자로 찍힌 박자·빠르기·
        마디 번호. 이것만으로도 "이 급수의 곡은 대략 몇 마디에 어느 빠르기인가" 는
        배운다. 표절 검사(n-gram)에는 넣지 않는다 — 음표가 없으니 넣을 것이 없다.

        **모르는 값은 지어내지 않는다.** 못 찾으면 기본값이 그대로 남고, 화면이
        그 사실을 함께 보여 준다. 참고 자료에 거짓이 섞이면 없느니만 못하다.
        """
        from app.ingest.pdf_stats import read_pdf_stats

        st = read_pdf_stats(path)
        if st.pages <= 0:
            # 쪽 수조차 못 읽었다면 알아낸 것이 하나도 없다. 그런 줄을 목록에
            # 넣어 봐야 원장님 화면에 '—' 만 늘어선 칸이 생길 뿐이다.
            raise ValueError(
                "PDF 를 읽지 못했습니다 — 파일이 손상됐거나 PDF 가 아닐 수 있습니다"
                + (f" ({st.notes[0]})" if st.notes else "")
            )
        # **못 찾은 값은 기본값으로 메우지 않는다.**
        # StyleProfile 의 기본값은 C장조·4/4·♩=100·난이도 1.0 인데, 그대로 두면
        # 화면이 그것을 **알아낸 사실처럼** 보여 준다. 스캔한 악보를 올렸는데
        # "C 4/4 · 난이도 1.0" 이라고 뜨면 원장님은 그게 사실인 줄 아신다 —
        # 지어내지 않겠다는 약속이 표시 단계에서 깨지는 것이다. 비워 둔다.
        profile = StyleProfile(
            key="",
            meter=st.meter,
            tempo=st.tempo,
            measures=st.measures,
            difficulty_score=0.0,      # 0 = 모른다. 음표가 없으니 잴 수가 없다.
        )
        entry = CorpusScore(
            id=score_id,
            title=title or st.title or Path(path).stem,
            composer=composer or st.composer,
            copyright_status=copyright_status, era=era, source=source,
            division_tags=division_tags or [], teacher_difficulty=teacher_difficulty,
            profile=profile,
            measures=None,          # PDF 에서는 음표를 읽지 않는다
            # 사람이 한 번 봐 줘야 한다 — 글자에서 짐작한 값이기 때문이다.
            needs_review=True,
        )
        self.scores[score_id] = entry
        log.info("PDF 통계 적재 %s: %s", score_id, " / ".join(st.notes))
        return entry

    def add_file(self, path: str | Path, **kwargs: Any) -> CorpusScore:
        from app.ingest.parse import parse_score

        measures, meta = parse_score(path)
        kwargs.setdefault("title", str(meta["title"]))
        kwargs.setdefault("composer", str(meta["composer"]))
        kwargs.setdefault("key", str(meta["key"]))
        kwargs.setdefault("meter", str(meta["meter"]))
        kwargs.setdefault("tempo", int(str(meta["tempo"])))
        return self.add(measures, **kwargs)

    def register_generated(
        self,
        measures: list[Measure],
        *,
        score_id: str,
        title: str,
        key: str = "C",
        meter: str = "4/4",
        tempo: int = 100,
        division_tags: list[str] | None = None,
    ) -> CorpusScore:
        """우리가 만든 곡을 표절 인덱스에 등록한다.

        이걸 하지 않으면 다음 곡을 쓸 때 **이전에 만든 곡을 한 번도 보지 않는다** —
        같은 학원이 같은 콩쿨에 거의 같은 곡을 두 개 내보내도 검증기가 통과시킨다.
        스타일 검색에서는 빠진다(`generated=True`).
        """
        return self.add(
            measures,
            score_id=score_id, title=title, composer="ConcoursComposer",
            copyright_status="own", key=key, meter=meter, tempo=tempo,
            source="generated", division_tags=division_tags or [],
            generated=True,
        )

    def remove(self, score_id: str) -> bool:
        self._ngrams.pop(score_id, None)
        return self.scores.pop(score_id, None) is not None

    # ── 검색 ─────────────────────────────────────────────────────────────
    @staticmethod
    def _request_similarity(target: StyleProfile, cand: StyleProfile) -> float:
        """요청에서 만든 target 은 '아직 없는 곡' 이라 대부분의 칸이 비어 있다.

        그 상태로 코사인을 쓰면 방향이 아니라 크기가 이겨서, 쉬운 곡을 요청해도 가장
        화려한 곡이 1등으로 올라온다(실제로 그랬다). 그래서 **아는 축에서의 거리**로만
        점수를 낸다 — 난이도가 지배적이고, 템포·박자·선법이 보조한다.
        """
        diff_gap = abs(target.difficulty_score - cand.difficulty_score) / 9.0
        tempo_gap = abs(target.tempo - cand.tempo) / 160.0
        score = 1.0 - (0.60 * min(1.0, diff_gap) + 0.25 * min(1.0, tempo_gap))
        if target.meter == cand.meter:
            score += 0.10
        if target.mode == cand.mode:
            score += 0.05
        return max(0.0, min(1.0, score))

    def search(
        self,
        target: StyleProfile,
        *,
        difficulty: float | None = None,
        division: str = "",
        pinned_ids: list[str] | None = None,
        top: int = SEARCH_TOP,
    ) -> list[tuple[CorpusScore, float]]:
        """§7.8 검색: 상위 10 → 난이도 ±2 필터 → 상위 5. 원장 지정 곡은 항상 포함.

        target 이 실제 악보에서 뽑은 프로필이면(`measures > 0`) 전체 특징 벡터의 코사인을,
        요청에서 만든 것이면 아는 축만 쓰는 거리 점수를 쓴다.
        """
        pinned = set(pinned_ids or [])
        from_real_score = target.measures > 0
        tv = target.vector()

        def sim(cand: StyleProfile) -> float:
            if from_real_score:
                return cosine(tv, cand.vector())
            return self._request_similarity(target, cand)

        # 우리가 만든 곡은 스타일 참고에서 뺀다. 자기 출력을 다시 참고하면
        # 곡들이 서로를 닮아가고, 그것을 잡아 줄 지표가 없다.
        scored = [
            (s, sim(s.profile))
            for s in self.scores.values()
            if s.id not in pinned and not s.generated
        ]
        scored.sort(key=lambda kv: kv[1], reverse=True)
        pool = scored[:SEARCH_POOL]

        if difficulty is not None:
            # **모르는 것과 쉬운 것은 다르다.**
            # PDF 악보는 음표가 없어 난이도를 잴 수가 없고, 그 값이 0 으로 남는다.
            # 그것을 '난이도 0(아주 쉬움)' 으로 읽으면, 중급 곡을 만들 때 원장님이
            # 올리신 PDF 가 전부 걸러져 **한 번도 쓰이지 않는다.** 올리는 자리를
            # 만들어 놓고 정작 쓰지 않는 셈이다 — 모르면 거르지 않고 남긴다.
            filtered = [
                (s, sim) for s, sim in pool
                if not s.difficulty or abs(s.difficulty - difficulty) <= DIFFICULTY_WINDOW
            ]
            # 난이도 필터가 전부 걸러내면 필터 없이 쓴다 — 빈 컨텍스트보다는 낫다.
            pool = filtered or pool

        if division:
            preferred = [(s, sim) for s, sim in pool if division in s.division_tags]
            pool = preferred + [kv for kv in pool if kv not in preferred]

        out = [(self.scores[pid], 1.0) for pid in pinned if pid in self.scores]
        out += pool[: max(0, top - len(out))]
        return out

    def entries_for_prompt(self, results: list[tuple[CorpusScore, float]]) -> list[CorpusEntry]:
        return [s.to_entry() for s, _ in results]

    # ── 표절 인덱스 ──────────────────────────────────────────────────────
    def ngram_index(self, exclude: set[str] | None = None) -> set[tuple[int, ...]]:
        exclude = exclude or set()
        out: set[tuple[int, ...]] = set()
        for sid, grams in self._ngrams.items():
            if sid not in exclude:
                out |= grams
        return out
