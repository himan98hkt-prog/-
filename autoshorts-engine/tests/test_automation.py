"""자동 실행(탐색→제작→업로드) 흐름 테스트."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from autoshorts import automation
from autoshorts.automation import AutoOptions, build_upload_request, resolve_target, run_auto
from autoshorts.config import Settings
from autoshorts.models import Clip
from autoshorts.pipeline import PipelineResult
from autoshorts.state import HistoryStore
from autoshorts.trend_finder import TrendVideo
from autoshorts.uploader import AuthRequiredError, QuotaExceededError, UploadResult
from autoshorts.video_renderer import RenderResult


def make_render(tmp_path, index=1, title="클립 제목"):
    path = tmp_path / f"output_{index:02d}_{title}.mp4"
    path.write_bytes(b"video")
    return RenderResult(
        clip=Clip(start=0, end=40, title=title, reason="선정 이유", score=80, index=index),
        output_path=path, duration=40.0, size_bytes=5,
    )


@pytest.fixture
def settings(tmp_path):
    return Settings(source="", work_dir=tmp_path / "work", output_dir=tmp_path / "out",
                    youtube_api_key="yt-key")


@pytest.fixture
def history(tmp_path):
    return HistoryStore(tmp_path / "history.json")


@pytest.fixture
def stub(monkeypatch, tmp_path):
    """탐색과 파이프라인을 가짜로 교체한다."""
    state = {"videos": [TrendVideo(video_id="hot", title="떡상 영상", view_count=90_000,
                                   subscriber_count=10_000, duration_seconds=600)],
             "renders": [make_render(tmp_path, 1, "첫클립"), make_render(tmp_path, 2, "둘째클립")]}

    monkeypatch.setattr(
        automation.trend_finder, "find_trending",
        lambda target, **kwargs: (list(state["videos"]), 102),
    )

    def fake_pipeline(settings, on_progress=None, **kwargs):
        state["source"] = settings.source
        return PipelineResult(source=settings.source, title="떡상 영상", renders=list(state["renders"]))

    monkeypatch.setattr(automation.pipeline, "run_pipeline", fake_pipeline)
    return state


class TestResolveTarget:
    @pytest.mark.parametrize(
        "value",
        ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ",
         "https://www.youtube.com/shorts/dQw4w9WgXcQ"],
    )
    def test_video_urls_are_direct(self, value):
        assert resolve_target(value)[0] == "direct"

    def test_local_file_is_direct(self, tmp_path):
        path = tmp_path / "v.mp4"
        path.write_bytes(b"x")
        assert resolve_target(str(path)) == ("direct", str(path))

    @pytest.mark.parametrize("value", ["재테크", "@채널핸들", "UCabcdefghijklmnopqrstuv"])
    def test_keywords_and_channels_are_searched(self, value):
        assert resolve_target(value)[0] == "search"

    def test_empty_rejected(self):
        with pytest.raises(ValueError, match="대상"):
            resolve_target("  ")


class TestBuildUploadRequest:
    def test_carries_title_and_credits_source(self, tmp_path):
        render = make_render(tmp_path, 1, "후킹제목")
        request = build_upload_request(
            render, options=AutoOptions(tags=["재테크"]),
            source_title="원본 영상", source_url="https://youtu.be/abc",
        )
        assert request.title == "후킹제목"
        assert "원본 영상" in request.description
        assert "https://youtu.be/abc" in request.description   # 출처를 밝힌다
        assert request.tags == ["재테크"]

    def test_defaults_to_private(self, tmp_path):
        assert build_upload_request(make_render(tmp_path), options=AutoOptions()).privacy == "private"


class TestRunAuto:
    def test_search_then_render(self, settings, stub, history):
        result = run_auto(settings, "재테크", AutoOptions(), history=history)
        assert result.ok
        assert result.source_id == "hot"
        assert stub["source"] == "https://www.youtube.com/watch?v=hot"
        assert len(result.renders) == 2
        assert result.quota_used == 102

    def test_records_history_so_next_run_skips(self, settings, stub, history):
        run_auto(settings, "재테크", AutoOptions(), history=history)
        second = run_auto(settings, "재테크", AutoOptions(), history=history)
        assert second.skipped_reason
        assert "처리" in second.skipped_reason

    def test_allow_reprocess(self, settings, stub, history):
        run_auto(settings, "재테크", AutoOptions(), history=history)
        again = run_auto(settings, "재테크", AutoOptions(skip_processed=False), history=history)
        assert again.ok

    def test_direct_url_skips_search(self, settings, stub, history, monkeypatch):
        monkeypatch.setattr(
            automation.trend_finder, "find_trending",
            lambda *a, **k: pytest.fail("URL 을 직접 주면 탐색하면 안 된다"),
        )
        result = run_auto(settings, "https://youtu.be/dQw4w9WgXcQ", AutoOptions(), history=history)
        assert result.ok and result.source_id == "dQw4w9WgXcQ"

    def test_search_without_key_is_skipped_with_guidance(self, settings, stub, history):
        settings.youtube_api_key = None
        result = run_auto(settings, "재테크", AutoOptions(), history=history)
        assert "YOUTUBE_API_KEY" in result.skipped_reason
        assert not result.renders

    def test_no_new_candidates(self, settings, stub, history):
        history.record("hot")
        result = run_auto(settings, "재테크", AutoOptions(), history=history)
        assert "새로 처리할" in result.skipped_reason

    def test_uploads_each_render(self, settings, stub, history):
        calls = []

        def fake_upload(request, **kwargs):
            calls.append(request)
            return UploadResult(video_id=f"up{len(calls)}", title=request.title)

        result = run_auto(settings, "재테크", AutoOptions(upload=True), history=history,
                          upload_fn=fake_upload)
        assert len(result.uploads) == 2
        assert [u.video_id for u in result.uploads] == ["up1", "up2"]
        assert all(r.privacy == "private" for r in calls)

    def test_upload_count_limits(self, settings, stub, history):
        result = run_auto(settings, "재테크", AutoOptions(upload=True, upload_count=1),
                          history=history, upload_fn=lambda r, **k: UploadResult(video_id="x"))
        assert len(result.uploads) == 1

    def test_daily_quota_is_respected(self, settings, stub, history):
        # 이미 오늘 6건을 올린 상태
        history.record("earlier", uploads=[{"video_id": str(i)} for i in range(6)])
        result = run_auto(settings, "재테크", AutoOptions(upload=True), history=history,
                          upload_fn=lambda r, **k: pytest.fail("한도를 넘겨 업로드하면 안 된다"))
        assert result.uploads == []
        assert result.renders                       # 제작은 되었다

    def test_publish_times_are_spread(self, settings, stub, history):
        base = datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)
        seen = []

        def fake_upload(request, **kwargs):
            seen.append(request.publish_at)
            return UploadResult(video_id="x", publish_at=request.publish_at)

        run_auto(settings, "재테크", AutoOptions(upload=True, publish_at=base),
                 history=history, upload_fn=fake_upload)
        assert seen[0] == base
        assert seen[1] == base + timedelta(hours=24)

    def test_upload_failure_does_not_stop_the_rest(self, settings, stub, history):
        calls = {"n": 0}

        def flaky(request, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("일시적 오류")
            return UploadResult(video_id="ok")

        result = run_auto(settings, "재테크", AutoOptions(upload=True), history=history, upload_fn=flaky)
        assert len(result.uploads) == 1
        assert len(result.upload_errors) == 1

    def test_auth_error_stops_remaining_uploads(self, settings, stub, history):
        calls = {"n": 0}

        def unauthorised(request, **kwargs):
            calls["n"] += 1
            raise AuthRequiredError("로그인 필요")

        result = run_auto(settings, "재테크", AutoOptions(upload=True), history=history,
                          upload_fn=unauthorised)
        assert calls["n"] == 1                      # 두 번째는 시도조차 하지 않는다
        assert len(result.upload_errors) == 1

    def test_quota_error_stops_remaining_uploads(self, settings, stub, history):
        calls = {"n": 0}

        def exhausted(request, **kwargs):
            calls["n"] += 1
            raise QuotaExceededError("한도 초과")

        run_auto(settings, "재테크", AutoOptions(upload=True), history=history, upload_fn=exhausted)
        assert calls["n"] == 1

    def test_dry_run_upload_makes_no_calls(self, settings, stub, history):
        result = run_auto(settings, "재테크", AutoOptions(upload=True, dry_run_upload=True),
                          history=history,
                          upload_fn=lambda r, **k: pytest.fail("dry-run 에서는 올리면 안 된다"))
        assert result.uploads == [] and result.renders

    def test_no_renders_is_recorded_and_reported(self, settings, stub, history, monkeypatch):
        monkeypatch.setattr(
            automation.pipeline, "run_pipeline",
            lambda settings, **k: PipelineResult(source=settings.source, renders=[]),
        )
        result = run_auto(settings, "재테크", AutoOptions(), history=history)
        assert "생성된 쇼츠가 없습니다" in result.skipped_reason
        assert history.is_processed("hot")          # 다음 실행에서 또 붙잡지 않도록

    def test_uploads_recorded_in_history(self, settings, stub, history, tmp_path):
        run_auto(settings, "재테크", AutoOptions(upload=True), history=history,
                 upload_fn=lambda r, **k: UploadResult(video_id="rec"))
        reloaded = HistoryStore(tmp_path / "history.json")
        assert reloaded.uploads_on() == 2
