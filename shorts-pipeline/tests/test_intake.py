"""새 이미지 들여오기·다시 분류·배경음악 자동 선택 검사.

    python tests/test_intake.py

여기서 지키려는 것은 하나다 — **계속 다운로드해도 안전할 것.**
같은 폴더를 몇 번을 가리켜도 이미 있는 것은 건드리지 않고,
새로 받은 것만 붙어야 한다. 이게 깨지면 이미 만든 영상의 시드가
이름이 바뀌거나 사라진다.
"""

from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw          # noqa: E402

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_intake"


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(name)
    print(f"  {'✓' if condition else '✗'} {name}" + (f"  — {detail}" if detail else ""))


def make_image(path: Path, seed: int, size=(816, 1456)) -> Path:
    """매번 다른 그림. 같은 seed 면 같은 그림."""
    rnd = random.Random(seed)
    img = Image.new("RGB", size, (rnd.randrange(40, 90),) * 3)
    draw = ImageDraw.Draw(img)
    for _ in range(70):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        draw.ellipse([x, y, x + rnd.randrange(40, 320), y + rnd.randrange(40, 320)],
                     fill=(rnd.randrange(255), rnd.randrange(255), rnd.randrange(255)))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


MJ = {
    "downhill": "user_first_person_view_cycling_downhill_a_switchback_mountain_road_aa11.png",
    "spirit_path": "user_first_person_view_walking_a_torii_tunnel_at_night_bb22.png",
    "dragon": "user_first_person_view_riding_on_a_dragon_neck_over_the_clouds_cc33.png",
    "underwater": "user_first_person_view_swimming_down_to_a_sunken_city_dd44.png",
}


# ══════════════════════════════════════════════════════════════════════
def intake_tests() -> None:
    from pipeline.intake import import_folder, read_sidecar, reclassify

    src, seeds = TMP / "dl", TMP / "seeds"
    for i, name in enumerate(MJ.values()):
        make_image(src / name, i)
    seeds.mkdir(parents=True, exist_ok=True)

    print("\n[처음 들여오기]")
    r = import_folder(src, seeds)
    check("4장 다 살펴봄", r.scanned == 4, f"{r.scanned}장")
    check("4장 다 들어옴", len(r.added) == 4, f"{len(r.added)}장")
    themes = sorted(i.theme for i in r.added)
    check("테마가 파일명대로", themes == sorted(MJ), str(themes))
    check("제목이 다 다름",
          len({i.title for i in r.added}) == 4,
          str([i.title for i in r.added]))
    check("사이드카가 생김",
          all((seeds / i.name).with_suffix(".yaml").exists() for i in r.added))

    side = read_sidecar(seeds / r.added[0].name)
    check("원본 이름을 남김", bool(side.get("source")), str(side.get("source")))
    check("테마도 남김", bool(side.get("theme")), str(side.get("theme")))

    print("\n[같은 폴더를 다시 가리켜도 안전]")
    before = sorted(p.name for p in seeds.glob("*"))
    r2 = import_folder(src, seeds)
    after = sorted(p.name for p in seeds.glob("*"))
    check("새로 들어온 것 없음", not r2.added, f"{len(r2.added)}장")
    check("폴더가 그대로", before == after)
    check("이유를 '이미 들여온 그림' 으로 알려줌",
          all(s.reason == "이미 들여온 그림" for s in r2.skipped),
          str({s.reason for s in r2.skipped}))

    print("\n[새로 받은 것만 추가]")
    make_image(src / "user_first_person_view_walking_an_endless_library_catwalk_ee55.png", 9)
    r3 = import_folder(src, seeds)
    check("딱 1장만 추가", len(r3.added) == 1, f"{len(r3.added)}장")
    check("도서관으로 분류", r3.added and r3.added[0].theme == "library",
          r3.added[0].theme if r3.added else "-")

    print("\n[같은 프롬프트의 비슷한 그림은 한 장만]")
    twin = src / MJ["downhill"].replace("aa11", "aa12")
    shutil.copy2(src / MJ["downhill"], twin)
    r4 = import_folder(src, seeds)
    check("쌍둥이는 안 들어옴", not r4.added, str([i.name for i in r4.added]))

    print("\n[서명이 다르면 비슷해 보여도 들여온다]")
    # 그림은 거의 같아도 프롬프트가 다르면 다른 장면이다. 버리면 안 된다.
    # 밝은 하늘 풍경끼리는 장면이 전혀 달라도 dhash 가 가깝게 나온다.
    other = src / "user_first_person_view_crossing_a_rope_bridge_over_a_cloud_sea_ff66.png"
    twin_img = Image.open(src / MJ["downhill"]).convert("RGB")
    twin_img.putpixel((0, 0), (1, 2, 3))       # 내용 해시만 달라지게
    twin_img.save(other)
    r5 = import_folder(src, seeds)
    check("다른 프롬프트면 들어옴", len(r5.added) == 1, str([i.name for i in r5.added]))
    check("부유섬으로 분류", r5.added and r5.added[0].theme == "sky_islands",
          r5.added[0].theme if r5.added else "-")

    print("\n[규격 미달은 이유를 붙여 건너뛴다]")
    make_image(src / "user_a_wide_landscape_gg77.png", 3, size=(1920, 1080))
    make_image(src / "user_a_tiny_thumbnail_hh88.png", 4, size=(320, 570))
    r6 = import_folder(src, seeds)
    reasons = " / ".join(s.reason for s in r6.skipped if "9:16" in s.reason
                         or "해상도" in s.reason)
    check("가로·저해상도 둘 다 걸러짐", reasons.count("—") + reasons.count("해상도") >= 2,
          reasons)

    print("\n[예전에 curate 로 넣은 것 — 원본 폴더를 다시 가리켜도 안전]")
    # intake 가 생기기 전에 넣은 시드는 인덱스에 없다. 그대로 두고 원래
    # 미드저니 폴더를 가리키면 272장이 통째로 다시 들어온다.
    old_src, old_seeds = TMP / "old_dl", TMP / "old_seeds"
    (old_seeds / "_used").mkdir(parents=True, exist_ok=True)
    old_names = [f"user_first_person_view_cycling_downhill_scene_{i}_zz{i}{i}.png"
                 for i in range(5)]
    for i, name in enumerate(old_names):
        make_image(old_src / name, 100 + i)
    # curate 가 하던 일: shutil.copy2 로 복사하고 이름만 바꾼다 (인덱스 없음)
    shutil.copy2(old_src / old_names[0], old_seeds / "downhill_01.png")
    shutil.copy2(old_src / old_names[1], old_seeds / "downhill_02.png")
    shutil.copy2(old_src / old_names[2], old_seeds / "_used" / "downhill_03.png")

    r_old = import_folder(old_src, old_seeds)
    check("기존 시드를 인덱스에 등록", r_old.bootstrapped == 3, f"{r_old.bootstrapped}장")
    check("이미 있는 3장은 안 들어옴", len(r_old.added) == 2,
          str([i.name for i in r_old.added]))
    check("이유가 '이미 들여온 그림'",
          all(s.reason == "이미 들여온 그림" for s in r_old.skipped),
          str({s.reason for s in r_old.skipped}))
    # _used/ 를 빼먹으면 이미 올린 영상의 시드가 다시 들어온다
    back = [i for i in r_old.added if i.source == old_names[2]]
    check("이미 올린(_used) 시드도 안 돌아옴", not back, str([i.source for i in back]))
    # _used/downhill_03 과 번호가 겹치면 나중에 shutil.move 가 덮어쓴다
    check("_used 의 번호를 피해 이름 붙임",
          all(i.name != "downhill_03.png" for i in r_old.added),
          str([i.name for i in r_old.added]))

    r_old2 = import_folder(old_src, old_seeds)
    check("두 번째는 아무것도 안 들어옴", not r_old2.added)
    check("이미 등록했으므로 다시 등록 안 함", r_old2.bootstrapped == 0,
          f"{r_old2.bootstrapped}장")

    print("\n[다시 분류]")
    in_seeds = len([p for p in seeds.glob("*")
                    if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")])
    r7 = reclassify(seeds)
    check("전부 다시 살펴봄", r7.scanned == in_seeds, f"{r7.scanned}/{in_seeds}장")
    check("멀쩡한 것은 이름을 안 바꿈", not r7.renamed, str(r7.renamed))

    # 사용자가 고쳐 둔 제목은 다시 분류해도 살아남아야 한다
    target = seeds / r.added[0].name
    yaml = target.with_suffix(".yaml")
    yaml.write_text(
        yaml.read_text(encoding="utf-8").replace(
            f"title:  {read_sidecar(target)['title']}", "title:  내가 고친 제목"),
        encoding="utf-8")
    reclassify(seeds)
    check("직접 고친 제목이 안 지워짐",
          read_sidecar(target).get("title") == "내가 고친 제목",
          read_sidecar(target).get("title", ""))

    # 사이드카를 지워도 다시 만들어져야 한다
    yaml.unlink()
    r8 = reclassify(seeds)
    check("지운 사이드카를 다시 만듦", yaml.exists())
    check("무엇을 고쳤는지 알려줌", target.name in r8.fixed, str(r8.fixed))


# ══════════════════════════════════════════════════════════════════════
def music_tests() -> None:
    from pipeline import music
    from pipeline.curate import THEMES

    print("\n[배경음악 자동 선택]")
    missing = [k for k, _l, _w in THEMES if k not in music.MOOD_OF]
    check("모든 테마에 분위기가 정해져 있음", not missing, str(missing))

    md = TMP / "music"
    for mood in ("bright", "epic"):
        (md / mood).mkdir(parents=True, exist_ok=True)
    check("곡이 없으면 None", music.pick("downhill", "seed_01", md) is None)
    check("비었다고 알려줌", "비어 있습니다" in music.describe(md), music.describe(md))

    for i in range(3):
        (md / "bright" / f"ride_{i}.mp3").write_bytes(b"\0" * 32)
    (md / "epic" / "flight.mp3").write_bytes(b"\0" * 32)

    t = music.pick("downhill", "downhill_01", md)
    check("다운힐은 bright 에서 고름", t is not None and t.mood == "bright",
          t.mood if t else "-")
    t2 = music.pick("dragon", "dragon_01", md)
    check("용은 epic 에서 고름", t2 is not None and t2.mood == "epic",
          t2.mood if t2 else "-")

    again = music.pick("downhill", "downhill_01", md)
    check("같은 시드는 항상 같은 곡", again is not None and again.path == t.path)
    picks = {music.pick("downhill", f"downhill_{n:02d}", md).path.name
             for n in range(1, 12)}
    check("시드가 다르면 곡이 갈림", len(picks) >= 2, str(sorted(picks)))

    # 분위기 폴더가 비면 any 로 떨어져야 한다. 무음으로 나가면 안 된다.
    (md / "any").mkdir(parents=True, exist_ok=True)
    (md / "any" / "fallback.mp3").write_bytes(b"\0" * 32)
    t3 = music.pick("library", "library_01", md)      # calm 폴더가 없다
    check("분위기 폴더가 없으면 any 로", t3 is not None and t3.mood == "any",
          t3.mood if t3 else "-")

    check("상태를 한 줄로 알려줌", "밝고 상쾌 3곡" in music.describe(md),
          music.describe(md))


def stitch_audio_tests() -> None:
    from pipeline.stitcher import _audio_args

    print("\n[음악 붙이기]")
    track = TMP / "music" / "bright" / "ride_0.mp3"
    args, mapping, graph = _audio_args("file", str(track), 4, total=30.0)
    check("-stream_loop 으로 짧은 곡도 채움", "-stream_loop" in args)
    # 무한 반복 입력을 필터그래프에 물리면 ffmpeg 메모리가 GB 단위로 불어나
    # 끝나지 않는다. -t 로 길이를 못 박아야 한다. 실제로 한 번 멈췄다.
    check("-t 로 길이를 못 박음", "-t" in args and args[args.index("-t") + 1] == "30.000",
          " ".join(args))
    check("-t 가 -i 앞에 옴", args.index("-t") < args.index("-i"), " ".join(args))
    check("라우드니스를 맞춤", "loudnorm" in graph, graph[:60])
    check("앞에 페이드인", "afade=t=in" in graph)
    check("뒤에 페이드아웃", "afade=t=out" in graph)
    check("페이드아웃이 영상 끝에 맞음", "st=28.40" in graph, graph[-60:])
    check("필터 출력을 매핑", mapping == ["-map", "[aout]"], str(mapping))

    # 3초짜리 영상에 1.6초 페이드아웃을 넣으면 소리가 거의 안 들린다
    _a, _m, short = _audio_args("file", str(track), 1, total=2.0)
    check("너무 짧으면 페이드아웃 생략", "afade=t=out" not in short)

    # 길이를 못 재면 필터를 걸지 않는다. 무한 입력 + 필터 = 멈춤.
    a3, m3, g3 = _audio_args("file", str(track), 2, total=0)
    check("길이를 모르면 필터 없이 예전 방식", g3 == "" and m3 == ["-map", "2:a"],
          f"{g3!r} {m3}")
    check("길이를 모르면 -t 도 없음", "-t" not in a3, " ".join(a3))

    args2, map2, graph2 = _audio_args("silent", None, 3)
    check("무음은 anullsrc", any("anullsrc" in a for a in args2))
    check("무음은 필터 없음", graph2 == "")
    check("무음도 트랙을 매핑", map2 == ["-map", "3:a"], str(map2))


# ══════════════════════════════════════════════════════════════════════
def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    try:
        intake_tests()
        music_tests()
        stitch_audio_tests()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)

    print("\n" + "═" * 62)
    print(f" 통과 {len(PASSED)} / 실패 {len(FAILED)}")
    print("═" * 62)
    if FAILED:
        for name in FAILED:
            print(f"  ✗ {name}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
