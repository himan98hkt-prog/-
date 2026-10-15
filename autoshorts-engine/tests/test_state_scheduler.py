"""이력 저장소와 예약 등록 테스트."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from autoshorts.scheduler import (
    TASK_NAME,
    Schedule,
    ScheduleError,
    build_auto_command,
    cron_line,
    detect_platform,
    launchd_plist,
    parse_time,
    parse_weekday,
    schtasks_command,
)
from autoshorts.state import HistoryStore


@pytest.fixture
def store(tmp_path):
    return HistoryStore(tmp_path / "history.json")


class TestHistoryStore:
    def test_new_store_is_empty(self, store):
        assert store.entries == [] and not store.is_processed("v1")

    def test_records_and_persists(self, store, tmp_path):
        store.record("v1", source_url="u", title="제목", clip_count=3)
        store.save()
        reloaded = HistoryStore(tmp_path / "history.json")
        assert reloaded.is_processed("v1")
        assert reloaded.entries[0].title == "제목"
        assert reloaded.entries[0].clip_count == 3

    def test_same_source_merges_instead_of_duplicating(self, store):
        store.record("v1", clip_count=2, uploads=[{"video_id": "a"}])
        store.record("v1", clip_count=3, uploads=[{"video_id": "b"}])
        assert len(store.entries) == 1
        assert store.entries[0].clip_count == 3
        assert len(store.entries[0].uploads) == 2

    def test_filter_unprocessed(self, store):
        store.record("v1")
        assert store.filter_unprocessed(["v1", "v2", "v3"]) == ["v2", "v3"]

    def test_blank_id_is_never_processed(self, store):
        assert not store.is_processed("")

    def test_counts_uploads_today(self, store):
        store.record("v1", uploads=[{"video_id": "a"}, {"video_id": "b"}])
        assert store.uploads_on() == 2
        assert store.remaining_uploads_today(6) == 4

    def test_yesterdays_uploads_do_not_count(self, store):
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        store.record("v1", uploads=[{"video_id": "a", "uploaded_at": yesterday}])
        assert store.uploads_on() == 0
        assert store.remaining_uploads_today(6) == 6

    def test_remaining_never_negative(self, store):
        store.record("v1", uploads=[{"video_id": str(i)} for i in range(10)])
        assert store.remaining_uploads_today(6) == 0

    def test_corrupt_file_does_not_crash(self, tmp_path):
        broken = tmp_path / "history.json"
        broken.write_text("{ not json", encoding="utf-8")
        store = HistoryStore(broken)
        assert store.entries == []
        store.record("v1")
        store.save()
        assert HistoryStore(broken).is_processed("v1")

    def test_prune_drops_old_entries(self, store):
        old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        store.record("old")
        store._data["entries"][0]["processed_at"] = old
        store.record("new")
        assert store.prune(retention_days=180) == 1
        assert [e.source_id for e in store.entries] == ["new"]

    def test_prune_keeps_unparseable_dates(self, store):
        store.record("weird")
        store._data["entries"][0]["processed_at"] = "언젠가"
        assert store.prune() == 0
        assert store.entries

    def test_path_override_via_environment(self, tmp_path, monkeypatch):
        from autoshorts.state import default_history_path

        monkeypatch.setenv("AUTOSHORTS_HISTORY_PATH", str(tmp_path / "custom.json"))
        assert default_history_path() == tmp_path / "custom.json"


class TestScheduleParsing:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [("09:00", (9, 0)), ("9", (9, 0)), ("21:30", (21, 30)), ("0:05", (0, 5)), ("23:59", (23, 59))],
    )
    def test_parse_time(self, text, expected):
        assert parse_time(text) == expected

    @pytest.mark.parametrize("text", ["25:00", "09:70", "아침", "", "abc"])
    def test_rejects_bad_time(self, text):
        with pytest.raises(ValueError):
            parse_time(text)

    @pytest.mark.parametrize(("text", "expected"), [("mon", 1), ("sun", 0), ("월", 1), ("토", 6), (None, None), ("", None)])
    def test_parse_weekday(self, text, expected):
        assert parse_weekday(text) == expected

    def test_rejects_bad_weekday(self):
        with pytest.raises(ValueError):
            parse_weekday("someday")

    def test_schedule_validation(self):
        with pytest.raises(ValueError, match="시"):
            Schedule(hour=25)
        with pytest.raises(ValueError, match="분"):
            Schedule(minute=90)
        with pytest.raises(ValueError, match="every_hours"):
            Schedule(every_hours=48)

    def test_descriptions_are_readable(self):
        assert Schedule(hour=9, minute=0).description == "매일 09:00"
        assert Schedule(hour=21, minute=30, weekday=1).description == "매주 월요일 21:30"
        assert Schedule(every_hours=6).description == "6시간마다"


class TestCommandBuilding:
    def test_auto_command_shape(self):
        command = build_auto_command("재테크", extra_args=["--upload"], python="/usr/bin/python3")
        assert command[:4] == ["/usr/bin/python3", "-m", "autoshorts", "auto"]
        assert command[4] == "재테크"
        assert "--upload" in command

    def test_cron_daily(self):
        line = cron_line(Schedule(hour=9, minute=30), ["python3", "-m", "autoshorts", "auto", "x"])
        assert line.startswith("30 9 * * *")
        assert TASK_NAME in line                     # 나중에 지울 수 있게 표식을 남긴다

    def test_cron_weekly(self):
        assert cron_line(Schedule(hour=8, minute=0, weekday=1), ["cmd"]).startswith("0 8 * * 1")

    def test_cron_every_n_hours(self):
        assert cron_line(Schedule(every_hours=6), ["cmd"]).startswith("0 */6 * * *")

    def test_cron_appends_log_redirect(self):
        line = cron_line(Schedule(), ["cmd"], log_path="/tmp/a b.log")
        assert ">>" in line and "2>&1" in line

    def test_schtasks_daily(self):
        args = schtasks_command(Schedule(hour=9, minute=5), ["python", "-m", "autoshorts"])
        assert args[:2] == ["schtasks", "/Create"]
        assert args[args.index("/SC") + 1] == "DAILY"
        assert args[args.index("/ST") + 1] == "09:05"

    def test_schtasks_weekly_uses_day_name(self):
        args = schtasks_command(Schedule(hour=9, weekday=3), ["cmd"])
        assert args[args.index("/SC") + 1] == "WEEKLY"
        assert args[args.index("/D") + 1] == "WED"

    def test_schtasks_hourly(self):
        args = schtasks_command(Schedule(every_hours=4), ["cmd"])
        assert args[args.index("/SC") + 1] == "HOURLY"
        assert args[args.index("/MO") + 1] == "4"

    def test_launchd_plist_is_well_formed(self):
        plist = launchd_plist(Schedule(hour=7, minute=15), ["python3", "-m", "autoshorts"])
        assert plist.startswith("<?xml")
        assert "<key>StartCalendarInterval</key>" in plist
        assert "<integer>7</integer>" in plist
        assert "<string>python3</string>" in plist

    def test_launchd_interval_mode(self):
        plist = launchd_plist(Schedule(every_hours=3), ["cmd"])
        assert "<key>StartInterval</key>" in plist
        assert "<integer>10800</integer>" in plist    # 3시간 = 10800초


class TestInstallDryRun:
    def test_linux_dry_run_returns_cron_line(self):
        from autoshorts.scheduler import install_schedule

        out = install_schedule(Schedule(hour=9), ["cmd"], dry_run=True, target_platform="linux")
        assert out.startswith("0 9 * * *")

    def test_windows_dry_run_returns_schtasks(self):
        from autoshorts.scheduler import install_schedule

        out = install_schedule(Schedule(hour=9), ["cmd"], dry_run=True, target_platform="windows")
        assert out.startswith("schtasks /Create")

    def test_macos_dry_run_returns_plist(self):
        from autoshorts.scheduler import install_schedule

        out = install_schedule(Schedule(hour=9), ["cmd"], dry_run=True, target_platform="macos")
        assert "<?xml" in out and "LaunchAgents" in out

    def test_detect_platform_is_known(self):
        assert detect_platform() in {"windows", "macos", "linux"}
