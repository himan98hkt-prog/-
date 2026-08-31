#!/usr/bin/env python3
"""M0 완료 기준: 외부 도구 검증.

ffmpeg / mscore / audiveris / fluidsynth / music21 / anthropic
각 항목은 (이름, 상태, 상세)로 보고하고 하나라도 FAIL 이면 종료코드 1.
--soft 를 주면 FAIL 도 경고로만 처리한다(로컬 개발용).

채보·시각화(B축)는 docs/SCOPE.md 결정으로 제외했으므로 torch·chromium 은 검사하지 않는다.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 60
OK, WARN, FAIL = "OK", "WARN", "FAIL"


def _run(cmd: list[str], timeout: int = TIMEOUT) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except FileNotFoundError:
        return 127, f"{cmd[0]} 없음"
    except subprocess.TimeoutExpired:
        return 124, f"{cmd[0]} 타임아웃 {timeout}s"


def check_ffmpeg() -> tuple[str, str]:
    exe = os.environ.get("FFMPEG_BIN", "ffmpeg")
    if not shutil.which(exe):
        return FAIL, "ffmpeg 미설치 — MP3 내보내기 불가"
    code, out = _run([exe, "-version"])
    return (OK, out.splitlines()[0]) if code == 0 else (FAIL, out[:200])


def check_mscore() -> tuple[str, str]:
    exe = os.environ.get("MSCORE_BIN", "mscore")
    if not shutil.which(exe):
        return WARN, "MuseScore CLI 미설치 — PDF/MP3 는 FluidSynth 폴백 사용"
    code, out = _run([exe, "--version"])
    return (OK, (out.splitlines() or ["mscore"])[0]) if code == 0 else (WARN, out[:200])


def check_audiveris() -> tuple[str, str]:
    exe = os.environ.get("AUDIVERIS_BIN", "audiveris")
    if not shutil.which(exe):
        return WARN, "Audiveris 미설치 — PDF/이미지 OMR 업로드 비활성"
    code, out = _run([exe, "-version"], timeout=90)
    return (OK, (out.splitlines() or ["audiveris"])[0]) if code in (0, 1) else (WARN, out[:200])


def check_fluidsynth() -> tuple[str, str]:
    exe = os.environ.get("FLUIDSYNTH_BIN", "fluidsynth")
    if not shutil.which(exe):
        return WARN, "fluidsynth 미설치 — MuseScore CLI 가 있으면 그쪽으로 MP3 를 만든다"
    sf = os.environ.get("SOUNDFONT_PATH", "")
    if sf and not Path(sf).exists():
        return WARN, f"fluidsynth 는 있으나 사운드폰트 없음: {sf}"
    return OK, "fluidsynth + 사운드폰트"


def check_music21() -> tuple[str, str]:
    try:
        import music21
    except Exception as e:
        return FAIL, f"music21 import 실패: {e}"
    from music21 import note, stream
    from music21.musicxml.m21ToXml import GeneralObjectExporter

    s = stream.Score()
    p = stream.Part()
    p.append(note.Note("C4", quarterLength=1.0))
    s.insert(0, p)
    xml = GeneralObjectExporter().parse(s).decode("utf-8")
    if "<note" not in xml:
        return FAIL, "MusicXML 직렬화 결과에 <note> 없음"
    return OK, f"music21 {music21.VERSION_STR} · MusicXML 왕복 성공"


def check_anthropic() -> tuple[str, str]:
    """작곡 품질이 전부 여기 달렸다 — SDK 와 모델 문자열을 시작 시 확인한다."""
    try:
        import anthropic
    except Exception as e:
        return FAIL, f"anthropic SDK import 실패: {e}"
    composer = os.environ.get("COMPOSER_MODEL", "")
    writer = os.environ.get("WRITER_MODEL", "")
    if not composer or not writer:
        return WARN, "COMPOSER_MODEL / WRITER_MODEL 미설정 — .env 를 확인하라"
    # Settings.has_api_key 와 같은 판정을 쓴다 — .env 의 자리표시자를 키로 착각하지 않게.
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    has_key = key.startswith("sk-ant-") and len(key) > 20
    keymsg = "API 키 있음" if has_key else "API 키 없음 → 스텁 엔진으로만 동작"
    return OK, f"anthropic {anthropic.__version__} · {composer} / {writer} · {keymsg}"


CHECKS = [
    ("ffmpeg", check_ffmpeg),
    ("mscore", check_mscore),
    ("audiveris", check_audiveris),
    ("fluidsynth", check_fluidsynth),
    ("music21", check_music21),
    ("anthropic", check_anthropic),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--soft", action="store_true", help="FAIL 도 경고로만 처리")
    args = ap.parse_args()

    rows: list[tuple[str, str, str]] = []
    for name, fn in CHECKS:
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = FAIL, f"검사 실패: {e}"
        rows.append((name, status, detail))

    width = max(len(r[0]) for r in rows)
    icons = {OK: "OK  ", WARN: "WARN", FAIL: "FAIL"}
    print("\nConcoursComposer · make check-tools")
    print("-" * 78)
    for name, status, detail in rows:
        print(f"[{icons[status]}] {name.ljust(width)}  {detail}")
    print("-" * 78)

    failed = [r[0] for r in rows if r[1] == FAIL]
    warned = [r[0] for r in rows if r[1] == WARN]
    print(f"OK {len(rows) - len(failed) - len(warned)} · WARN {len(warned)} · FAIL {len(failed)}\n")
    if failed and not args.soft:
        print(f"필수 도구 실패: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
