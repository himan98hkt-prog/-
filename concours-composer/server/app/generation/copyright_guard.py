"""저작권 가드 (CLAUDE.md 절대 규칙 3).

`copyright_status == "copyrighted"` 인 코퍼스 곡의 음표열은 어떤 프롬프트에도
들어가지 못한다. 통계·특징(StyleProfile 수치)만 통과시킨다.
프롬프트를 조립하는 모든 경로가 이 모듈을 지나야 한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CopyrightStatus = Literal["public_domain", "copyrighted", "own"]

# public_domain/own 곡이라도 프롬프트에 넣을 수 있는 발췌 길이 상한(§7.3 Stage 0)
MAX_EXCERPT_MEASURES = 8
MAX_EXCERPTS = 3


class CopyrightViolation(RuntimeError):
    """저작권곡의 음표열이 프롬프트로 새려는 시도. 절대 통과시키지 않는다."""


@dataclass
class CorpusEntry:
    id: str
    title: str
    composer: str
    copyright_status: CopyrightStatus
    style_profile: dict[str, Any]
    excerpt_measures: list[dict[str, Any]] | None = None   # 음표열 — 통과 여부는 상태가 정한다

    @property
    def excerpt_allowed(self) -> bool:
        return self.copyright_status in ("public_domain", "own")


def sanitize_entry(entry: CorpusEntry) -> dict[str, Any]:
    """프롬프트에 넣어도 되는 형태로 깎아낸다."""
    out: dict[str, Any] = {
        "id": entry.id,
        "title": entry.title,
        "composer": entry.composer,
        "copyright_status": entry.copyright_status,
        "style_profile": entry.style_profile,
    }
    if entry.excerpt_allowed and entry.excerpt_measures:
        out["excerpt_measures"] = entry.excerpt_measures[:MAX_EXCERPT_MEASURES]
    return out


def sanitize_corpus(entries: list[CorpusEntry]) -> list[dict[str, Any]]:
    """발췌를 가진 곡은 최대 MAX_EXCERPTS 개까지만 음표열을 남긴다."""
    out: list[dict[str, Any]] = []
    excerpts_used = 0
    for e in entries:
        s = sanitize_entry(e)
        if "excerpt_measures" in s:
            if excerpts_used >= MAX_EXCERPTS:
                s.pop("excerpt_measures")
            else:
                excerpts_used += 1
        out.append(s)
    return out


def assert_no_copyrighted_notes(payload: Any, entries: list[CorpusEntry]) -> None:
    """조립된 프롬프트 페이로드에 저작권곡 음표열이 없는지 최종 확인.

    tests/test_copyright_guard.py 가 이 함수를 직접 호출한다.
    """
    protected_ids = {e.id for e in entries if not CorpusEntry.excerpt_allowed.fget(e)}  # type: ignore[attr-defined]

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            if node.get("id") in protected_ids and "excerpt_measures" in node:
                raise CopyrightViolation(
                    f"{path}: 저작권곡 {node['id']} 의 음표열이 프롬프트에 포함됐다"
                )
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(payload)
