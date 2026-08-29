"""API 비용 0원으로 파이프라인 전 구간을 검증한다.

  python tests/test_pipeline.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

import tests.mock_provider as mock  # noqa: E402  (import 시 provider 등록)
from pipeline.config import ConfigError, load_config  # noqa: E402
from pipeline.costs import actual_cost, estimate  # noqa: E402
from pipeline.ffmpeg_util import duration_of, dimensions_of, has_audio  # noqa: E402
from pipeline.frame_extractor import extract_last_frame  # noqa: E402
from pipeline.modes import orchestrate  # noqa: E402
from pipeline.runlog import Run  # noqa: E402
from pipeline.stitcher import stitch  # noqa: E402
from pipeline.validator import ValidationError, prepare_input  # noqa: E402

CONFIG = ROOT / "tests" / "config.test.yaml"
TMP = ROOT / "tests" / "_tmp"
PASSED, FAILED = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(name)
    mark = "✓" if condition else "✗"
    print(f"  {mark} {name}" + (f"  — {detail}" if detail else ""))


def make_image(path: Path, size: tuple[int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (30, 60, 120)).save(path)
    return path


def noisy_image(path: Path, size: tuple[int, int]) -> Path:
    """압축이 잘 안 되는 그림. 크기 관련 테스트에는 단색을 쓰면 안 된다."""
    import random

    rnd = random.Random(7)
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(size[1]):
        for x in range(size[0]):
            px[x, y] = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


# ══════════════════════════════════════════════════════════════════════
def test_oversized_input_never_hangs() -> None:
    """4배 업스케일한 프레임을 그대로 올리면 안 된다.

    esrgan 이 1080x1920 을 4320x7680 으로 키운다. 그걸 data URI 로 만들면
    40~80MB 가 되는데, requests 의 timeout 은 소켓이 조용할 때만 도는 값이라
    업로드가 느리게 이어지는 동안에는 만료되지 않는다. 실제로 클립 2에서
    43분을 멈춰 있다가 아무 오류도 못 낸 사례가 나왔다.
    """
    import os

    os.environ.setdefault("FAL_API_KEY", "test-key")
    from pipeline.generator import shrink_to_output
    from pipeline.providers.fal import MAX_INLINE_MB, _data_uri

    print("\n[큰 입력 이미지]")
    TMP.mkdir(parents=True, exist_ok=True)

    # ① 업스케일 결과를 출력 해상도로 되돌린다
    big = noisy_image(TMP / "last_01_upscaled.png", (2160, 3840))
    before_mb = big.stat().st_size / 1e6

    class _Cfg:
        output = {"width": 1080, "height": 1920}

    class _Run:
        def log(self, *a, **k):
            pass

    out = shrink_to_output(big, _Cfg(), _Run(), index=1)
    with Image.open(out) as img:
        shrunk_size = img.size
    after_mb = out.stat().st_size / 1e6
    check("업스케일 프레임을 출력 해상도로 되돌림", shrunk_size == (1080, 1920),
          str(shrunk_size))
    check("파일이 작아짐", after_mb < before_mb, f"{before_mb:.1f} -> {after_mb:.1f}MB")

    # 이미 작은 것은 건드리지 않는다 (다시 인코딩하면 화질만 손해다)
    small = noisy_image(TMP / "small_frame.png", (1080, 1920))
    stamp = small.stat().st_mtime_ns
    shrink_to_output(small, _Cfg(), _Run(), index=2)
    check("작은 프레임은 그대로 둠", small.stat().st_mtime_ns == stamp)

    # ② 그래도 큰 것이 오면 provider 가 JPEG 로 줄여서 보낸다
    huge = noisy_image(TMP / "huge.png", (2600, 4600))
    huge_mb = huge.stat().st_size / 1e6
    check("테스트 파일이 기준보다 큼", huge_mb > MAX_INLINE_MB, f"{huge_mb:.1f}MB")
    uri = _data_uri(huge)
    check("기준을 넘으면 JPEG 로 보냄", uri.startswith("data:image/jpeg;base64,"),
          uri[:32])
    check("payload 가 작아짐", len(uri) / 1e6 < huge_mb,
          f"{huge_mb:.1f}MB -> {len(uri) / 1e6:.1f}MB")

    # 기준 아래는 PNG 그대로 간다 (다시 인코딩하면 화질만 손해다).
    # 순수 노이즈는 PNG 최악의 경우라 1080x1920 이어도 6MB 가 넘는다.
    # 실사 프레임에 가깝게 완만한 그라데이션으로 만든다.
    gentle = TMP / "gentle.png"
    grad = Image.new("RGB", (1080, 1920))
    gpx = grad.load()
    for y in range(1920):
        for x in range(0, 1080, 2):
            c = (x * 255 // 1080, y * 255 // 1920, 120)
            gpx[x, y] = c
            gpx[x + 1, y] = c
    grad.save(gentle)
    gentle_mb = gentle.stat().st_size / 1e6
    check("실사에 가까운 프레임은 기준 아래", gentle_mb < MAX_INLINE_MB,
          f"{gentle_mb:.1f}MB")
    plain = _data_uri(gentle)
    check("기준 아래는 PNG 그대로", plain.startswith("data:image/png;base64,"),
          plain[:30])


def test_poll_heartbeat() -> None:
    """기다리는 동안 살아 있다는 표시가 나와야 한다.

    안 그러면 클립 하나에 몇 분씩 출력이 없어서, 화면만 보는 사람은 멈춘
    것과 구별할 수 없다.
    """
    import io
    from contextlib import redirect_stdout

    from pipeline.providers.base import HEARTBEAT_SECONDS, VideoProvider

    print("\n[대기 중 신호]")

    class _P(VideoProvider):
        def generate(self, req, dest):
            raise NotImplementedError

        def upscale(self, image, dest, endpoint):
            raise NotImplementedError

    prov = _P("x", poll_interval=0.01, timeout=300.0)
    calls = {"n": 0}
    # 가짜 시계로 30초씩 흘려보낸다. 진짜로 기다리면 테스트가 30초 걸린다.
    import pipeline.providers.base as base_mod

    real_time = base_mod.time.time
    clock = {"t": real_time()}
    base_mod.time.time = lambda: clock["t"]          # type: ignore[assignment]
    try:
        def check_fn():
            calls["n"] += 1
            clock["t"] += 12          # 한 번 돌 때마다 12초씩 흐른다
            return calls["n"] >= 8, {"ok": True}

        buf = io.StringIO()
        with redirect_stdout(buf):
            prov._poll(check_fn, label="테스트 작업")
        out = buf.getvalue()
    finally:
        base_mod.time.time = real_time                # type: ignore[assignment]

    beats = out.count("기다리는 중")
    check("기다리는 동안 신호를 찍음", beats >= 2, f"{beats}줄")
    check("경과 시간을 알려줌", "초 경과" in out, out.splitlines()[:1])
    check("남은 시간도 알려줌", "남음" in out)
    check(f"{int(HEARTBEAT_SECONDS)}초마다 한 번꼴", beats <= 5, f"{beats}줄")


# ══════════════════════════════════════════════════════════════════════
def test_validator() -> None:
    print("\n[validator]")
    out = TMP / "v"
    warns = prepare_input(make_image(TMP / "src_916.png", (1080, 1920)), out / "a.png")
    check("9:16 입력은 경고 없음", warns == [], str(warns))
    check("출력 크기 1080x1920", Image.open(out / "a.png").size == (1080, 1920))

    warns = prepare_input(make_image(TMP / "src_sq.png", (1000, 1000)), out / "b.png")
    check("정사각 입력은 크롭 경고", any("크롭" in w for w in warns))
    check("크롭 후에도 1080x1920", Image.open(out / "b.png").size == (1080, 1920))

    warns = prepare_input(make_image(TMP / "src_wide.png", (1920, 1080)),
                          out / "c.png", pad=True)
    check("--pad 는 블러 패딩 경고", any("패딩" in w for w in warns))

    warns = prepare_input(make_image(TMP / "src_small.png", (405, 720)), out / "d.png")
    check("저해상도 경고", any("해상도" in w for w in warns))

    try:
        prepare_input(TMP / "does_not_exist.png", out / "e.png")
        check("없는 파일은 오류", False)
    except ValidationError:
        check("없는 파일은 오류", True)


def test_config_guards() -> None:
    print("\n[config 가드]")
    try:
        load_config(CONFIG, clip_duration=99)
        check("모델 상한 초과 시 거부", False)
    except ConfigError as exc:
        check("모델 상한 초과 시 거부", "최대" in str(exc))

    try:
        load_config(CONFIG, mode="nonsense")
        check("알 수 없는 mode 거부", False)
    except ConfigError:
        check("알 수 없는 mode 거부", True)

    try:
        load_config(CONFIG, crossfade_seconds=99.0)
        check("크로스페이드 > 클립길이 거부", False)
    except ConfigError:
        check("크로스페이드 > 클립길이 거부", True)


def test_costs() -> None:
    print("\n[비용]")
    cfg = load_config(CONFIG, num_clips=6, clip_duration=5)
    est = estimate(cfg)
    check("영상 소계 = 6 x 5초 x $0.07", abs(est.video_subtotal - 2.10) < 1e-6,
          f"${est.video_subtotal:.2f}")
    check("업스케일은 클립수-1 회", est.upscale_images == 5, str(est.upscale_images))
    check("재시도 계수 반영", abs(est.expected - est.subtotal * 1.8) < 1e-6)

    cfg_loop = load_config(CONFIG, num_clips=6, loop_back=True)
    check("loop_back 은 클립 1개 추가", estimate(cfg_loop).video_clips_planned == 7)

    # montage 는 프레임을 이어붙이지 않으므로 업스케일이 없다
    cfg_m = load_config(CONFIG, mode="montage", num_clips=6)
    check("montage 는 업스케일 0", estimate(cfg_m).upscale_images == 0)

    check("사후 비용은 실제 호출 기준",
          abs(actual_cost(cfg, clips_generated=8, upscales_done=3) - (8 * 0.35 + 3 * 0.01)) < 1e-6)


def test_chain_end_to_end() -> None:
    print("\n[chain 모드 E2E]")
    mock.MockProvider.counter = 0
    mock.MockProvider.fail_on = set()
    mock.MockProvider._attempts = {}

    cfg = load_config(CONFIG, num_clips=4, clip_duration=5)
    runs = TMP / "runs"
    run = Run.create(runs, "chain_test")
    prepare_input(make_image(TMP / "seed.png", (1080, 1920)), run.input_image)

    clips, stats = orchestrate(cfg, run, interactive=False, resume=False)
    check("클립 4개 생성", len(clips) == 4, f"{len(clips)}개")
    check("호출 4회", stats.clip_calls == 4, f"{stats.clip_calls}회")
    check("업스케일 3회", stats.upscale_calls == 3, f"{stats.upscale_calls}회")
    check("라스트 프레임 파일 존재", run.frame(1).exists())
    check("업스케일 프레임 존재", run.frame(1, upscaled=True).exists())
    check("log.jsonl 기록됨", run.log_path.exists() and run.log_path.stat().st_size > 0)

    result = stitch(clips, run.final, crossfade=0.3, transition="fade")
    expected = 4 * 5 - 3 * 0.3
    check(f"합성 길이 {expected}초", abs(result.duration - expected) < 0.15,
          f"{result.duration:.3f}초")
    check("출력 1080x1920", dimensions_of(run.final) == (1080, 1920))
    check("오디오 트랙 포함", has_audio(run.final))


def test_retry() -> None:
    print("\n[재시도]")
    mock.MockProvider.counter = 0
    mock.MockProvider.fail_on = {2}   # 2번 클립을 1회 실패시킨다
    mock.MockProvider._attempts = {}

    cfg = load_config(CONFIG, num_clips=3, clip_duration=5)
    run = Run.create(TMP / "runs", "retry_test")
    prepare_input(make_image(TMP / "seed.png", (1080, 1920)), run.input_image)

    clips, stats = orchestrate(cfg, run, interactive=False, resume=False)
    check("실패해도 3개 완성", len(clips) == 3, f"{len(clips)}개")
    check("실패분까지 5회 과금 집계", stats.clip_calls == 4, f"{stats.clip_calls}회")
    mock.MockProvider.fail_on = set()


def test_resume() -> None:
    print("\n[resume]")
    mock.MockProvider.counter = 0
    mock.MockProvider._attempts = {}

    cfg = load_config(CONFIG, num_clips=5, clip_duration=5)
    run = Run.create(TMP / "runs", "resume_test")
    prepare_input(make_image(TMP / "seed.png", (1080, 1920)), run.input_image)

    # 먼저 2개만 만든다
    partial = load_config(CONFIG, num_clips=2, clip_duration=5)
    orchestrate(partial, run, interactive=False, resume=False)
    check("부분 실행 2개", len(run.completed_clips()) == 2)

    calls_before = mock.MockProvider.counter
    clips, stats = orchestrate(cfg, run, interactive=False, resume=True)
    check("이어하기로 총 5개", len(clips) == 5, f"{len(clips)}개")
    check("새로 만든 건 3개뿐", mock.MockProvider.counter - calls_before == 3,
          f"{mock.MockProvider.counter - calls_before}개")


def test_montage() -> None:
    print("\n[montage 모드]")
    mock.MockProvider.counter = 0
    mock.MockProvider._attempts = {}

    # 레퍼런스 실측: 5초 x 5장면 = 25초, 하드 컷
    cfg = load_config(CONFIG, mode="montage", num_clips=5, clip_duration=5,
                      montage_transition="cut")
    run = Run.create(TMP / "runs", "montage_test")
    prepare_input(make_image(TMP / "seed.png", (1080, 1920)), run.input_image)

    clips, stats = orchestrate(cfg, run, interactive=False, resume=False)
    check("장면 5개", len(clips) == 5)
    check("montage 는 업스케일 안 함", stats.upscale_calls == 0, f"{stats.upscale_calls}회")

    result = stitch(clips, run.final, transition="cut")
    check("하드 컷 길이 25초", abs(result.duration - 25.0) < 0.15, f"{result.duration:.3f}초")


def test_frame_extraction() -> None:
    print("\n[프레임 추출]")
    run = Run.load(TMP / "runs", "chain_test")
    out = extract_last_frame(run.clip(1), TMP / "last.png")
    check("마지막 프레임 추출", out.exists() and out.stat().st_size > 0)
    check("추출 프레임도 9:16", abs(Image.open(out).size[0] / Image.open(out).size[1] - 9 / 16) < 0.01)


def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP)
    print("═" * 62)
    print(" 파이프라인 검증 (mock provider — API 호출 0회, 비용 $0)")
    print("═" * 62)

    test_validator()
    test_config_guards()
    test_costs()
    test_chain_end_to_end()
    test_retry()
    test_resume()
    test_montage()
    test_frame_extraction()
    test_oversized_input_never_hangs()
    test_poll_heartbeat()

    print("\n" + "═" * 62)
    print(f" 통과 {len(PASSED)} / 실패 {len(FAILED)}")
    if FAILED:
        for name in FAILED:
            print(f"   ✗ {name}")
    print("═" * 62)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
