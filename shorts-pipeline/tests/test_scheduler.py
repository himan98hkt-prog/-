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

    _curate_tests(check, TMP)
    _hd_prompt_pack_tests(check)
    _upload_queue_tests(check)

    shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "═" * 62)
    print(f" 통과 {len(PASSED)} / 실패 {len(FAILED)}")
    for n in FAILED:
        print(f"   ✗ {n}")
    print("═" * 62)
    return 1 if FAILED else 0




# ══════════════════════════════════════════════════════════════════════
def _curate_tests(check, TMP):
    """curate 검증. 미드저니 출력 형식을 흉내낸 파일로 확인한다."""
    from pipeline.curate import (
        analyze, classify, dedupe, prompt_from_filename, prompt_signature,
    )

    print("\n[테마 분류]")
    cases = [
        ("aideokhu_first_person_view_standing_on_a_rope_bridge_between_floating_islands_"
         "1a2b3c4d-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png", "sky_islands"),
        ("u_POV_walking_through_a_spirit_forest_glowing_mushroom_"
         "2a2b3c4d-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png", "spirit_forest"),
        ("u_descending_a_vast_temple_staircase_braziers_"
         "3a2b3c4d-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png", "temple"),
        ("u_from_inside_a_car_at_night_glowing_red_dashboard_"
         "4a2b3c4d-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png", "night_drive"),
        ("u_something_totally_unrelated_xyz_"
         "5a2b3c4d-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png", "misc"),
    ]
    for name, expect in cases:
        got = classify(Path(name))
        check(f"{expect} 분류", got == expect, got)

    print("\n[프롬프트 복원]")
    f = Path("aideokhu_POV_walking_a_frozen_river_between_ice_cliffs_"
             "1a2b3c4d-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png")
    text = prompt_from_filename(f)
    check("uuid 제거", "1a2b3c4d" not in text, text[:40])
    check("문장 복원", "frozen river" in text, text[:40])

    a = Path("u_POV_walking_a_frozen_river_aaaaaaaa-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png")
    b = Path("u_POV_walking_a_frozen_river_bbbbbbbb-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png")
    c = Path("u_POV_riding_a_dragon_cccccccc-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png")
    check("같은 프롬프트는 같은 서명", prompt_signature(a) == prompt_signature(b))
    check("다른 프롬프트는 다른 서명", prompt_signature(a) != prompt_signature(c))

    print("\n[점수 · 탈락]")
    d = TMP / "shots"
    d.mkdir(parents=True, exist_ok=True)

    def shot(name, size, color):
        p = d / name
        Image.new("RGB", size, color).save(p)
        return analyze(p)

    wide = shot("u_wide_castle_1a2b3c4d-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png",
                (1920, 1080), (20, 30, 70))
    check("가로 이미지 탈락", wide.disqualified)
    check("탈락 사유 명시", any("가로" in r for r in wide.reasons), str(wide.reasons))

    small = shot("u_small_temple_2a2b3c4d-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png",
                 (405, 720), (20, 30, 70))
    check("저해상도 탈락", small.disqualified)

    ok = shot("u_temple_stairs_3a2b3c4d-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png",
              (1080, 1920), (18, 26, 64))
    check("9:16 세로는 통과", not ok.disqualified, str(ok.reasons))

    bright = shot("u_bright_temple_4a2b3c4d-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png",
                  (1080, 1920), (240, 238, 230))
    check("너무 밝으면 감점", bright.score < ok.score + 15 and
          any("밝" in r for r in bright.reasons), f"{bright.score} vs {ok.score}")

    print("\n[중복 묶기]")
    same_a = shot("u_ice_river_aaaaaaaa-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png",
                  (1080, 1920), (20, 30, 70))
    same_b = shot("u_ice_river_bbbbbbbb-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png",
                  (1080, 1920), (20, 30, 70))
    other = shot("u_dragon_flight_cccccccc-1a2b-3c4d-5e6f-1a2b3c4d5e6f.png",
                 (1080, 1920), (20, 30, 70))
    groups = dedupe([same_a, same_b, other])
    check("같은 프롬프트 2장은 한 묶음", any(len(g) == 2 for g in groups),
          str([len(g) for g in groups]))
    check("다른 프롬프트는 안 합쳐짐",
          len(groups) == 2 and all(len(g) <= 2 for g in groups),
          str([len(g) for g in groups]))


# ══════════════════════════════════════════════════════════════════════
def _hd_prompt_pack_tests(check) -> None:
    """고급 팩(PROMPTS_HD.md) 프롬프트가 제대로 분류되고 제목이 안 겹치는지.

    파일명 하나로 테마·제목·훅이 전부 정해진다. 그래서 프롬프트를 새로 쓰면
    사전에 없는 어휘가 생겨 제목이 기본값으로 몰린다. 실제로 용·거대존재
    프롬프트 4개가 전부 "끝나지 않는 여행" 으로 나왔었다.
    """
    import re as _re

    from pipeline.copywriter import write as write_copy
    from pipeline.curate import classify, prompt_from_filename

    print("\n[고급 프롬프트 팩]")
    pack = ROOT / "seeds" / "PROMPTS_HD.md"
    # 로컬에는 있는데 CI 에서만 없으면 커밋이 안 된 것이다.
    # seeds/* 가 통째로 gitignore 라서 실제로 한 번 그렇게 빠졌다.
    check("PROMPTS_HD.md 있음", pack.exists(),
          "" if pack.exists() else "커밋됐는지 확인하세요 (seeds/* 는 gitignore 대상)")
    if not pack.exists():
        return

    prompts = [ln for ln in pack.read_text(encoding="utf-8").splitlines()
               if ln.startswith("first person view ")]
    check("프롬프트 20개 이상", len(prompts) >= 20, f"{len(prompts)}개")

    def as_filename(prompt: str) -> Path:
        # 미드저니는 프롬프트 앞부분을 파일명에 넣고 자른다
        t = _re.sub(r"[^a-z0-9 ]+", " ", prompt.lower())
        return Path(f"user_{'_'.join(t.split())[:95]}_9f3a2b1c.png")

    titles, themes = [], []
    for prompt in prompts:
        f = as_filename(prompt)
        theme = classify(f)
        themes.append(theme)
        titles.append(write_copy(theme, prompt_from_filename(f), seed_key=f.stem).title)

    check("미분류(misc) 없음", "misc" not in themes, f"{themes.count('misc')}개")
    check("테마가 골고루", len(set(themes)) >= 10, f"{len(set(themes))}종")
    dup = len(titles) - len(set(titles))
    check("제목 중복 없음", dup == 0, f"{dup}개 중복")
    check("기본 제목으로 안 몰림", titles.count("끝나지 않는 여행") <= 1,
          f"{titles.count('끝나지 않는 여행')}개")
    check("빈 제목 없음", all(t.strip() for t in titles))
    # 용을 타는 장면이 '걷는 길' 이 되면 안 된다
    dragon = [t for t in titles if "용의 등" in t]
    check("용은 나는 길로", all("나는" in t for t in dragon), str(dragon))

    # ── 자전거 다운힐 팩 ──────────────────────────────────────────────
    print("\n[다운힐 프롬프트 팩]")
    ride = ROOT / "seeds" / "PROMPTS_RIDE.md"
    check("PROMPTS_RIDE.md 있음", ride.exists(),
          "" if ride.exists() else "커밋됐는지 확인하세요 (seeds/* 는 gitignore 대상)")
    if not ride.exists():
        return

    ride_prompts = [ln for ln in ride.read_text(encoding="utf-8").splitlines()
                    if ln.startswith("first person view ")]
    check("프롬프트 12개 이상", len(ride_prompts) >= 12, f"{len(ride_prompts)}개")

    ride_titles, ride_themes = [], []
    for prompt in ride_prompts:
        f = as_filename(prompt)
        theme = classify(f)
        ride_themes.append(theme)
        ride_titles.append(
            write_copy(theme, prompt_from_filename(f), seed_key=f.stem).title)

    # 전부 downhill 이어야 한다. bicycle 이 alley_bike 로 새면 훅이
    # "비 온 뒤의 골목" 처럼 장면과 전혀 안 맞는 문구가 붙는다.
    wrong = sorted({t for t in ride_themes if t != "downhill"})
    check("전부 자전거 다운힐로", not wrong, str(wrong))
    ride_dup = len(ride_titles) - len(set(ride_titles))
    check("제목 중복 없음", ride_dup == 0, f"{ride_dup}개 중복")
    check("기본 제목 없음", "끝나지 않는 여행" not in ride_titles)
    check("전부 내려가는 길로", all("내려가는" in t for t in ride_titles),
          str([t for t in ride_titles if "내려가는" not in t]))
    # 두 팩을 합쳐도 제목이 겹치면 안 된다
    both = titles + ride_titles
    check("두 팩 합쳐도 제목 안 겹침", len(both) == len(set(both)),
          f"{len(both) - len(set(both))}개 중복")

    # 파일명이 95자에서 잘려도 분류 단어가 살아남아야 한다
    long_ok = all(
        classify(as_filename(p_)) == "downhill"
        for p_ in ride_prompts if len(as_filename(p_).stem) >= 95)
    check("잘린 파일명도 분류됨", long_ok)

    # ── 3인칭 월드 팩 ─────────────────────────────────────────────────
    print("\n[월드 프롬프트 팩]")
    world = ROOT / "seeds" / "PROMPTS_WORLD.md"
    check("PROMPTS_WORLD.md 있음", world.exists(),
          "" if world.exists() else "커밋됐는지 확인하세요 (seeds/* 는 gitignore 대상)")
    if not world.exists():
        return

    world_prompts = [ln for ln in world.read_text(encoding="utf-8").splitlines()
                     if ln.startswith("third person view ")]
    check("프롬프트 12개 이상", len(world_prompts) >= 12, f"{len(world_prompts)}개")

    world_titles = []
    world_wrong = []
    for prompt in world_prompts:
        f = as_filename(prompt)
        theme = classify(f)
        if theme != "downhill":
            world_wrong.append(f"{theme}: {prompt[:50]}")
        world_titles.append(
            write_copy(theme, prompt_from_filename(f), seed_key=f.stem).title)

    check("전부 자전거 다운힐로", not world_wrong, str(world_wrong[:3]))
    check("제목 중복 없음", len(world_titles) == len(set(world_titles)),
          f"{len(world_titles) - len(set(world_titles))}개 중복")
    check("기본 제목 없음", "끝나지 않는 여행" not in world_titles)

    # 세 팩을 전부 합쳐도 제목이 겹치면 안 된다
    everything = titles + ride_titles + world_titles
    check("세 팩 합쳐도 제목 안 겹침",
          len(everything) == len(set(everything)),
          f"{len(everything) - len(set(everything))}개 중복")


def _upload_queue_tests(check) -> None:
    """예약 업로드 대기열.

    컴퓨터가 꺼져 있으면 예약 시각을 놓친다. 놓친 것을 버리면 사용자는
    올라간 줄 알고 넘어간다. 그래서 밀린 것은 다음에 켤 때 올리되,
    너무 오래된 것은 사람이 판단하도록 남긴다.
    """
    import tempfile
    from datetime import datetime, timedelta

    from publish.queue import STALE_HOURS, Queue

    print("\n[예약 업로드]")
    d = Path(tempfile.mkdtemp())
    q = Queue.load(d)
    now = datetime.now()

    q.add("run_due", ["youtube", "instagram"],
          (now - timedelta(minutes=5)).isoformat())
    q.add("run_future", ["youtube"], (now + timedelta(hours=3)).isoformat())
    q.add("run_stale", ["instagram"],
          (now - timedelta(hours=STALE_HOURS + 1)).isoformat())

    due = q.due()
    check("지난 예약을 집어낸다", due is not None and due.run == "run_due",
          due.run if due else "없음")
    check("미래 예약은 안 건드린다",
          all(i.run != "run_future" for i in [due] if i))
    check("너무 밀린 것은 자동으로 안 올린다",
          [i.run for i in q.stale()] == ["run_stale"], str(q.stale()))
    check("밀린 것도 버리지는 않는다",
          any(i.run == "run_stale" for i in q.items))

    # 껐다 켜도 남아야 한다
    again = Queue.load(d)
    check("파일로 살아남는다", len(again.items) == 3, f"{len(again.items)}건")

    # 같은 영상을 두 번 예약하면 덮어쓴다 — 두 번 올리면 안 된다
    q.add("run_due", ["youtube"], (now + timedelta(days=1)).isoformat())
    dupes = [i for i in Queue.load(d).items
             if i.run == "run_due" and i.status == "waiting"]
    check("같은 영상은 예약 하나만", len(dupes) == 1, f"{len(dupes)}건")

    check("취소된다", Queue.load(d).cancel("run_future"))
    check("취소 뒤엔 안 남는다",
          all(i.run != "run_future" for i in Queue.load(d).items))
    check("없는 것 취소는 False", Queue.load(d).cancel("없는run") is False)

    # 올릴 곳이 없으면 예약이 성립하지 않는다
    try:
        Queue.load(d).add("x", [], now.isoformat())
        check("빈 대상은 거부", False)
    except ValueError:
        check("빈 대상은 거부", True)
    try:
        Queue.load(d).add("x", ["youtube"], "내일 아홉시")
        check("이상한 시각은 거부", False)
    except ValueError:
        check("이상한 시각은 거부", True)
    # 모르는 대상은 조용히 걸러낸다
    it = Queue.load(d).add("x", ["youtube", "틱톡"], now.isoformat())
    check("모르는 대상은 무시", it.targets == ["youtube"], str(it.targets))

    server = (ROOT / "ui" / "server.py").read_text(encoding="utf-8")
    check("워커가 돈다", "_queue_worker" in server and "daemon=True" in server)
    check("한 번에 하나만 올린다", "if jobs.active():" in server)
    check("영상이 지워졌으면 건너뛴다", '"skipped"' in server)
    html = (ROOT / "ui" / "app.html").read_text(encoding="utf-8")
    check("카드에 예약 버튼", 'data-sch=' in html)
    check("예약 상태를 보여준다", "업로드 예약" in html and "공개 예약" in html)
    check("컴퓨터가 켜져 있어야 한다고 알려준다", "켜져 있고" in html)

    # ── 지금 올리고 나중에 공개 (컴퓨터가 꺼져 있어도 되는 길) ──────
    print("\n[유튜브 공개 예약]")
    from publish.youtube import UploadError, _rfc3339

    later = (now + timedelta(days=2)).strftime("%Y-%m-%dT21:00")
    stamp = _rfc3339(later)
    check("UTC RFC3339 로 바꾼다", stamp.endswith("Z") and "T" in stamp, stamp)
    # 한국(UTC+9) 21:00 은 12:00Z 다. 로컬 그대로 보내면 9시간 어긋난다.
    import os
    from datetime import datetime as _dt
    keep = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "Asia/Seoul"
        __import__("time").tzset()
        check("한국 21시는 12시 UTC",
              _rfc3339("2026-12-25T21:00") == "2026-12-25T12:00:00Z",
              _rfc3339("2026-12-25T21:00"))
    finally:
        if keep is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = keep
        __import__("time").tzset()

    for bad in ("내일 아홉시", "2020-01-01T09:00"):
        try:
            _rfc3339(bad)
            check(f"{bad!r} 는 거부", False)
        except UploadError:
            check(f"{bad!r} 는 거부", True)

    yt = (ROOT / "publish" / "youtube.py").read_text(encoding="utf-8")
    check("publishAt 을 보낸다", 'body["status"]["publishAt"] = when' in yt)
    # 예약 공개는 비공개 업로드에서만 된다. 공개로 올리면 즉시 공개된다.
    check("예약이면 비공개로 강제", 'privacy = "private"' in yt)

    # publish_at 예약은 시각을 기다리지 않고 지금 올려야 한다
    q2 = Queue.load(Path(tempfile.mkdtemp()))
    q2.add("r_pub", ["youtube"], (now + timedelta(days=2)).isoformat(),
           kind="publish_at")
    q2.add("r_up", ["youtube"], (now + timedelta(days=2)).isoformat(),
           kind="upload_at")
    d2 = q2.due()
    check("공개 예약은 지금 올린다", d2 is not None and d2.run == "r_pub",
          d2.run if d2 else "없음")
    server2 = (ROOT / "ui" / "server.py").read_text(encoding="utf-8")
    check("워커가 --publish-at 을 넘긴다", '"--publish-at", item.at' in server2)


if __name__ == "__main__":
    sys.exit(main())
