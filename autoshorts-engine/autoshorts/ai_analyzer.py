"""Module C — AI Highlight Extractor.

타임스탬프가 붙은 전체 전사본을 Gemini 에 넘겨 30~60초짜리 완결형
하이라이트 구간을 3~5개 뽑는다. API 키가 없거나 호출이 실패하면
로컬 휴리스틱으로 대체해 무과금·오프라인에서도 파이프라인이 끝까지 돈다.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Sequence

from .models import Clip, Segment, Transcript
from .utils import get_logger

__all__ = [
    "analyze",
    "build_prompt",
    "SYSTEM_PROMPT",
    "RESPONSE_SCHEMA",
    "parse_response_json",
    "normalize_clips",
    "snap_to_segments",
    "heuristic_highlights",
    "AnalysisError",
]

LOG = get_logger("analyzer")

# 프롬프트 길이 안전선. Flash 계열은 여유가 크지만 무료 티어 RPM/TPM 을 아낀다.
MAX_PROMPT_CHARS = 120_000

SYSTEM_PROMPT = """당신은 조회수 상위 1% 쇼츠를 만들어 온 숏폼 편집자다.
아래 영상 전사본(타임스탬프 포함)에서 쇼츠로 잘라 쓸 구간을 고른다.

선정 기준:
1. 각 구간은 {min_seconds:.0f}~{max_seconds:.0f}초 길이여야 한다. 이 범위를 벗어나면 안 된다.
2. 앞뒤 맥락 없이 그 구간만 봐도 이해되는 '완결성 있는' 이야기여야 한다.
   문장 중간에서 시작하거나 끝나지 않게 발화 경계에 맞춘다.
3. 첫 3초 안에 시선을 잡는 훅(놀라운 주장, 반전, 강한 감정, 구체적 수치,
   질문, 갈등)이 있는 구간을 우선한다.
4. 서로 겹치지 않는 구간을 {min_clips}~{max_clips}개 고른다. 영상 전체에 고르게 분포시킨다.
5. 인사말, 채널 구독 요청, 광고, 잡담, 의미 없는 반복은 제외한다.

각 구간마다 다음을 채운다:
- start_time / end_time: 전사본의 실제 초 단위 숫자 (소수 1자리까지)
- title: 클릭을 부르는 한국어 후킹 제목. 25자 이내, 낚시성 과장 금지,
  구간에서 실제로 하는 말에 근거할 것.
- reason: 이 구간을 고른 이유 한 문장.
- score: 바이럴 가능성 0~100 정수.

반드시 아래 JSON 스키마만 출력한다. 설명, 마크다운, 코드펜스를 붙이지 않는다.
{{"clips": [{{"start_time": 0.0, "end_time": 0.0, "title": "", "reason": "", "score": 0}}]}}
"""

# Gemini 의 구조화 출력(response_schema)에 그대로 넘기는 스키마
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_time": {"type": "number"},
                    "end_time": {"type": "number"},
                    "title": {"type": "string"},
                    "reason": {"type": "string"},
                    "score": {"type": "number"},
                },
                "required": ["start_time", "end_time", "title", "reason", "score"],
            },
        }
    },
    "required": ["clips"],
}

# 훅이 될 만한 한국어/영어 신호어. 휴리스틱 점수의 근거.
_HOOK_WORDS = (
    "사실", "비밀", "진짜", "충격", "결국", "반전", "이유", "방법", "절대", "처음",
    "마지막", "왜냐하면", "그런데", "하지만", "놀랍게도", "핵심", "문제는", "중요한",
    "아무도", "생각보다", "실수", "성공", "실패", "돈", "만원", "억", "퍼센트", "%",
    "actually", "secret", "never", "always", "biggest", "mistake", "truth", "why",
)
_FILLER_WORDS = ("구독", "좋아요", "알림설정", "광고", "협찬", "subscribe", "sponsor")
_QUESTION_RE = re.compile(r"[?？]|까요|나요|습니까")
_NUMBER_RE = re.compile(r"\d")


class AnalysisError(RuntimeError):
    """하이라이트 분석 실패."""


def build_prompt(
    transcript: Transcript,
    *,
    min_seconds: float = 30.0,
    max_seconds: float = 60.0,
    min_clips: int = 3,
    max_clips: int = 5,
    video_title: str = "",
    max_chars: int = MAX_PROMPT_CHARS,
) -> str:
    """시스템 지시 + 전사본을 합친 최종 프롬프트."""
    header = SYSTEM_PROMPT.format(
        min_seconds=min_seconds,
        max_seconds=max_seconds,
        min_clips=min_clips,
        max_clips=max_clips,
    )
    meta = [f"영상 길이: {transcript.duration:.1f}초"]
    if video_title:
        meta.append(f"영상 제목: {video_title}")
    if transcript.language:
        meta.append(f"언어: {transcript.language}")
    body = transcript.timestamped_text(max_chars=max_chars)
    return f"{header}\n\n{' / '.join(meta)}\n\n=== 전사본 ===\n{body}\n=== 끝 ===\n"


def parse_response_json(text: str) -> list[dict[str, Any]]:
    """모델 응답에서 클립 배열을 뽑아낸다.

    코드펜스, 앞뒤 설명 문장이 섞여 있어도 첫 번째 JSON 오브젝트/배열을
    찾아 파싱한다.
    """
    if not text or not str(text).strip():
        raise AnalysisError("모델 응답이 비어 있습니다.")
    raw = str(text).strip()

    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()

    candidates = [raw]
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            candidates.append(match.group(0))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            for key in ("clips", "highlights", "results", "segments", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            # {"0": {...}} 형태 방어
            if all(isinstance(v, dict) for v in data.values()) and data:
                return list(data.values())
        elif isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

    raise AnalysisError("모델 응답에서 JSON 클립 목록을 찾지 못했습니다.")


def snap_to_segments(
    start: float,
    end: float,
    segments: Sequence[Segment],
    *,
    tolerance: float = 2.5,
) -> tuple[float, float]:
    """구간 경계를 가까운 발화 경계로 당겨 문장 중간 잘림을 막는다.

    ``tolerance`` 초 안에 발화 경계가 있을 때만 스냅한다.
    """
    if not segments:
        return start, end
    starts = [s.start for s in segments]
    ends = [s.end for s in segments]

    best_start = min(starts, key=lambda value: abs(value - start))
    if abs(best_start - start) <= tolerance:
        start = best_start
    best_end = min(ends, key=lambda value: abs(value - end))
    if abs(best_end - end) <= tolerance:
        end = best_end
    return start, end


def _overlap(a: Clip, b: Clip) -> float:
    return max(0.0, min(a.end, b.end) - max(a.start, b.start))


def normalize_clips(
    raw_clips: Iterable[dict[str, Any] | Clip],
    transcript: Transcript,
    *,
    min_seconds: float = 30.0,
    max_seconds: float = 60.0,
    min_clips: int = 3,
    max_clips: int = 5,
    snap_tolerance: float = 2.5,
    max_overlap_ratio: float = 0.25,
) -> list[Clip]:
    """모델이 준 구간을 실제로 렌더 가능한 형태로 교정한다.

    - 영상 길이 밖으로 나간 구간을 잘라 맞춘다.
    - 발화 경계로 스냅한다.
    - 너무 짧으면 늘리고, 너무 길면 자른다(가능하면 앞쪽을 살린다).
    - 크게 겹치는 구간은 점수가 높은 쪽만 남긴다.
    - 점수 내림차순으로 ``max_clips`` 개까지 남기고, 최종 순서는 시간순.
    """
    duration = transcript.duration or (max((s.end for s in transcript.segments), default=0.0))
    segments = list(transcript.segments)
    candidates: list[Clip] = []

    for item in raw_clips:
        clip = item if isinstance(item, Clip) else Clip.from_dict(item)
        start, end = float(clip.start), float(clip.end)
        if end <= start:
            LOG.debug("무시: 끝이 시작보다 빠른 구간 (%.1f~%.1f)", start, end)
            continue

        start, end = snap_to_segments(start, end, segments, tolerance=snap_tolerance)
        start = max(0.0, start)
        if duration:
            end = min(end, duration)
            start = min(start, max(0.0, duration - min_seconds))
        if end <= start:
            continue

        length = end - start
        if length > max_seconds:
            end = start + max_seconds
        elif length < min_seconds:
            need = min_seconds - length
            end = end + need
            if duration and end > duration:
                # 뒤가 모자라면 앞으로 당긴다.
                start = max(0.0, start - (end - duration))
                end = min(duration, start + min_seconds)

        if end - start < min(min_seconds, duration or min_seconds) - 0.5:
            LOG.debug("무시: 길이 확보 실패 (%.1f~%.1f)", start, end)
            continue

        clip.start, clip.end = round(start, 2), round(end, 2)
        if not clip.title:
            clip.title = _fallback_title(transcript, clip.start, clip.end)
        candidates.append(clip)

    # 점수 높은 순으로 훑으며 크게 겹치는 후보를 버린다.
    candidates.sort(key=lambda c: (-c.score, c.start))
    selected: list[Clip] = []
    for clip in candidates:
        if len(selected) >= max_clips:
            break
        conflict = any(
            _overlap(clip, kept) > max_overlap_ratio * min(clip.duration, kept.duration)
            for kept in selected
        )
        if conflict:
            LOG.debug("무시: 기존 클립과 겹침 (%.1f~%.1f)", clip.start, clip.end)
            continue
        selected.append(clip)

    selected.sort(key=lambda c: c.start)
    for index, clip in enumerate(selected, start=1):
        clip.index = index

    if len(selected) < min_clips:
        LOG.warning(
            "요청한 최소 클립 수(%d)보다 적은 %d개만 확보했습니다.", min_clips, len(selected)
        )
    return selected


def _fallback_title(transcript: Transcript, start: float, end: float, max_chars: int = 25) -> str:
    """제목이 비었을 때 구간 첫 문장으로 대체."""
    for segment in transcript.slice(start, end):
        text = segment.text.strip()
        if text:
            return text[:max_chars]
    return f"하이라이트 {int(start)}초"


def _window_score(segments: Sequence[Segment], start: float, end: float) -> tuple[float, str]:
    """휴리스틱 점수: 발화 밀도 + 훅 단어 + 숫자/질문 가산, 광고성 감점."""
    window = [s for s in segments if s.overlaps(start, end)]
    if not window:
        return 0.0, ""
    text = " ".join(s.text for s in window)
    span = max(end - start, 1.0)
    speech = sum(min(s.end, end) - max(s.start, start) for s in window)

    density = speech / span                                     # 0~1
    hooks = sum(text.count(word) for word in _HOOK_WORDS)
    fillers = sum(text.lower().count(word) for word in _FILLER_WORDS)
    questions = len(_QUESTION_RE.findall(text))
    numbers = len(_NUMBER_RE.findall(text))
    chars = len(text)

    score = (
        density * 40
        + min(hooks, 8) * 5
        + min(questions, 4) * 3
        + min(numbers, 10) * 1.2
        + min(chars / 400, 1.0) * 10
        - fillers * 8
    )
    return max(0.0, min(100.0, score)), text


def heuristic_highlights(
    transcript: Transcript,
    *,
    min_seconds: float = 30.0,
    max_seconds: float = 60.0,
    max_clips: int = 5,
    step: float = 5.0,
) -> list[Clip]:
    """Gemini 없이 도는 오프라인 대체 분석기.

    슬라이딩 윈도로 구간 점수를 매기고, 겹치지 않게 상위 구간을 고른다.
    품질은 LLM 보다 낮지만 무과금·오프라인에서도 결과물이 나온다.
    """
    segments = list(transcript.segments)
    if not segments:
        return []
    duration = transcript.duration or max(s.end for s in segments)
    window = min(max(min_seconds, (min_seconds + max_seconds) / 2), max(duration, min_seconds))

    scored: list[Clip] = []
    start = 0.0
    while start < max(duration - min_seconds, 0.0) + step:
        end = min(start + window, duration)
        if end - start < min(min_seconds, duration):
            break
        score, _ = _window_score(segments, start, end)
        if score > 0:
            snapped_start, snapped_end = snap_to_segments(start, end, segments, tolerance=2.0)
            scored.append(
                Clip(
                    start=snapped_start,
                    end=snapped_end,
                    title=_fallback_title(transcript, snapped_start, snapped_end),
                    reason="발화 밀도·훅 표현·수치 언급을 기준으로 자동 선정했습니다. (오프라인 분석)",
                    score=round(score, 1),
                )
            )
        start += step

    return normalize_clips(
        scored,
        transcript,
        min_seconds=min_seconds,
        max_seconds=max_seconds,
        min_clips=1,
        max_clips=max_clips,
    )


def _call_gemini(prompt: str, *, api_key: str, model: str, timeout: float = 180.0) -> str:
    """Gemini 호출. 신구 SDK(``google-genai`` / ``google-generativeai``) 모두 지원."""
    try:  # 신형 SDK 우선
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                temperature=0.7,
            ),
        )
        return response.text or ""
    except ImportError:
        pass

    try:
        import google.generativeai as genai_legacy  # type: ignore
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise AnalysisError(
            "Gemini SDK 가 없습니다. `pip install google-genai` (또는 google-generativeai) 로 설치하세요."
        ) from exc

    genai_legacy.configure(api_key=api_key)
    generative_model = genai_legacy.GenerativeModel(
        model,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.7,
        },
    )
    response = generative_model.generate_content(prompt, request_options={"timeout": timeout})
    return getattr(response, "text", "") or ""


def analyze(
    transcript: Transcript,
    *,
    api_key: str | None = None,
    model: str = "gemini-2.0-flash",
    min_seconds: float = 30.0,
    max_seconds: float = 60.0,
    min_clips: int = 3,
    max_clips: int = 5,
    video_title: str = "",
    allow_offline_fallback: bool = True,
) -> list[Clip]:
    """하이라이트 구간을 선정해 :class:`Clip` 목록으로 돌려준다."""
    if not transcript.segments:
        raise AnalysisError("전사 결과가 비어 있어 분석할 수 없습니다.")

    if not api_key:
        if not allow_offline_fallback:
            raise AnalysisError(
                "GEMINI_API_KEY 가 없습니다. 키를 설정하거나 오프라인 분석을 허용하세요."
            )
        LOG.warning("Gemini API 키가 없어 오프라인 휴리스틱 분석으로 진행합니다.")
        return heuristic_highlights(
            transcript, min_seconds=min_seconds, max_seconds=max_seconds, max_clips=max_clips
        )

    prompt = build_prompt(
        transcript,
        min_seconds=min_seconds,
        max_seconds=max_seconds,
        min_clips=min_clips,
        max_clips=max_clips,
        video_title=video_title,
    )
    LOG.info("Gemini 분석 요청: model=%s, 프롬프트 %d자", model, len(prompt))
    try:
        text = _call_gemini(prompt, api_key=api_key, model=model)
        raw_clips = parse_response_json(text)
        clips = normalize_clips(
            raw_clips,
            transcript,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            min_clips=min_clips,
            max_clips=max_clips,
        )
        if not clips:
            raise AnalysisError("교정 후 남은 클립이 없습니다.")
        LOG.info("Gemini 하이라이트 %d개 선정", len(clips))
        return clips
    except Exception as exc:
        if not allow_offline_fallback:
            raise AnalysisError(f"Gemini 분석 실패: {exc}") from exc
        LOG.warning("Gemini 분석 실패(%s). 오프라인 휴리스틱으로 대체합니다.", exc)
        return heuristic_highlights(
            transcript, min_seconds=min_seconds, max_seconds=max_seconds, max_clips=max_clips
        )
