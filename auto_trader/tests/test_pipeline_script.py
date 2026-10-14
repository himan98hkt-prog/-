"""scripts/test_pipeline.py 의 스키마 검증·저장 단계 테스트."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from data_pipeline.market_data import collect
from tests.test_market_data import StubApi

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 9, 7, 9, 35, tzinfo=KST)


def _load_script():
    path = Path(__file__).resolve().parent.parent / "scripts" / "test_pipeline.py"
    spec = importlib.util.spec_from_file_location("pipeline_script", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pipeline_script"] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


def test_snapshot_passes_schema_validation(settings_obj):
    snapshot = collect("005930", StubApi(), settings_obj, now=NOW)
    assert script.validate_schema(snapshot) == []


def test_validate_schema_reports_missing_keys():
    broken = {"code": "005930", "price": {"current": 100}}
    missing = script.validate_schema(broken)
    assert "name" in missing
    assert "price.volume_ratio_20d" in missing
    assert "indicators.rsi14" in missing


def test_validate_schema_rejects_wrong_type():
    missing = script.validate_schema({"price": "not-a-dict"})
    assert any("price" in entry for entry in missing)


def test_snapshot_saved_to_snapshots_dir(settings_obj):
    snapshot = collect("005930", StubApi(), settings_obj, now=NOW)
    path = script.save_snapshot(snapshot, settings_obj.paths["snapshots"], NOW)

    assert path.name == "20260907_093500_005930.json"
    assert path.parent == settings_obj.paths["snapshots"]

    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded == snapshot, "저장·재로드 후에도 동일해야 합니다"
    assert script.validate_schema(reloaded) == []
    assert "삼성전자" in path.read_text(encoding="utf-8"), "한글이 이스케이프되면 안 됩니다"


def test_summarize_does_not_raise_for_holding(settings_obj):
    from trading.kis_api import Holding

    holding = Holding("005930", "삼성전자", 12, 12, 70000, 76000, 912000, 72000, 8.57)
    snapshot = collect("005930", StubApi(), settings_obj, holding=holding, now=NOW)
    script.summarize(snapshot)  # 포맷 문자열 오류가 없어야 한다
