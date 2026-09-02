"""판매 꾸러미 — 한 곡에 딸린 모든 것을 폴더 하나로.

학원에 악보를 팔 때 파일을 하나씩 받아 모으는 일은 사람이 할 일이 아니다. 게다가
받는 쪽(다른 학원 원장)은 이 프로그램을 모른다 — 압축을 풀었을 때 **무엇이 들었고
무엇부터 열면 되는지**가 안에 적혀 있어야 한다.

그래서 꾸러미에는 파일만이 아니라 `읽어보세요.txt` 가 함께 들어간다.

저작권이 정리되지 않은 곡은 꾸러미를 만들 때 그 사실을 안에 크게 적는다. 막지는
않는다 — 보관용으로 뽑을 수도 있으니까. 다만 모르고 파는 일은 없어야 한다.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import date

from app.schemas.guide import Guide
from app.schemas.rights import SOURCE_STATUS_KO, WorkRights


@dataclass(frozen=True)
class PackageInput:
    """꾸러미 하나를 만드는 데 필요한 것 전부."""

    composition_id: str
    title: str
    composer: str
    key: str
    meter: str
    tempo: int
    measures: int
    difficulty: float
    duration_sec: int
    musicxml: str
    audio: bytes
    audio_ext: str
    midi: bytes
    guide: Guide | None
    rights: WorkRights
    rights_ready: bool
    rights_blockers: list[str]
    combined_score: float
    judge_average: float | None
    judge_passed: bool | None
    # 지도용 판 — 원장이 보고 가르치는 쪽. 없으면 꾸러미에서 빠진다.
    teaching_musicxml: str = ""
    teaching_notes: str = ""


def _safe(name: str) -> str:
    """파일 이름에 못 쓰는 글자를 눕힌다. 윈도우가 제일 까다롭다."""
    out = "".join("_" if c in '\\/:*?"<>|' else c for c in name).strip(" .")
    return out or "무제"


def _guide_markdown(g: Guide, title: str) -> str:
    lines = [f"# {title} — 연주법 해설", "", g.overview, ""]
    if g.sections:
        lines += ["## 구간별 요점", ""]
        for s in g.sections:
            lines.append(f"### {s.measures[0]}~{s.measures[1]}마디 · {s.title}")
            lines += [f"- {p}" for p in s.points]
            lines.append("")
    if g.fingering_notes:
        lines += ["## 손가락", ""]
        lines += [f"- {f.measure}마디: {f.note}" for f in g.fingering_notes]
        lines.append("")
    if g.practice_plan:
        lines += ["## 연습 계획", ""]
        for w in g.practice_plan:
            lines += [
                f"### {w.week}주차 — {w.goal}",
                f"- 방법: {w.method}",
                f"- 메트로놈: ♩={w.metronome_bpm}",
                "",
            ]
    if g.memorization_map:
        lines += ["## 암보 구획", ""]
        lines += [f"- {c.measures[0]}~{c.measures[1]}마디: {c.cue}" for c in g.memorization_map]
        lines.append("")
    if g.competition_tips:
        lines += ["## 무대에서", ""]
        lines += [f"- {t}" for t in g.competition_tips]
    return "\n".join(lines).rstrip() + "\n"


def _info_markdown(p: PackageInput) -> str:
    mins, secs = divmod(max(0, p.duration_sec), 60)
    lines = [
        f"# {p.title}",
        "",
        f"작곡 **{p.composer}**",
        "",
        "| | |",
        "|---|---|",
        f"| 조성 | {p.key} |",
        f"| 박자 | {p.meter} |",
        f"| 빠르기 | ♩={p.tempo} |",
        f"| 길이 | {p.measures}마디 · 약 {mins}분 {secs}초 |",
        f"| 난이도 | {p.difficulty} / 10 |",
        "| 편성 | 피아노 독주 (2단 보표) |",
    ]
    if p.judge_average is not None:
        verdict = "통과" if p.judge_passed else "초안"
        lines.append(f"| 사전 심사 | {verdict} · 평균 {p.judge_average} |")
    lines += [
        f"| 품질 종합 | {p.combined_score} |",
        "",
        "이 곡은 검증기(음역·손 스팬·박자·성부 규칙)를 통과했습니다.",
    ]
    return "\n".join(lines) + "\n"


def _rights_markdown(p: PackageInput) -> str:
    r = p.rights
    kind = "창작곡" if r.work_type == "original" else "2차적저작물(편곡)"
    lines = [f"# 권리 정보 — {p.title}", "", f"- 구분: {kind}", f"- 작곡: {p.composer}"]
    if r.work_type == "arrangement":
        lines += [
            f"- 원곡: {r.original_title or '(비어 있음)'} / {r.original_composer or '(비어 있음)'}",
            f"- 원곡 권리: {SOURCE_STATUS_KO.get(r.original_status, r.original_status)}",
            f"- 이용허락 근거: {r.license_note or '(없음)'}",
        ]
    if r.first_published:
        lines.append(f"- 공표일: {r.first_published}")
    lines.append("")
    if p.rights_ready:
        lines += ["## 상태: 정리됨", "", "등록·판매에 필요한 권리 정보가 채워져 있습니다."]
    else:
        lines += [
            "## 상태: 아직 정리되지 않음",
            "",
            "**이대로 등록하거나 판매하면 안 됩니다.** 아래를 먼저 해결하십시오.",
            "",
        ]
        lines += [f"- {b}" for b in p.rights_blockers]
    return "\n".join(lines) + "\n"


def _readme(p: PackageInput, names: dict[str, str]) -> str:
    """받는 사람이 압축을 풀었을 때 제일 먼저 읽는 글."""
    lines = [
        f"{p.title}",
        "=" * (len(p.title) + 4),
        "",
        f"작곡 {p.composer}",
        f"{p.key} · {p.meter} · ♩={p.tempo} · {p.measures}마디 · 난이도 {p.difficulty}/10",
        "",
        "무엇이 들어 있나",
        "----------------",
        f"  {names['audio']}",
        "      먼저 이것부터 들어 보십시오. 어느 기기에서나 열립니다.",
        f"  {names['xml']}",
        "      **아이에게 줄 악보**입니다. 음표만 있는 깨끗한 판입니다.",
        "      MuseScore·Sibelius·Finale 에서 열어 인쇄하십시오.",
        "      (MuseScore 는 무료입니다: https://musescore.org)",
        f"  {names['midi']}",
        "      오른손·왼손이 트랙으로 나뉜 MIDI 입니다. 손 나눠 연습할 때 씁니다.",
    ]
    if "teaching" in names:
        lines += [
            f"  {names['teaching']}",
            "      **가르치실 때 보는 악보**입니다. 손가락 번호와 지도 요점이 얹혀 있습니다.",
            "      아이에게는 위의 깨끗한 악보를 주십시오.",
        ]
    if "teaching_notes" in names:
        lines += [
            f"  {names['teaching_notes']}",
            "      악보를 열지 않고도 읽는 지도 메모입니다 — 아이가 걸리는 자리가 적혀 있습니다.",
        ]
    if "guide" in names:
        lines += [
            f"  {names['guide']}",
            "      구간별 요점·손가락·주차별 연습 계획·암보 구획이 적혀 있습니다.",
        ]
    lines += [
        f"  {names['info']}",
        "      조성·길이·난이도 등 곡의 제원입니다.",
        f"  {names['rights']}",
        "      이 곡의 저작권 구분과 상태입니다.",
        "",
        "악보를 인쇄하려면",
        "-----------------",
        "  1. musescore.org 에서 MuseScore 를 내려받아 설치합니다(무료).",
        f"  2. {names['xml']} 를 두 번 누르면 열립니다.",
        "  3. 파일 → 인쇄.",
        "",
    ]
    if not p.rights_ready:
        lines += [
            "!! 주의",
            "-------",
            "  이 곡은 권리 정보가 아직 정리되지 않았습니다.",
            "  판매·배포 전에 함께 든 권리 정보 문서를 확인하십시오.",
            "",
        ]
    lines.append(f"만든 날 {date.today().isoformat()}")
    return "\n".join(lines) + "\n"


def build_package(p: PackageInput) -> tuple[bytes, str]:
    """꾸러미 ZIP 과 파일 이름을 만든다.

    압축을 풀면 곡 제목 폴더 하나가 나오게 담는다 — 바탕화면에 파일이 흩어지지 않는다.
    """
    stem = _safe(p.title)
    names = {
        "audio": f"연주.{p.audio_ext}",
        "xml": f"{stem}.musicxml",
        "midi": f"{stem}.mid",
        "info": "곡 정보.md",
        "rights": "권리 정보.md",
    }
    if p.guide is not None:
        names["guide"] = "연주법 해설.md"
    if p.teaching_musicxml:
        names["teaching"] = f"{stem} (지도용).musicxml"
    if p.teaching_notes:
        names["teaching_notes"] = "지도 메모.md"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        root = stem
        z.writestr(f"{root}/읽어보세요.txt", _readme(p, names))
        z.writestr(f"{root}/{names['audio']}", p.audio)
        z.writestr(f"{root}/{names['xml']}", p.musicxml)
        z.writestr(f"{root}/{names['midi']}", p.midi)
        z.writestr(f"{root}/{names['info']}", _info_markdown(p))
        z.writestr(f"{root}/{names['rights']}", _rights_markdown(p))
        if p.guide is not None:
            z.writestr(f"{root}/{names['guide']}", _guide_markdown(p.guide, p.title))
        if p.teaching_musicxml:
            z.writestr(f"{root}/{names['teaching']}", p.teaching_musicxml)
        if p.teaching_notes:
            z.writestr(f"{root}/{names['teaching_notes']}", p.teaching_notes)
    return buf.getvalue(), f"{stem}.zip"
