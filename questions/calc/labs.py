"""체험실 자료. 앱의 @st.fragment 체험 위젯이 읽는 작은 JSON을 만든다.
실행: py -3 questions/calc/labs.py
출력: questions/data/labs/{이름}.json
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BORO_ACS, BORO_KO, DATA_OUT, ROOT  # noqa: E402

LAB_OUT = DATA_OUT / "labs"
TRACT_CSV = ROOT / "data" / "processed" / "nyc311_tract_complaints.csv"
DEFAULT_MIN_POP = 1000          # 분석 대상 Tract 기준(common.tracts와 같음)
EXAMPLE_GEOID = "36081056100"   # 인구 12명, 민원 679건 → 1,000명당 56,583건


def small_denominator() -> dict:
    """작은 분모의 함정(74·95번): Tract 2,327개 전부의 인구와 민원 수.
    1,000명당 값은 넣지 않는다. 인구 0명 Tract(84개)가 있어 화면이 문턱값에 따라 계산한다."""
    t = pd.read_csv(TRACT_CSV, dtype={"GEOID": str}, encoding="utf-8-sig")
    t["boro"] = t.borough.map(BORO_ACS).map(BORO_KO)
    if t.boro.isna().any():
        raise ValueError(f"자치구 이름을 바꾸지 못했다: {t.loc[t.boro.isna(), 'borough'].unique()}")
    t["pop"] = t.total_pop.round().astype(int)
    t["n"] = t.complaint_count.astype(int)
    ex = t.set_index("GEOID").loc[EXAMPLE_GEOID]
    return {
        "id": "small_denominator",
        "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "data/processed/nyc311_tract_complaints.csv",
        "default_min_pop": DEFAULT_MIN_POP,
        "totals": {"tracts": int(len(t)), "complaints": int(t.n.sum())},
        "example": {"GEOID": EXAMPLE_GEOID, "pop": int(ex["pop"]), "n": int(ex.n),
                    "per_1k": round(float(ex.n / ex["pop"] * 1000), 1)},
        "rows": t[["GEOID", "boro", "pop", "n"]].to_dict("records"),
    }


def save_lab(name: str, doc: dict) -> Path:
    LAB_OUT.mkdir(parents=True, exist_ok=True)
    path = LAB_OUT / f"{name}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("saved", path.relative_to(ROOT), f"{path.stat().st_size / 1024:.0f}KB")
    return path


if __name__ == "__main__":
    save_lab("small_denominator", small_denominator())
