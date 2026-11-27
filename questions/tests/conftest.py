"""질문 앱 테스트 공통 설정.
빠른 테스트: py -3 -m pytest questions/tests -q
원본 재계산까지: py -3 -m pytest questions/tests -q --runslow  (311 원본이 있는 PC에서만)
"""
import json
import sys
from pathlib import Path

import pytest

QDIR = Path(__file__).resolve().parents[1]
for p in (QDIR, QDIR / "calc"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False, help="311 원본을 다시 읽는 느린 테스트도 실행")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: 311 원본(392MB)을 다시 읽어 계산한다. --runslow가 있을 때만 실행")


def pytest_collection_modifyitems(config, items):
    import common
    if not config.getoption("--runslow"):
        reason = "느린 테스트: --runslow를 붙이면 실행한다"
    elif not common.RAW.exists():
        reason = f"311 원본이 없다: {common.RAW} (환경 변수 NY311_RAW로 지정)"
    else:
        return
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=reason))


@pytest.fixture(scope="session")
def qdir() -> Path:
    return QDIR


@pytest.fixture(scope="session")
def stats():
    def load(qid: int) -> dict:
        return json.loads((QDIR / "data" / f"q{qid:03d}.json").read_text(encoding="utf-8"))
    return load
