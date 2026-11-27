"""기준 수치 회귀 테스트(빠름, 311 원본 불필요).
리팩토링 뒤에도 이 수치가 그대로여야 한다. 숫자의 근거는 CLAUDE.md '기준 수치'."""
import json
import tomllib

import pandas as pd
import pytest

from common import ROOT

TRACT_CSV = ROOT / "data" / "processed" / "nyc311_tract_complaints.csv"


def bronx(stats) -> dict[str, float]:
    rows = stats(95)["charts"][0]["rows"]
    return {r["분야"]: r["1,000명당"] for r in rows if r["자치구"] == "브롱크스"}


def test_q095_metrics(stats):
    m = stats(95)["metrics"]
    assert [x["value"] for x in m] == ["97.9%", "2,195개", "3,803,874건"]
    assert m[0]["help"] == "3,880,604 / 3,963,959건"


def test_q095_bronx(stats):
    b = bronx(stats)
    assert b["주거환경"] == pytest.approx(183.0, rel=1e-4)
    assert b["소음"] == pytest.approx(152.8, rel=1e-4)


def test_tract_table():
    t = pd.read_csv(TRACT_CSV, dtype={"GEOID": str}, encoding="utf-8-sig")
    big = t[t.total_pop >= 1000]
    assert len(t) == 2327
    assert len(big) == 2195
    assert big.complaint_count.sum() == 3_803_874
    assert t.complaint_count.sum() == 3_880_604
    ex = t.set_index("GEOID").loc["36081056100"]
    assert (ex.total_pop, ex.complaint_count) == (12, 679)
    assert round(ex.complaint_count / ex.total_pop * 1000) == 56_583


def test_small_denominator_lab(qdir):
    lab = json.loads((qdir / "data" / "labs" / "small_denominator.json").read_text(encoding="utf-8"))
    rows = pd.DataFrame(lab["rows"])
    kept = rows[rows["pop"] >= lab["default_min_pop"]]
    assert lab["default_min_pop"] == 1000
    assert (len(kept), int(kept.n.sum())) == (2195, 3_803_874)
    assert lab["totals"] == {"tracts": 2327, "complaints": 3_880_604}
    assert (len(rows), int(rows.n.sum())) == (2327, 3_880_604)
    assert lab["example"] == {"GEOID": "36081056100", "pop": 12, "n": 679, "per_1k": 56583.3}


def test_stats_schema(qdir):
    files = sorted((qdir / "data").glob("q*.json"))
    assert len(files) == 97
    keys = {"id", "computed_at", "source", "metrics", "charts", "tables", "numbers"}
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        assert set(d) == keys, f.name
        assert f.name == f"q{d['id']:03d}.json"


def test_content_links(qdir):
    concepts = tomllib.loads((qdir / "meta" / "concepts.toml").read_text(encoding="utf-8"))
    for qid in range(1, 101):
        path = qdir / "content" / f"q{qid:03d}.toml"
        assert path.exists(), path.name
        c = tomllib.loads(path.read_text(encoding="utf-8"))
        missing = [k for k in c.get("concepts", []) if k not in concepts]
        assert not missing, f"{path.name}: 개념 사전에 없는 키 {missing}"
        bad = [r for r in c.get("related", []) if not 1 <= r <= 100 or r == qid]
        assert not bad, f"{path.name}: 잘못된 관련 문항 {bad}"
