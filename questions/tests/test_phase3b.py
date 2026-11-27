"""Phase 3B: 선거 결합·쓰레기통 DiD."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from elections import ed_tract_weights, ed_votes, parse_tally
from fetch_ext import ELECTION_DIR, EXT_DIR

QDIR = Path(__file__).resolve().parents[1]
JOINED = QDIR / "data" / "joined"
LABS = QDIR / "data" / "labs"
DOC_KEYS = {"id", "computed_at", "sources", "metrics", "charts", "tables", "numbers"}
SOURCE_KEYS = {"name", "dataset", "url", "period", "rows", "fetched_at"}
ALLOWED_KINDS = {"bar", "barh", "line", "stack", "stackh", "group", "scatter"}


def _has_elections() -> bool:
    csvs = list(ELECTION_DIR.glob("mayor_2025_*.csv"))
    shp = list(ELECTION_DIR.glob("**/nyed.shp"))
    pluto = EXT_DIR / "pluto_xy.parquet"
    return len(csvs) >= 5 and bool(shp) and pluto.exists()


def test_parse_tally():
    out = parse_tally(pd.Series(["2,116", "0", "15", ""]))
    assert list(out) == [2116, 0, 15, 0]


def test_results_totals():
    if not _has_elections():
        pytest.skip("elections/pluto_xy 외부 파일 없음")
    ed = ed_votes()
    assert int(ed["total"].sum()) == 2_187_998
    assert int(ed["mamdani"].sum()) == 1_114_184
    assert int(ed["cuomo"].sum()) == 906_614
    assert int(ed["sliwa"].sum()) == 153_749


def test_ed_weights_sum():
    if not _has_elections():
        pytest.skip("elections/pluto_xy 외부 파일 없음")
    w = ed_tract_weights()
    by = w.groupby("ed")["w"].sum()
    assert (by <= 1 + 1e-6).all()
    bad = (by < 0.99).mean()
    assert bad <= 0.02


def test_did_lab_numbers():
    path = LABS / "did_containerization.json"
    assert path.exists()
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["excluded_cd"] == [109, 302]
    win = {r["label"]: r for r in doc["windows"]}
    assert abs(win["2024"]["T"] - 6.056) <= 0.01
    assert abs(win["2024"]["C"] - 3.511) <= 0.01
    assert abs(win["2025"]["T"] - 4.577) <= 0.01
    assert abs(win["2025"]["C"] - 3.263) <= 0.01
    t24, c24 = win["2024"]["T"], win["2024"]["C"]
    t25, c25 = win["2025"]["T"], win["2025"]["C"]
    ratio_change = (t25 / c25) / (t24 / c24) - 1
    assert abs(ratio_change * 100 - (-18.7)) <= 0.2


def test_joined_3b_schema():
    for qid in (17, 99):
        path = JOINED / f"q{qid:03d}.json"
        assert path.exists()
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert set(doc.keys()) == DOC_KEYS
        assert doc["id"] == qid
        for s in doc["sources"]:
            assert set(s.keys()) >= SOURCE_KEYS
            assert s["rows"] > 0
        for c in doc["charts"]:
            assert c["kind"] in ALLOWED_KINDS
