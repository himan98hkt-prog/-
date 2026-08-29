"""채널을 굴리는 데 필요한 것들 — 성적표 · 배치 · 토큰 · 영상 꾸미기.

    python tests/test_growth.py

만들고 올리는 것까지는 되는데 **뭐가 통했는지 모르면** 계속 감으로 시드를
고르게 된다. 여기 있는 것들은 그 고리를 닫기 위한 장치다.

  1. 성적표     조회수를 끌어와 테마·음악·움직임별로 묶는다
  2. 배치       일주일치를 미리 만들어 둔다. 한 편 실패해도 안 멈춘다
  3. 토큰       인스타 장기 토큰은 60일이면 조용히 죽는다. 미리 센다
  4. 훅 자막    첫 3초에 이탈이 결정되는데 훅이 영상 안에 없었다
  5. 무한 루프  끝을 첫 장면으로 이어 붙인다. 비용 0
  6. 채널 룩    색보정 · 로고

ffmpeg 로 진짜 파일을 만들고, 네트워크는 가짜로 세운다. 비용 $0.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_growth"


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(name)
    print(f"  {'OK ' if condition else 'X  '} {name}" + (f"  — {detail}" if detail else ""))


def clip(path: Path, *, seconds: float = 3.0, fps: int = 25, seed: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi",
         "-i", f"gradients=size=270x480:rate={fps}:duration={seconds}:speed=0.05:n={3 + seed}",
         "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
         "-r", str(fps), "-y", str(path)],
        check=True, capture_output=True)
    return path


def frame(video: Path, index: int, dest: Path) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(video),
                    "-vf", f"select=eq(n\\,{index})", "-vsync", "0",
                    "-frames:v", "1", "-y", str(dest)], check=True, capture_output=True)
    return dest


def frames_in(path: Path) -> int:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return int(out.stdout.strip().rstrip(","))


def rmse(a: Path, b: Path) -> float:
    from PIL import Image, ImageChops
    d = ImageChops.difference(Image.open(a).convert("RGB"),
                              Image.open(b).convert("RGB")).convert("L")
    px = list(d.getdata())
    return math.sqrt(sum(v * v for v in px) / len(px))


# ══════════════════════════════════════════════════════════════════════
#  1. 훅 자막 — 첫 3초
# ══════════════════════════════════════════════════════════════════════
def hook_tests() -> None:
    print("\n[훅 자막] 훅이 영상 안에 들어간다")
    from pipeline import look
    from pipeline.stitcher import stitch

    d = TMP / "hook"
    a, b = clip(d / "a.mp4", seed=0), clip(d / "b.mp4", seed=1)
    font = look.find_font()
    check("한글 폰트를 찾는다", font is not None, str(font))
    if font is None:
        return

    # 화면 밖으로 나가지 않게 줄을 나눈다. 이걸 안 하면 양쪽이 잘린다.
    #
    # **줄이 몇 개로 나뉘는지는 검사하지 않는다.** 폰트마다 글자 폭이 달라서
    # 같은 문구가 어디서는 한 줄, 어디서는 두 줄이 된다. 실제로 이 검사가
    # CI 에서만 깨졌다. 지켜야 하는 성질은 그게 아니라 이 둘이다.
    #
    #   1) 모든 줄이 정해진 폭 안에 들어온다  (안 그러면 화면 밖으로 잘린다)
    #   2) 글자를 잃지 않는다                (줄여도 내용이 사라지면 안 된다)
    def fits(text: str, width: int, base: int = 34) -> tuple[bool, bool, int, list]:
        lines, size = look.wrap(text, font=font, size=base, max_width=width)
        inside = all(look.measure(ln, font, size) <= width for ln in lines)
        kept = " ".join(lines).split() == text.split()
        return inside, kept, size, lines

    hook_text = "이 길 끝에 뭐가 있을까"
    inside, kept, size, lines = fits(hook_text, round(270 * 0.86))
    check("모든 줄이 폭 안에 들어온다", inside, f"{size}px {lines}")
    check("글자를 잃지 않는다", kept, str(lines))

    # 좁게 잡으면 어떤 폰트에서도 한 줄로는 못 담는다 — 여기서는 나뉘어야 한다.
    narrow = look.measure("이 길", font, 34)
    _, _, _, tight = fits(hook_text, narrow)
    check("한 줄에 안 들어가면 줄을 나눈다", len(tight) >= 2,
          f"폭 {narrow}px -> {tight}")

    long_text = "비 내리는 네온 골목을 끝없이 달리다 그리고 조금 더 멀리까지 계속"
    inside2, kept2, size2, lines2 = fits(long_text, round(270 * 0.86))
    check("더 길어도 폭 안에 들어온다", inside2, f"{size2}px {lines2}")
    check("두 줄을 넘기지 않는다", len(lines2) <= 2, str(len(lines2)))
    check("두 줄로 안 되면 글자를 줄인다", size2 <= size, f"{size} -> {size2}px")
    check("긴 문구도 글자를 잃지 않는다", kept2, str(lines2))

    # 아주 좁아도 죽지 않고 최소 크기에서 멈춘다
    _, _, tiny, _ = fits(long_text, 20)
    check("아무리 좁아도 멈춘다", tiny >= 14, f"{tiny}px")
    check("빈 문구는 빈 결과", look.wrap("", font=font, size=34, max_width=200)[0] == [])

    check("폰트가 없으면 자막을 건너뛴다",
          look.hook_filter("훅", seconds=2, height=480, font=None) == "")
    check("문구가 비면 건너뛴다",
          look.hook_filter("", seconds=2, height=480, font=font) == "")
    check("시간이 0 이면 건너뛴다",
          look.hook_filter("훅", seconds=0, height=480, font=font) == "")

    # 콜론·작은따옴표가 들어가도 필터그래프가 안 깨진다
    tricky = look.hook_filter("여기: 그리고 'ㅋ' 100%", seconds=2, height=480,
                              font=font, width=270)
    check("특수문자를 감싼다", "\\:" in tricky and "\\'" in tricky and "\\%" in tricky)

    plain = stitch([a, b], d / "plain.mp4", width=270, height=480, fps="auto",
                   crf=20, crossfade=0.3, transition="fade", audio="silent")
    styled = stitch([a, b], d / "hook.mp4", width=270, height=480, fps="auto",
                    crf=20, crossfade=0.3, transition="fade", audio="silent",
                    hook="이 길 끝에 뭐가 있을까", hook_seconds=2.0, hook_font=font)
    check("길이는 그대로", abs(plain.duration - styled.duration) < 0.1,
          f"{plain.duration:.2f} vs {styled.duration:.2f}")

    # 자막이 있는 구간과 없는 구간이 실제로 달라야 한다
    p1 = frame(d / "plain.mp4", 25, d / "p1.png")
    h1 = frame(d / "hook.mp4", 25, d / "h1.png")
    h2 = frame(d / "hook.mp4", frames_in(d / "hook.mp4") - 3, d / "h2.png")
    p2 = frame(d / "plain.mp4", frames_in(d / "plain.mp4") - 3, d / "p2.png")
    check("1초 시점에는 자막이 있다", rmse(p1, h1) > 3, f"차이 {rmse(p1, h1):.1f}")
    check("끝에는 자막이 사라진다", rmse(p2, h2) < 3, f"차이 {rmse(p2, h2):.1f}")


# ══════════════════════════════════════════════════════════════════════
#  2. 무한 루프 · 채널 룩
# ══════════════════════════════════════════════════════════════════════
def look_tests() -> None:
    print("\n[무한 루프] 끝과 처음이 같은 장면이 된다")
    from pipeline import look
    from pipeline.ffmpeg_util import FFmpegError
    from pipeline.stitcher import stitch

    d = TMP / "look"
    a, b = clip(d / "a.mp4", seed=0), clip(d / "b.mp4", seed=1)
    base = stitch([a, b], d / "base.mp4", width=270, height=480, fps="auto",
                  crf=20, crossfade=0.3, transition="fade", audio="silent")

    def seam(path: Path, tag: str) -> float:
        n = frames_in(path)
        return rmse(frame(path, 0, d / f"{tag}_A.png"),
                    frame(path, n - 1, d / f"{tag}_B.png"))

    before = seam(d / "base.mp4", "base")
    shutil.copy(d / "base.mp4", d / "loop.mp4")
    after_dur = look.make_seamless(d / "loop.mp4", overlap=0.6, crf=20, fps=25)
    after = seam(d / "loop.mp4", "loop")

    check("이음매가 크게 줄어든다", after < before / 3,
          f"첫↔마지막 프레임 차이 {before:.1f} -> {after:.1f}")
    check("겹친 만큼 짧아진다", abs((base.duration - after_dur) - 0.6) < 0.15,
          f"{base.duration:.2f} -> {after_dur:.2f}")

    # 겹침이 영상보다 크면 만들지 않는다 — 조용히 이상한 결과를 내는 것보다 낫다
    shutil.copy(d / "base.mp4", d / "bad.mp4")
    try:
        look.make_seamless(d / "bad.mp4", overlap=99, crf=20, fps=25)
        raised = False
    except FFmpegError:
        raised = True
    check("겹침이 너무 크면 막는다", raised)

    print("\n[채널 룩] 색보정과 로고")
    check("프리셋이 다 있다", set(look.GRADES) == {"none", "warm", "cool", "cinema"})
    check("none 은 필터가 없다", look.grade_filter("none") == "")
    check("모르는 이름도 필터가 없다", look.grade_filter("무지개") == "")
    check("cinema 는 필터가 있다", "eq=" in look.grade_filter("cinema"))

    graded = stitch([a, b], d / "graded.mp4", width=270, height=480, fps="auto",
                    crf=20, crossfade=0.3, transition="fade", audio="silent",
                    grade="cinema")
    g1 = frame(d / "graded.mp4", 25, d / "g1.png")
    p1 = frame(d / "base.mp4", 25, d / "p1.png")
    check("색보정이 실제로 먹는다", rmse(p1, g1) > 2, f"차이 {rmse(p1, g1):.1f}")
    check("색보정이 과하지 않다", rmse(p1, g1) < 40, f"차이 {rmse(p1, g1):.1f}")

    from PIL import Image, ImageDraw
    logo = d / "logo.png"
    im = Image.new("RGBA", (120, 40), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([0, 0, 119, 39], fill=(255, 255, 255, 255))
    im.save(logo)
    check("로고가 없으면 입력을 안 더한다", look.logo_inputs("") == [])
    check("없는 경로도 안 더한다", look.logo_inputs("/없는/로고.png") == [])
    check("있으면 입력을 더한다", look.logo_inputs(str(logo)) == ["-i", str(logo)])

    branded = stitch([a, b], d / "logo.mp4", width=270, height=480, fps="auto",
                     crf=20, crossfade=0.3, transition="fade", audio="silent",
                     logo=str(logo), logo_height=24, logo_margin=8, logo_opacity=0.9)
    check("로고를 넣어도 길이는 그대로",
          abs(branded.duration - base.duration) < 0.1)
    # 오른쪽 위 구석이 달라져야 한다
    from PIL import Image as I
    corner = lambda p: I.open(p).convert("RGB").crop((270 - 140, 0, 270, 40))  # noqa: E731
    f_plain = frame(d / "base.mp4", 25, d / "lp.png")
    f_logo = frame(d / "logo.mp4", 25, d / "ll.png")
    corner(f_plain).save(d / "cp.png")
    corner(f_logo).save(d / "cl.png")
    check("오른쪽 위에 로고가 있다", rmse(d / "cp.png", d / "cl.png") > 10,
          f"차이 {rmse(d / 'cp.png', d / 'cl.png'):.1f}")

    # 소리가 있어도 루프 처리가 소리를 잃지 않는다
    from pipeline.ffmpeg_util import has_audio
    song = d / "song.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=20", "-y", str(song)],
                   check=True, capture_output=True)
    with_sound = stitch([a, b], d / "snd.mp4", width=270, height=480, fps="auto",
                        crf=20, crossfade=0.3, transition="fade",
                        audio="file", audio_file=str(song))
    check("합성본에 소리가 있다", has_audio(with_sound.path))
    look.make_seamless(with_sound.path, overlap=0.5, crf=20, fps=25)
    check("루프 처리 뒤에도 소리가 남는다", has_audio(with_sound.path))

    check("설정 요약이 사람 말이다",
          look.describe({"hook_overlay": {"enabled": True, "seconds": 2.2},
                         "seamless_loop": {"enabled": True, "seconds": 0.6},
                         "look": {"grade": "cinema", "logo": "x.png"}})
          == "훅 자막 2.2초 · 무한 루프 0.6초 · 색보정 시네마 · 로고")
    check("아무것도 안 켰으면 '없음'", look.describe({}) == "없음")


# ══════════════════════════════════════════════════════════════════════
#  3. 성적표
# ══════════════════════════════════════════════════════════════════════
def stats_tests() -> None:
    print("\n[성적표] 무엇이 통했는지")
    from pipeline import motions
    from publish import insights

    runs = TMP / "runs"
    follow = next(m for m in motions.MOTIONS if m.key == "follow")
    rise = next(m for m in motions.MOTIONS if m.key == "rise")

    def make(name, theme, prompt, yt, ig, cost, *, grade="none", hook=False,
             loop=False, title="", metrics=True):
        d = runs / name
        d.mkdir(parents=True, exist_ok=True)
        state = {
            "seed_image": f"seeds/{theme}_x.png", "theme": theme,
            "cost_usd": cost, "grade": grade, "hook_burned": hook, "looped": loop,
            "content": {"title": title, "prompt": prompt},
            "published": {"youtube": {"ok": True, "id": f"yt_{name}"},
                          "instagram": {"ok": True, "id": f"ig_{name}"}},
        }
        if metrics:
            state["metrics"] = {"youtube": {"views": yt},
                                "instagram": {"views": ig}}
        (d / "state.json").write_text(json.dumps(state, ensure_ascii=False),
                                      encoding="utf-8")

    make("r1", "alley_bike", follow.prompt, 5200, 3100, 1.47,
         grade="cinema", hook=True, loop=True, title="골목")
    make("r2", "alley_bike", follow.prompt, 4100, 2400, 1.47,
         grade="cinema", hook=True, loop=True, title="밤 골목")
    make("r3", "ice", rise.prompt, 900, 400, 1.47, title="얼음")
    make("r4", "ice", rise.prompt, 1100, 500, 1.47, title="빙하")
    make("r5", "space", "직접 쓴 프롬프트", 300, 150, 1.47, title="우주")
    make("r6", "space", follow.prompt, 0, 0, 1.47, title="아직", metrics=False)

    yt, ig = insights.published_ids(runs)
    check("올린 영상의 id 를 모은다", len(yt) == 6 and len(ig) == 6,
          f"yt {len(yt)} ig {len(ig)}")
    check("run 으로 되짚을 수 있다", yt["yt_r1"] == "r1")

    s = insights.summarize(runs)
    check("성적을 읽은 것만 센다", s["videos"] == 5, f"{s['videos']}편")
    check("두 플랫폼 조회수를 합친다", s["total_views"] == 18150,
          str(s["total_views"]))
    check("조회 1,000회당 비용을 낸다",
          abs(s["cost_per_1k"] - round(1.47 * 5 / 18150 * 1000, 2)) < 0.01,
          f"${s['cost_per_1k']}")

    themes = {r["key"]: r for r in s["tables"]["theme"]}
    check("테마별로 묶는다", themes["alley_bike"]["videos"] == 2)
    check("평균을 낸다", themes["alley_bike"]["average"] == 7400,
          str(themes["alley_bike"]["average"]))
    check("잘된 것이 위로", s["tables"]["theme"][0]["key"] == "alley_bike")
    check("편수가 적으면 판단 보류로 표시",
          not themes["space"]["enough"] and themes["alley_bike"]["enough"])

    motion = {r["key"]: r for r in s["tables"]["motion"]}
    check("움직임 프리셋을 알아본다", "뒤에서 따라가기" in motion, str(list(motion)))
    check("직접 쓴 프롬프트는 따로 묶는다", "(직접 쓴 프롬프트)" in motion)
    hooks = {r["key"]: r for r in s["tables"]["hook"]}
    check("훅 자막 유무로도 묶는다",
          hooks["넣음"]["average"] > hooks["안 넣음"]["average"])
    check("음악 분위기로도 묶는다",
          {"도시 밤", "신비"} <= {r["key"] for r in s["tables"]["mood"]},
          str([r["key"] for r in s["tables"]["mood"]]))

    check("가장 많이 본 영상이 맨 위", s["best"][0]["title"] == "골목")
    text = insights.render(s)
    check("콘솔 표가 나온다", "성적표" in text and "테마" in text)
    check("판단 보류를 말로 알려준다", "판단 보류" in text)

    empty = insights.summarize(TMP / "없는폴더")
    check("빈 폴더도 안 죽는다", empty["videos"] == 0)
    check("빈 성적표는 무엇을 하라고 알려준다",
          "--refresh" in insights.render(empty))


# ══════════════════════════════════════════════════════════════════════
#  4. 인스타 토큰 — 60일 뒤 조용히 죽는 것
# ══════════════════════════════════════════════════════════════════════
def token_tests() -> None:
    print("\n[인스타 토큰] 만료 전에 알려준다")
    import types

    from publish import instagram

    real = instagram.requests
    now = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).timestamp()

    class Resp:
        def __init__(self, code, body):
            self.status_code, self._b, self.text = code, body, json.dumps(body)

        def json(self):
            return self._b

    def fake(expires, valid=True, code=200):
        mod = types.SimpleNamespace(
            RequestException=real.RequestException,
            get=lambda *a, **k: Resp(code, {"data": {
                "is_valid": valid, "expires_at": expires, "scopes": ["x"]}}))
        return mod

    try:
        instagram.requests = fake(int(now + 45 * 86400))
        st = instagram.token_status("TOK")
        check("남은 날짜를 센다", st["days_left"] in (44, 45), str(st["days_left"]))
        check("괜찮으면 ok", st["ok"] is True)

        instagram.requests = fake(int(now + 3 * 86400))
        check("얼마 안 남았을 때도 센다",
              instagram.token_status("TOK")["days_left"] in (2, 3))

        instagram.requests = fake(int(now - 86400))
        st = instagram.token_status("TOK")
        check("만료된 것을 안다", st["days_left"] < 0 and st["note"] == "만료됨",
              str(st))

        instagram.requests = fake(0)
        check("만료 없는 토큰도 있다",
              instagram.token_status("TOK")["days_left"] is None)

        instagram.requests = fake(0, code=400)
        st = instagram.token_status("TOK")
        check("거절당하면 이유를 말한다",
              st["ok"] is False and "만료" in st["reason"], str(st))
    finally:
        instagram.requests = real

    check("토큰이 없으면 그렇다고 한다",
          instagram.token_status("")["reason"] == "토큰이 없습니다.")

    # doctor 가 이걸 항목으로 보여주는지
    from pipeline import doctor
    src = Path(doctor.__file__).read_text(encoding="utf-8")
    check("doctor 가 유효기간을 점검한다", "_token_check" in src)
    check("연장하라고 안내한다", "60일 연장" in src)


# ══════════════════════════════════════════════════════════════════════
#  5. 배치 — 한 편 실패해도 안 멈춘다
# ══════════════════════════════════════════════════════════════════════
def batch_tests() -> None:
    print("\n[배치] 일주일치를 미리, 실패해도 안 멈춘다")
    import yaml
    from typer.testing import CliRunner

    sys.path.insert(0, str(ROOT / "tests"))
    import mock_provider
    import main as cli
    from PIL import Image
    from pipeline.providers.base import ProviderError

    work = TMP / "batch"
    (work / "seeds").mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(("aa", "bb", "cc")):
        Image.new("RGB", (1080, 1920), (20 + i * 30, 40, 80)).save(
            work / "seeds" / f"{name}.png")
        (work / "seeds" / f"{name}.yaml").write_text(
            f"title: 제목{i + 1}\nhook: 훅{i + 1}\n", encoding="utf-8")

    cfg = yaml.safe_load((ROOT / "tests" / "config.test.yaml").read_text(
        encoding="utf-8"))
    cfg["output"]["fps"] = "auto"
    cfg["output"]["audio"] = "silent"
    cfg["num_clips"] = 1
    cfg["upscale_between_clips"] = False
    (work / "cfg.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True),
                                   encoding="utf-8")

    # 두 번째 시드에서만 실패시킨다
    original = mock_provider.MockProvider.generate

    def flaky(self, req, dest):
        if "bb" in str(req.image.parent.parent.name) or getattr(
                self, "_fail_next", False):
            pass
        return original(self, req, dest)

    calls = {"n": 0}

    def sometimes(self, req, dest):
        calls["n"] += 1
        if calls["n"] == 2:
            raise ProviderError("일부러 낸 실패", retryable=False, billed=False)
        return original(self, req, dest)

    keep_runs = cli.RUNS_DIR
    mock_provider.MockProvider.generate = sometimes
    try:
        cli.RUNS_DIR = work / "runs"
        res = CliRunner().invoke(cli.app, [
            "batch", "-n", "3", "--seeds", str(work / "seeds"),
            "-c", str(work / "cfg.yaml"), "-y"])
    finally:
        mock_provider.MockProvider.generate = original
        cli.RUNS_DIR = keep_runs

    out = res.output
    check("끝까지 돌린다", res.exit_code == 0, f"exit {res.exit_code}")
    check("실패한 편이 있어도 멈추지 않는다", "다음 편으로 넘어갑니다" in out)
    check("요약을 준다", "2편 완성 · 1편 실패" in out,
          [l for l in out.splitlines() if "완성" in l][:1])
    check("총 비용을 합친다", "총 $" in out)

    made = sorted(p.name for p in (work / "runs").iterdir()
                  if (p / "final.mp4").exists())
    check("성공한 것만 결과물이 있다", len(made) == 2, str(len(made)))
    used = {p.name for p in (work / "seeds" / "_used").iterdir()}
    left = {p.name for p in (work / "seeds").iterdir() if p.is_file()}
    check("성공한 시드만 치운다", len(used) == 4, str(sorted(used)))
    check("실패한 시드는 남겨 다시 쓴다", len(left) == 2, str(sorted(left)))


# ══════════════════════════════════════════════════════════════════════
def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    try:
        hook_tests()
        look_tests()
        stats_tests()
        token_tests()
        batch_tests()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)

    print("\n" + "=" * 60)
    print(f"통과 {len(PASSED)} · 실패 {len(FAILED)}")
    if FAILED:
        for name in FAILED:
            print(f"  X {name}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
