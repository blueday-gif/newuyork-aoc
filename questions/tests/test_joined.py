"""Phase 3A 결합 결과·도구 테스트."""
import json
from pathlib import Path

import pandas as pd

from components.edu_blocks import md_safe
from fetch_ext import norm_bbl
from joined import points_to_geoid

QDIR = Path(__file__).resolve().parents[1]
JOINED = QDIR / "data" / "joined"
ALLOWED_KINDS = {"bar", "barh", "line", "stack", "stackh", "group", "scatter"}
JOINED_IDS = {7, 57, 58, 72, 75, 96, 97, 100}
SOURCE_KEYS = {"name", "dataset", "url", "period", "rows", "fetched_at"}
DOC_KEYS = {"id", "computed_at", "sources", "metrics", "charts", "tables", "numbers"}


def test_md_safe():
    assert md_safe("2024-11~2025-10, 12~44배") == r"2024-11\~2025-10, 12\~44배"
    assert md_safe("a ~ b") == r"a \~ b"


def test_norm_bbl():
    s = pd.Series(["1000010010.00000000", " 3033540029", "0000000000", "", None, "123", "6000000001"])
    out = norm_bbl(s)
    assert list(out.iloc[:2]) == ["1000010010", "3033540029"]
    assert out.iloc[2:].isna().all()


def test_points_to_geoid():
    df = pd.DataFrame({
        "latitude": [40.7580, 40.0],
        "longitude": [-73.9855, -70.0],
    })
    g = points_to_geoid(df)
    assert str(g.iloc[0]).startswith("36061")
    assert pd.isna(g.iloc[1])


def test_joined_schema():
    paths = sorted(JOINED.glob("q*.json"))
    ids = {int(p.stem[1:]) for p in paths}
    assert ids == JOINED_IDS
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert set(doc.keys()) == DOC_KEYS
        assert doc["id"] == int(p.stem[1:])
        for s in doc["sources"]:
            assert set(s.keys()) >= SOURCE_KEYS
            assert s["rows"] > 0
        for c in doc["charts"]:
            assert c["kind"] in ALLOWED_KINDS


def test_original_stats_untouched(stats):
    d = stats(7)
    m0 = d["metrics"][0]
    assert m0["label"] == "난방 민원(2025-11 ~ 2026-05)"
    assert m0["value"] == "308,677건"


def test_q057_numbers():
    path = JOINED / "q057.json"
    assert path.exists()
    doc = json.loads(path.read_text(encoding="utf-8"))
    n = doc["numbers"]
    for k in ("days_below0", "days_0_10", "median_below0", "median_0_10", "ratio", "spearman"):
        assert k in n
    assert n["days_below0"] + n["days_0_10"] <= 151
    assert -1 <= n["spearman"] <= 1
