"""`scripts/e2e_phase2.py` 의 순수 헬퍼 테스트.

E2E 스크립트 전체는 PostgreSQL·FFmpeg·자식 프로세스가 필요해 CI 에서 돌리지
않는다. 하지만 **판정 로직**은 여기서 고정해 둔다 — 실제로 `probe()` 가
ffprobe 의 csv 출력 순서를 잘못 가정해 `width` 자리에 `codec_name` 을 읽는
버그가 있었고, 그건 단위 테스트로 잡을 수 있는 종류다.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.e2e_phase2 import Report, Step, probe  # noqa: E402

ffmpeg = shutil.which("ffmpeg")
ffprobe = shutil.which("ffprobe")
needs_ffmpeg = pytest.mark.skipif(
    not (ffmpeg and ffprobe), reason="ffmpeg/ffprobe 가 없는 환경"
)


class TestReport:
    def test_empty_report_is_not_ok(self):
        """단계가 하나도 없으면 통과로 치지 않는다."""
        assert Report().ok is False

    def test_all_steps_must_pass(self):
        report = Report()
        report.step("a").ok = True
        report.step("b").ok = True
        assert report.ok is True

    def test_one_failure_fails_the_run(self):
        report = Report()
        report.step("a").ok = True
        report.step("b").ok = False
        assert report.ok is False

    def test_render_marks_each_step(self):
        report = Report()
        first = report.step("성공한 단계")
        first.ok, first.detail = True, "세부"
        report.step("실패한 단계")
        text = report.render()
        assert "[OK  ] 성공한 단계" in text
        assert "[FAIL] 실패한 단계" in text
        assert "세부" in text

    def test_render_lists_facts(self):
        report = Report()
        report.step("s").ok = True
        report.facts["산출물 규격"] = "1080x1920"
        assert "1080x1920" in report.render()

    def test_to_dict_round_trip(self):
        report = Report()
        entry = report.step("s")
        entry.ok, entry.seconds = True, 1.234
        payload = report.to_dict()
        assert payload["ok"] is True
        assert payload["steps"][0] == {
            "name": "s", "ok": True, "detail": "", "seconds": 1.23,
        }

    def test_step_defaults_to_failed(self):
        """단계를 만들고 성공을 표시하지 않으면 실패로 남는다."""
        assert Step("x").ok is False


@needs_ffmpeg
class TestProbe:
    @pytest.fixture(scope="class")
    def sample(self, tmp_path_factory):
        """세로 해상도와 가로 해상도가 다른 영상 — 순서를 헷갈리면 바로 드러난다."""
        path = tmp_path_factory.mktemp("probe") / "s.mp4"
        subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=1",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
             "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "48000", "-shortest", str(path)],
            check=True, capture_output=True,
        )
        return path

    def test_reads_fields_by_name_not_position(self, sample):
        """ffprobe 는 요청 순서가 아니라 스트림 구조체 순서로 내보낸다.

        위치로 읽으면 width 자리에 codec_name('h264') 이 와서 int() 가 터진다.
        """
        info = probe(sample, ffprobe)
        assert info["width"] == 1080
        assert info["height"] == 1920
        assert info["video_codec"] == "h264"

    def test_reads_audio_stream(self, sample):
        info = probe(sample, ffprobe)
        assert info["audio_codec"] == "aac"
        assert info["sample_rate"] == 48000

    def test_portrait_is_not_confused_with_landscape(self, sample):
        info = probe(sample, ffprobe)
        assert info["height"] > info["width"]        # 9:16 인지 분간한다

    def test_missing_audio_does_not_crash(self, tmp_path):
        silent = tmp_path / "noaudio.mp4"
        subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=15:duration=1",
             "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
             str(silent)],
            check=True, capture_output=True,
        )
        info = probe(silent, ffprobe)
        assert info["width"] == 320 and info["height"] == 240
        assert info["audio_codec"] == ""             # 없으면 빈 문자열, 예외 아님
        assert info["sample_rate"] == 0
