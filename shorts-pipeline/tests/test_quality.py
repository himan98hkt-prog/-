"""돈이 새거나 화면이 떨리던 자리를 붙잡아 두는 검사.

    python tests/test_quality.py

여기 있는 것은 전부 **실제로 겪은 증상**에서 왔다.

  1. 영상이 미세하게 떨렸다        — 25fps 소스를 30 으로 올려 프레임을 복제했다
  2. 값이 두 번 나갔다             — 폴링 타임아웃에 같은 클립을 새로 제출했다
  3. 안 쓴 돈이 장부에 찍혔다      — 접수도 안 된 실패(401/422)를 과금으로 셌다
  4. 쓴 돈이 장부에서 사라졌다     — 실패 후 부분 합성이 비용을 0 으로 기록했다
  5. 깨진 클립을 완성으로 봤다     — 크기만 보고 재생 가능 여부를 안 봤다
  6. 새 기본값이 안 닿았다         — 사용자 config 에 없는 키는 추가되지 않았다

ffmpeg 로 진짜 파일을 만들어 검사한다. API 호출은 0회, 비용은 $0 이다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_quality"


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(name)
    print(f"  {'✓' if condition else '✗'} {name}" + (f"  — {detail}" if detail else ""))


def make_clip(path: Path, *, fps: int, seconds: float = 2.0, hue: int = 0) -> Path:
    """지정한 프레임률의 진짜 mp4. 클립마다 색을 달리해 내용이 겹치지 않게 한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi",
         "-i", f"testsrc2=size=270x480:rate={fps}:duration={seconds}",
         "-vf", f"hue=h={hue}", "-c:v", "libx264", "-crf", "20",
         "-pix_fmt", "yuv420p", "-r", str(fps), "-y", str(path)],
        check=True, capture_output=True,
    )
    return path


def duplicated_frames(clip: Path, target_fps: int) -> tuple[int, int]:
    """`fps=N` 필터를 통과시켰을 때 (전체 프레임, 복제된 프레임).

    인코딩 뒤에는 못 센다 — 복제 프레임도 압축 결과가 미세하게 달라진다.
    그래서 필터 출력 원본(rawvideo)에서 센다.
    """
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-vf", f"fps={target_fps}",
         "-f", "framemd5", "-c:v", "rawvideo", "-"],
        capture_output=True, text=True, check=True,
    )
    hashes = [line.rsplit(",", 1)[-1].strip()
              for line in proc.stdout.splitlines() if line and not line.startswith("#")]
    return len(hashes), len(hashes) - len(set(hashes))


# ══════════════════════════════════════════════════════════════════════
#  1. 프레임률 — 화면이 떨리던 원인
# ══════════════════════════════════════════════════════════════════════
def fps_tests() -> None:
    print("\n[프레임률] 25fps 소스를 30 으로 올리면 안 된다")
    from pipeline.ffmpeg_util import fps_of
    from pipeline.stitcher import FALLBACK_FPS, resolve_fps, stitch

    d = TMP / "fps"
    a = make_clip(d / "a.mp4", fps=25, hue=0)
    b = make_clip(d / "b.mp4", fps=25, hue=90)

    check("ffprobe 로 프레임률을 읽는다", fps_of(a) == 25.0, str(fps_of(a)))

    # 증상 자체를 먼저 재현한다. 이 숫자가 '떨림' 의 정체다.
    total, dup = duplicated_frames(a, 30)
    check("25 -> 30 은 프레임을 복제한다", dup > 0, f"{total}장 중 {dup}장 복제")
    check("복제 비율이 1/6 이다", abs(dup / total - 1 / 6) < 0.02,
          f"{dup}/{total}")
    total, dup = duplicated_frames(a, 25)
    check("25 -> 25 는 복제가 없다", dup == 0, f"{total}장 중 {dup}장")

    check("auto 는 소스 프레임률을 쓴다", resolve_fps([a, b], "auto") == 25)
    check("숫자를 주면 그대로 쓴다", resolve_fps([a, b], 30) == 30)
    check("문자열 숫자도 받는다", resolve_fps([a, b], "24") == 24)
    check("이상한 값이면 기본값", resolve_fps([a, b], "몰라") == FALLBACK_FPS)
    check("클립이 없으면 기본값", resolve_fps([], "auto") == FALLBACK_FPS)

    # 섞여 있으면 높은 쪽. 낮추면 있던 프레임을 버리게 된다.
    c = make_clip(d / "c.mp4", fps=30, hue=180)
    check("프레임률이 섞이면 높은 쪽", resolve_fps([a, c], "auto") == 30)

    # 29.97 같은 값은 30 으로 붙인다.
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi",
         "-i", "testsrc2=size=270x480:rate=30000/1001:duration=2",
         "-c:v", "libx264", "-crf", "20", "-y", str(d / "ntsc.mp4")],
        check=True, capture_output=True)
    check("29.97 은 30 으로 붙인다", resolve_fps([d / "ntsc.mp4"], "auto") == 30,
          f"{fps_of(d / 'ntsc.mp4'):.3f}")

    # 합성 전체를 돌려 결과 파일의 프레임률을 직접 확인한다.
    out = stitch([a, b], d / "auto.mp4", width=270, height=480, fps="auto",
                 crf=20, crossfade=0.3, transition="fade", audio="silent")
    check("합성 결과가 25fps 다", out.fps == 25 and round(fps_of(out.path)) == 25,
          f"{fps_of(out.path)}")
    check("결과에 프레임률이 남는다", out.fps == 25)

    out30 = stitch([a, b], d / "forced.mp4", width=270, height=480, fps=30,
                   crf=20, crossfade=0.3, transition="fade", audio="silent")
    check("숫자로 강제하면 그 값이 된다", round(fps_of(out30.path)) == 30)
    # 같은 소스인데 프레임 수가 늘었다 = 없던 프레임을 만들어 넣었다는 뜻.
    check("강제하면 프레임 수가 늘어난다",
          frames_in(out30.path) > frames_in(out.path),
          f"{frames_in(out.path)} -> {frames_in(out30.path)}")


def frames_in(path: Path) -> int:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return int(proc.stdout.strip().rstrip(","))


# ══════════════════════════════════════════════════════════════════════
#  2·3. 과금 — 두 번 내지 않기, 안 쓴 돈 세지 않기
# ══════════════════════════════════════════════════════════════════════
def billing_tests() -> None:
    print("\n[과금] 같은 클립 값을 두 번 내지 않는다")
    from pipeline.providers.base import DEFAULT_TIMEOUT, ProviderError, VideoProvider

    check("기본 대기 한도가 10분보다 길다", DEFAULT_TIMEOUT >= 1800,
          f"{DEFAULT_TIMEOUT / 60:.0f}분")

    class Never(VideoProvider):
        """영원히 안 끝나는 작업. 폴링 타임아웃 경로만 본다."""
        def generate(self, req, dest): raise NotImplementedError
        def upscale(self, image, dest, endpoint): raise NotImplementedError

    p = Never("x", poll_interval=0.01, timeout=0.05)
    try:
        p._poll(lambda: (False, {}), label="테스트 작업")
        raised = None
    except ProviderError as exc:
        raised = exc
    check("한도를 넘기면 멈춘다", raised is not None)
    check("타임아웃은 재시도하지 않는다", raised is not None and not raised.retryable,
          "재제출하면 먼저 낸 작업 값까지 두 번 나간다")
    check("타임아웃은 과금으로 본다", raised is not None and raised.billed is True)
    check("무엇을 해야 하는지 알려준다",
          raised is not None and "두 번" in str(raised))

    print("\n[과금] 접수도 안 된 실패는 돈이 안 나갔다")
    check("기본은 '알 수 없음'", ProviderError("x").billed is None)
    check("접수 실패를 표시할 수 있다", ProviderError("x", billed=False).billed is False)
    check("job_id 를 들고 다닌다", ProviderError("x", job_id="j1").job_id == "j1")

    from pipeline.config import load_config
    from pipeline.generator import GenerationStats, generate_clip
    from pipeline.runlog import Run

    cfg = load_config(ROOT / "tests" / "config.test.yaml")
    run = Run.create(TMP / "runs", "bill")

    class Rejecting(VideoProvider):
        """401 처럼 접수 자체가 거절되는 provider."""
        def __init__(self, billed):
            super().__init__("x")
            self.billed, self.calls = billed, 0
        def generate(self, req, dest):
            self.calls += 1
            raise ProviderError("fal HTTP 401", retryable=False, billed=self.billed)
        def upscale(self, image, dest, endpoint): raise NotImplementedError

    img = TMP / "seed.png"
    img.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=blue:s=270x480:d=1", "-frames:v", "1",
                    "-y", str(img)], check=True, capture_output=True)

    stats = GenerationStats()
    try:
        generate_clip(Rejecting(False), cfg, run, stats, index=1,
                      image=img, prompt="p")
    except ProviderError:
        pass
    check("접수 실패는 비용에 안 넣는다", stats.clip_calls == 0, f"{stats.clip_calls}회")

    stats = GenerationStats()
    try:
        generate_clip(Rejecting(True), cfg, run, stats, index=1,
                      image=img, prompt="p")
    except ProviderError:
        pass
    check("접수된 실패는 비용에 넣는다", stats.clip_calls == 1, f"{stats.clip_calls}회")

    stats = GenerationStats()
    try:
        generate_clip(Rejecting(None), cfg, run, stats, index=1,
                      image=img, prompt="p")
    except ProviderError:
        pass
    check("알 수 없으면 보수적으로 넣는다", stats.clip_calls == 1, f"{stats.clip_calls}회")


# ══════════════════════════════════════════════════════════════════════
#  4. 실패한 실행의 비용이 장부에서 사라지지 않는다
# ══════════════════════════════════════════════════════════════════════
def ledger_tests() -> None:
    print("\n[장부] 실패해도 나간 돈은 기록된다")
    import main as cli
    from pipeline.runlog import Run

    run = Run.create(TMP / "runs", "ledger")
    run.log("clip.done", index=1)
    run.log("clip.done", index=2)
    run.log("upscale.done", index=1)
    run.log("clip.attempt_failed", index=3, billed=True)
    run.log("clip.attempt_failed", index=3, billed=False)   # 401 — 돈 안 나감
    run.log("clip.attempt_failed", index=3)                 # 알 수 없음 — 센다

    stats = cli._stats_from_log(run)
    check("성공+과금된 실패를 센다", stats.clip_calls == 4, f"{stats.clip_calls}회")
    check("접수 실패는 빼고 센다", stats.clip_calls == 4,
          "성공 2 + 과금된 실패 1 + 알 수 없음 1")
    check("업스케일도 센다", stats.upscale_calls == 1, f"{stats.upscale_calls}회")

    empty = Run.create(TMP / "runs", "empty")
    check("로그가 없으면 0", cli._stats_from_log(empty).clip_calls == 0)

    # 깨진 줄이 섞여도 죽지 않는다.
    run.log_path.open("a", encoding="utf-8").write("{깨진 줄\n")
    check("깨진 줄은 건너뛴다", cli._stats_from_log(run).clip_calls == 4)

    from pipeline.config import load_config
    from pipeline.costs import actual_cost
    cfg = load_config(ROOT / "tests" / "config.test.yaml")
    check("비용으로 환산된다", actual_cost(cfg, stats.clip_calls, stats.upscale_calls) > 0)


# ══════════════════════════════════════════════════════════════════════
#  5. 깨진 클립을 완성으로 보지 않는다
# ══════════════════════════════════════════════════════════════════════
def resume_tests() -> None:
    print("\n[이어하기] 받다 만 클립을 완성으로 보지 않는다")
    from pipeline.runlog import Run

    run = Run.create(TMP / "runs", "resume")
    make_clip(run.clip(1), fps=25, seconds=1)
    make_clip(run.clip(2), fps=25, seconds=1, hue=60)
    check("정상 두 개를 인정한다", run.completed_clips() == [1, 2])

    # 다운로드가 중간에 끊긴 파일 — 크기는 있지만 열리지 않는다.
    run.clip(3).write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200)
    check("열리지 않는 파일은 뺀다", run.completed_clips() == [1, 2],
          str(run.completed_clips()))

    run.clip(3).unlink()
    make_clip(run.clip(4), fps=25, seconds=1, hue=120)
    check("3번이 비면 4번도 안 센다", run.completed_clips() == [1, 2],
          "번호가 이어지는 데까지만 인정한다")

    make_clip(run.clip(3), fps=25, seconds=1, hue=200)
    check("3번이 채워지면 4번까지", run.completed_clips() == [1, 2, 3, 4])

    run.clip(1).write_bytes(b"")
    check("빈 파일이면 아무것도 못 이어받는다", run.completed_clips() == [])


# ══════════════════════════════════════════════════════════════════════
#  6. 새 기본값이 사용자 설정에 닿는다
# ══════════════════════════════════════════════════════════════════════
def configdiff_tests() -> None:
    print("\n[설정] 새 기본값이 실제로 닿는다")
    import yaml

    from pipeline import configdiff

    d = TMP / "cfg"
    d.mkdir(parents=True, exist_ok=True)
    cur, new = d / "config.yaml", d / "config.yaml.new"
    cur.write_text(
        "mode: chain\n"
        "model: kling_25_turbo_pro\n"
        "output:\n"
        "  width: 1080\n"
        "  fps: 30          # 왜 30 인지 적어둔 주석\n"
        "  hook_overlay:\n"
        "    enabled: false\n"
        "  seamless_loop:\n"
        "    enabled: false\n"
        "cost:\n"
        "  hard_cap_usd: 25.0\n"
        "providers:\n"
        "  fal:\n"
        "    models:\n"
        "      x:\n"
        "        fps: 999\n"
        "        enabled: true\n", encoding="utf-8")
    new.write_text(
        "mode: chain\n"
        "model: hailuo_23_pro\n"
        "poll_timeout_seconds: 1800\n"
        "output:\n"
        "  width: 1080\n"
        "  fps: auto\n"
        "  hook_overlay:\n"
        "    enabled: false\n"
        "  seamless_loop:\n"
        "    enabled: true\n"
        "cost:\n"
        "  hard_cap_usd: 25.0\n"
        "  monthly_cap_usd: 30\n", encoding="utf-8")

    changes = {c.key: c for c in configdiff.compare(cur, new)}
    check("output 안쪽 값도 비교한다", "output.fps" in changes)
    check("두 단계 안쪽도 비교한다", "output.seamless_loop.enabled" in changes,
          str(sorted(changes)))
    check("바뀔 값을 정확히 짚는다",
          changes["output.fps"].current == "30"
          and changes["output.fps"].incoming == "auto")
    check("없던 키도 알려준다", changes["poll_timeout_seconds"].current == "(없음)")
    check("깊이 묻힌 동명 키는 건드리지 않는다",
          all(not c.startswith("providers") for c in changes))

    applied = configdiff.apply(cur, {k: c.incoming for k, c in changes.items()})
    text = cur.read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)

    check("output.fps 가 실제로 바뀐다", parsed["output"]["fps"] == "auto")
    check("두 단계 안쪽도 바뀐다",
          parsed["output"]["seamless_loop"]["enabled"] is True)
    check("이름이 같은 옆 항목은 그대로",
          parsed["output"]["hook_overlay"]["enabled"] is False,
          "seamless_loop.enabled 와 이름이 같다")
    check("주석은 살아 있다", "왜 30 인지 적어둔 주석" in text)
    check("없던 맨 윗단 키는 새로 추가된다",
          parsed.get("poll_timeout_seconds") == 1800)
    check("없던 하위 키는 부모 블록 안에 들어간다",
          parsed["cost"].get("monthly_cap_usd") == 30,
          "cost: 블록 안에 끼워 넣는다")
    check("providers 안쪽 fps 는 그대로", parsed["providers"]["fal"]["models"]["x"]["fps"] == 999)
    check("providers 안쪽 enabled 도 그대로",
          parsed["providers"]["fal"]["models"]["x"]["enabled"] is True)
    check("적용 목록에 다 들어 있다",
          set(applied) == {"model", "output.fps", "output.seamless_loop.enabled",
                           "poll_timeout_seconds", "cost.monthly_cap_usd"},
          str(sorted(applied)))
    check("적용 뒤에는 알림이 사라진다", configdiff.compare(cur, new) == [])

    # 두 번 눌러도 같은 결과여야 한다.
    check("다시 눌러도 바뀌는 게 없다", configdiff.apply(cur, {"output.fps": "auto"}) == [])
    check("두 번 적용해도 그대로",
          configdiff.apply(cur, {k: c.incoming for k, c in changes.items()}) == [])

    # 실제 배포 설정에도 적용된다 — 여기서 놓치면 사용자에게 안 닿는다.
    real = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    check("기본 설정의 fps 가 auto 다", real["output"]["fps"] == "auto")
    check("기본 설정에 대기 한도가 있다", real.get("poll_timeout_seconds") == 1800)


# ══════════════════════════════════════════════════════════════════════
#  7. 값을 덜 쓰게 하는 장치들
# ══════════════════════════════════════════════════════════════════════
def saver_tests() -> None:
    print("\n[아끼기] 카메라 움직임 프리셋")
    from pipeline import motions

    presets = motions.as_list()
    check("프리셋이 여러 개 있다", len(presets) >= 6, f"{len(presets)}개")
    check("키가 겹치지 않는다", len({m["key"] for m in presets}) == len(presets))
    for m in presets:
        ok = all(x in m["prompt"] for x in ("no scene cut", "steady speed"))
        if not ok:
            check(f"{m['key']} 가 컷·속도를 못 박는다", False, m["prompt"])
            break
    else:
        check("모든 프리셋이 컷·속도를 못 박는다", True, f"{len(presets)}개 확인")
    check("설명이 한국어로 다 있다", all(m["note"] and m["label"] for m in presets))
    check("이름으로 찾을 수 있다", motions.get("follow").label == "뒤에서 따라가기")
    check("모르는 이름은 None", motions.get("없는거") is None)

    merged = motions.combine_negative("blur, text", "rise")
    check("공통 금지 사항을 지운다", "blur" in merged and "text" in merged)
    check("움직임별 금지 사항을 더한다", "descending" in merged, merged)
    dup = motions.merge_negative("blur, zoom out", "zoom out, text")
    check("중복은 한 번만", dup.count("zoom out") == 1, dup)
    check("모르는 움직임이면 그대로",
          motions.combine_negative("blur, text", "없는거") == "blur, text")

    print("\n[아끼기] 이 영상에서만 막을 것이 사이드카에 남는다")
    import yaml

    from pipeline.content import load_content
    from ui.server import save_meta

    d = TMP / "seeds"
    d.mkdir(parents=True, exist_ok=True)
    img = d / "alley_bike_01.png"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=gray:s=108x192:d=1", "-frames:v", "1",
                    "-y", str(img)], check=True, capture_output=True)
    (d / "alley_bike_01.yaml").write_text(
        "title: 옛 제목\ntheme: alley_bike\nsource: /somewhere/orig.png\n",
        encoding="utf-8")

    save_meta(img, title="새 제목", hook="훅", prompt="forward",
              negative="zoom out, blur")
    side = yaml.safe_load((d / "alley_bike_01.yaml").read_text(encoding="utf-8"))
    check("금지 사항이 저장된다", side["negative"] == "zoom out, blur")
    check("theme 은 그대로 살아 있다", side["theme"] == "alley_bike")
    check("source 도 살아 있다", side["source"] == "/somewhere/orig.png")
    check("읽어올 때도 잡힌다", load_content(img).negative == "zoom out, blur")

    save_meta(img, title="또", hook="", prompt="forward")
    side = yaml.safe_load((d / "alley_bike_01.yaml").read_text(encoding="utf-8"))
    check("비우면 줄 자체가 빠진다", "negative" not in side)

    print("\n[아끼기] 같은 시드를 두 번 만들지 않게")
    import ui.server as srv

    runs = TMP / "runs2"
    real = runs / "20260101_000000"
    (real / "clips").mkdir(parents=True)
    (real / "final.mp4").write_bytes(b"x")
    (real / "state.json").write_text(json.dumps({
        "seed_image": "seeds/dragon_b.png", "clips_done": 3}), encoding="utf-8")
    pv = runs / "20260101_010000"
    pv.mkdir(parents=True)
    (pv / "final.mp4").write_bytes(b"x")
    (pv / "state.json").write_text(json.dumps({
        "seed_image": "seeds/ice_c.png", "clips_done": 1, "preview": True}),
        encoding="utf-8")
    dead = runs / "20260101_020000"
    dead.mkdir(parents=True)
    (dead / "state.json").write_text(json.dumps({
        "seed_image": "seeds/coast_d.png"}), encoding="utf-8")
    scenes = runs / "20260101_030000"
    scenes.mkdir(parents=True)
    (scenes / "final.mp4").write_bytes(b"x")
    (scenes / "state.json").write_text(json.dumps({
        "seed_image": "seeds/a.png", "clips_done": 2,
        "scene_seeds": ["seeds/b.png", "seeds/c.png"]}), encoding="utf-8")

    keep = srv.RUNS
    try:
        srv.RUNS = runs
        used = srv.seeds_already_used()
    finally:
        srv.RUNS = keep

    check("만든 시드를 짚어낸다", used.get("dragon_b.png") == "20260101_000000")
    check("시험판은 '만들었다' 로 치지 않는다", "ice_c.png" not in used,
          "시험판 때문에 본편을 못 만들면 안 된다")
    check("클립도 못 만든 실행은 빼고", "coast_d.png" not in used)
    check("장면 전환의 장면들도 센다",
          used.get("b.png") == "20260101_030000" and "c.png" in used)

    print("\n[아끼기] 클립 하나만 다시 만들기")
    from pipeline.config import load_config
    from pipeline.runlog import Run
    import main as cli

    cfg = load_config(ROOT / "tests" / "config.test.yaml")
    run = Run.create(TMP / "runs3", "redo")
    run.input_image.write_bytes(b"seed")
    check("1번은 원본 이미지에서 출발",
          cli._redo_input(run, cfg, "chain", 1) == run.input_image)

    run.frame(1).write_bytes(b"f1")
    check("2번은 1번의 마지막 장면에서",
          cli._redo_input(run, cfg, "chain", 2) == run.frame(1))
    run.frame(1, upscaled=True).write_bytes(b"f1u")
    check("보정된 장면이 있으면 그쪽을",
          cli._redo_input(run, cfg, "chain", 2) == run.frame(1, upscaled=True))

    check("장면 전환은 그 장면의 시드에서",
          cli._redo_input(run, cfg, "montage", 2) == run.input_image)
    run.seed(2).write_bytes(b"s2")
    check("장면 시드가 있으면 그것을",
          cli._redo_input(run, cfg, "montage", 2) == run.seed(2))

    print("\n[아끼기] 싼 모델로 먼저 시험")
    real_cfg = load_config(ROOT / "config.yaml")
    pvc = real_cfg.preview_cfg
    check("시험판 설정이 있다", bool(pvc), str(pvc))
    check("시험판 모델이 존재한다",
          pvc.get("model") in real_cfg.provider_cfg.get("models", {}), str(pvc.get("model")))

    trial = load_config(ROOT / "config.yaml", model=pvc["model"],
                        clip_duration=int(pvc["clip_duration"]), num_clips=1)
    one = trial.model.cost_per_clip(trial.clip_duration, trial.usd_per_credit)
    from pipeline.costs import estimate as est
    full = est(real_cfg).subtotal
    check("시험판이 본편보다 훨씬 싸다", one < full / 3,
          f"시험 ${one:.2f} vs 본편 ${full:.2f}")
    check("시험판은 클립 하나다", trial.num_clips == 1)


# ══════════════════════════════════════════════════════════════════════
#  8. 이번 달 상한 — 하루 조금씩 서른 번을 막는다
# ══════════════════════════════════════════════════════════════════════
def budget_tests() -> None:
    print("\n[예산] 이번 달 상한")
    from datetime import date

    from pipeline import budget as bud
    from pipeline.config import load_config

    runs = TMP / "budget_runs"
    this_month = date.today().strftime("%Y%m")
    other = "202601" if this_month[-2:] != "01" else "202602"

    def run(name, cost):
        d = runs / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "state.json").write_text(json.dumps({"cost_usd": cost}), encoding="utf-8")

    run(f"{this_month}01_100000", 0.99)
    run(f"{this_month}02_100000", 0.99)
    run(f"{this_month}03_100000", 0)          # 안 쓴 실행은 안 센다
    run(f"{other}15_100000", 40.0)            # 지난달은 안 센다
    (runs / "이상한폴더").mkdir(parents=True, exist_ok=True)
    (runs / f"{this_month}04_100000").mkdir(parents=True, exist_ok=True)  # state 없음

    spent, videos = bud.spent_in(runs)
    check("이번 달 것만 더한다", abs(spent - 1.98) < 0.001, f"${spent}")
    check("편수도 센다", videos == 2, str(videos))
    check("비용 0 인 실행은 빼고", videos == 2, "실패해서 안 쓴 실행")
    check("지난달은 안 센다", spent < 40, f"${spent}")
    check("이상한 폴더 이름은 건너뛴다", spent > 0)
    check("없는 폴더는 0", bud.spent_in(TMP / "없는폴더") == (0.0, 0))

    cfg = load_config(ROOT / "tests" / "config.test.yaml")
    cfg.raw.setdefault("cost", {})["monthly_cap_usd"] = 30
    state = bud.load(cfg, runs)
    check("설정에서 상한을 읽는다", state.cap == 30.0)
    check("남은 예산을 낸다", abs(state.left - 28.02) < 0.01, f"${state.left}")
    check("쓴 비율을 낸다", state.used_pct == 7, f"{state.used_pct}%")

    b = bud.Budget(month="2026-08", cap=30.0, spent=29.50, videos=30)
    check("넘으면 막는다", not b.allows(0.99))
    check("딱 맞으면 통과", b.allows(0.50))
    msg = bud.blocked_message(b, 0.99)
    check("왜 막혔는지 말한다", msg and "$30.49" in msg, (msg or "").splitlines()[0])
    check("어떻게 풀지도 말한다", msg and "monthly_cap_usd" in msg)

    near = bud.Budget(month="2026-08", cap=30.0, spent=28.50, videos=29)
    check("80% 넘으면 미리 알린다", bud.warn_message(near, 0.99) is not None)
    check("아직 여유 있으면 조용히",
          bud.warn_message(bud.Budget("2026-08", 30.0, 1.0, 1), 0.99) is None)

    free = bud.Budget(month="2026-08", cap=0.0, spent=999.0, videos=500)
    check("상한 0 이면 안 막는다", free.allows(100.0))
    check("상한 0 이면 남은 예산도 없음", free.left is None and free.used_pct is None)
    check("상한 0 이면 경고도 없다", bud.warn_message(free, 100.0) is None)

    # 실제 배포 설정에 상한이 들어 있는지 — 여기서 빠지면 아무 효과가 없다
    import yaml
    real = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    check("기본 설정에 월 상한이 있다", real["cost"].get("monthly_cap_usd") == 30.0,
          str(real["cost"].get("monthly_cap_usd")))
    check("기본이 20초(2클립)다", real["num_clips"] == 2, str(real["num_clips"]))
    check("무한 루프가 켜져 있다",
          real["output"]["seamless_loop"]["enabled"] is True)

    from pipeline.costs import estimate as est
    real_cfg = load_config(ROOT / "config.yaml")
    per = est(real_cfg).subtotal
    check("편당 $1 아래", per < 1.0, f"${per:.2f}")
    check("월 상한 안에서 30편", per * 30 <= real_cfg.cost_cfg["monthly_cap_usd"],
          f"${per * 30:.2f} / ${real_cfg.cost_cfg['monthly_cap_usd']}")


# ══════════════════════════════════════════════════════════════════════
def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    try:
        fps_tests()
        billing_tests()
        ledger_tests()
        resume_tests()
        configdiff_tests()
        saver_tests()
        budget_tests()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)

    print("\n" + "=" * 60)
    print(f"통과 {len(PASSED)} · 실패 {len(FAILED)}")
    if FAILED:
        for name in FAILED:
            print(f"  ✗ {name}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
