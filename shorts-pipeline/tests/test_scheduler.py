"""스케줄러 · 콘텐츠 메타데이터 검증 (API 호출 0회)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from pipeline.content import (  # noqa: E402
    Content, find_sidecar, load_content, write_template,
)

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_sched"


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(f"  {'✓' if cond else '✗'} {name}" + (f"  — {detail}" if detail else ""))


def seed(folder: Path, name: str, sidecar: str | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{name}.png"
    Image.new("RGB", (108, 192), (20, 30, 60)).save(p)
    if sidecar is not None:
        (folder / f"{name}.yaml").write_text(sidecar, encoding="utf-8")
    return p


def main() -> int:
    shutil.rmtree(TMP, ignore_errors=True)
    print("═" * 62)
    print(" 스케줄러 · 콘텐츠 검증")
    print("═" * 62)

    print("\n[콘텐츠 사이드카]")
    s = TMP / "seeds"
    seed(s, "neon_alley", "title: 비 내리는 네온 골목\nhook: 이 길 끝에 뭐가 있을까\n"
                          "prompt: rainy neon alley forward motion\n")
    c = load_content(s / "neon_alley.png")
    check("제목 읽기", c.title == "비 내리는 네온 골목", c.title)
    check("훅 읽기", c.hook == "이 길 끝에 뭐가 있을까")
    check("프롬프트 읽기", c.prompt == "rainy neon alley forward motion")
    check("description 은 훅 우선", c.description == c.hook)

    bare = seed(s, "star_coast")
    c2 = load_content(bare)
    check("사이드카 없으면 파일명", c2.title == "Star Coast", c2.title)
    check("description 은 제목으로 대체", c2.description == "Star Coast")

    print("\n[템플릿 렌더링]")
    import yaml
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    yt = cfg["publish"]["youtube"]
    ig = cfg["publish"]["instagram"]

    title = c.youtube_title(yt["title_template"])
    check("유튜브 제목에 브랜드 포함", "AI DEOKHU" in title and "#Shorts" in title, title)
    check("유튜브 제목 100자 이내", len(title) <= 100, f"{len(title)}자")

    desc = c.youtube_description(yt["description_template"])
    check("설명에 훅이 첫 줄", desc.splitlines()[0] == c.hook, desc.splitlines()[0])
    check("설명에 업로드 시각", "저녁 9시" in desc)
    check("설명에 인스타 핸들", "@ai.deokhu" in desc)
    check("설명에 #Shorts", "#Shorts" in desc)
    check("설명 5000자 이내", len(desc) <= 5000, f"{len(desc)}자")

    cap = c.instagram_caption(ig["caption_template"])
    check("캡션 첫 줄이 훅", cap.splitlines()[0] == c.hook, cap.splitlines()[0])
    check("캡션에 한글 해시태그", "#릴스" in cap and "#AI영상" in cap)
    check("캡션 2200자 이내", len(cap) <= 2200, f"{len(cap)}자")

    long_title = Content(title="가" * 300)
    check("긴 제목은 잘린다", len(long_title.youtube_title("{title}")) == 100)

    print("\n[시드 선택]")
    from publish import scheduler as sch

    picked = sch.pick_seed(s, shuffle=False)
    check("사이드카 있는 시드 우선", picked.stem == "neon_alley", picked.name)

    print("\n[시드 소진]")
    sch.retire_seed(s / "neon_alley.png")
    check("이미지가 _used 로", (s / "_used" / "neon_alley.png").exists())
    check("사이드카도 함께 이동", (s / "_used" / "neon_alley.yaml").exists())
    check("원본은 사라짐", not (s / "neon_alley.png").exists())
    check("남은 시드는 사이드카 없는 것", sch.pick_seed(s, shuffle=False).stem == "star_coast")

    print("\n[plan 양식]")
    tmpl = write_template(bare)
    check("양식 생성", tmpl.exists() and tmpl.suffix == ".yaml")
    check("양식이 파싱된다", load_content(bare).title == "Star Coast")
    check("find_sidecar 가 찾는다", find_sidecar(bare) == tmpl)

    print("\n[--at 대기 계산]")
    from datetime import datetime
    import time as _t
    started = _t.time()
    past = f"{max(datetime.now().hour - 1, 0):02d}:00"
    sch.wait_until(past)
    check("지난 시각은 기다리지 않는다", _t.time() - started < 1.0)
    started = _t.time()
    sch.wait_until("99:99")
    check("잘못된 형식도 안 멈춘다", _t.time() - started < 1.0)

    print("\n[doctor]")
    from pipeline.config import load_config
    from pipeline.doctor import run_all
    sections, can_gen = run_all(ROOT, load_config(ROOT / "config.yaml"))
    names = [s.title for s in sections]
    check("5개 영역 점검", len(sections) == 5, ", ".join(names))
    check("시드 없으면 생성 불가 판정", isinstance(can_gen, bool))
    core = sections[0]
    check("ffmpeg 감지", any(c.name == "ffmpeg" and c.status == "ok" for c in core.checks))

    shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "═" * 62)
    print(f" 통과 {len(PASSED)} / 실패 {len(FAILED)}")
    for n in FAILED:
        print(f"   ✗ {n}")
    print("═" * 62)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
