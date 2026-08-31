from __future__ import annotations

from pathlib import Path

import pytest
from golden_specs import GOLDEN


def pytest_addoption(parser):
    parser.addoption(
        "--golden-report", action="store", default=None,
        help="골든 회귀 결과를 기록할 마크다운 경로",
    )


@pytest.fixture(scope="session")
def golden_report_path(pytestconfig):
    p = pytestconfig.getoption("--golden-report")
    return Path(p) if p else None


@pytest.fixture(params=GOLDEN, ids=[g["id"] for g in GOLDEN])
def golden_spec(request):
    return request.param
