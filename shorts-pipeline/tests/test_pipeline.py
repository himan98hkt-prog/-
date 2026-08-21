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

    print("\n" + "═" * 62)
    print(f" 통과 {len(PASSED)} / 실패 {len(FAILED)}")
    if FAILED:
        for name in FAILED:
            print(f"   ✗ {name}")
    print("═" * 62)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
