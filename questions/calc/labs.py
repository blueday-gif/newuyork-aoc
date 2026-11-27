"""체험실 자료. 앱의 @st.fragment 체험 위젯이 읽는 작은 JSON을 만든다.
실행: py -3 questions/calc/labs.py [이름 ...]
출력: questions/data/labs/{이름}.json
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BORO_ACS, BORO_KO, DATA_OUT, ROOT  # noqa: E402
from fetch_ext import load_ext, meta, norm_bbl  # noqa: E402

LAB_OUT = DATA_OUT / "labs"
TRACT_CSV = ROOT / "data" / "processed" / "nyc311_tract_complaints.csv"
DEFAULT_MIN_POP = 1000          # 분석 대상 Tract 기준(common.tracts와 같음)
EXAMPLE_GEOID = "36081056100"   # 인구 12명, 민원 679건 → 1,000명당 56,583건

DID_POLICY = "2024-11-12"
DID_EXCLUDE_CD = [109, 302]
DID_WINDOWS = {
    "2022": ("2021-12-01", "2022-09-01"),
    "2023": ("2022-12-01", "2023-09-01"),
    "2024": ("2023-12-01", "2024-09-01"),
    "2025": ("2024-12-01", "2025-09-01"),
}  # [시작, 끝)
DID_MONTHS = ("2021-01", "2025-08")


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


def did_containerization() -> Path:
    """쓰레기통 의무화 DiD. Rat Sighting만, 2025-08까지."""
    pluto = load_ext("pluto_xy").copy()
    pluto["bbl"] = norm_bbl(pluto["bbl"])
    pluto = pluto[pluto["bbl"].notna()].drop_duplicates("bbl", keep="first")
    pluto = pluto[pluto["unitsres"].notna() & (pluto["unitsres"] > 0)]
    pluto = pluto[~pluto["cd"].isin(DID_EXCLUDE_CD)].copy()
    pluto["group"] = pd.Series(pd.NA, index=pluto.index, dtype=object)
    pluto.loc[pluto["unitsres"].between(1, 9, inclusive="both"), "group"] = "T"
    pluto.loc[pluto["unitsres"] >= 10, "group"] = "C"
    pluto = pluto[pluto["group"].notna()].copy()

    units = pluto.groupby("group")["unitsres"].sum()
    buildings = pluto.groupby("group").size()

    rats = load_ext("rodent_311_history").copy()
    rats = rats[rats["descriptor"].astype(str) == "Rat Sighting"].copy()
    rats["bbl"] = norm_bbl(rats["bbl"])
    rats = rats[rats["bbl"].notna()]
    rats = rats.merge(pluto[["bbl", "group"]], on="bbl", how="inner")
    rats["created_date"] = pd.to_datetime(rats["created_date"])
    rats["month"] = rats["created_date"].dt.strftime("%Y-%m")

    month_index = pd.period_range(DID_MONTHS[0], DID_MONTHS[1], freq="M").strftime("%Y-%m").tolist()
    monthly_rows = []
    for mo in month_index:
        g = rats[rats["month"] == mo]
        counts = g.groupby("group").size()
        row = {"month": mo}
        for lab in ("T", "C"):
            n = float(counts.get(lab, 0))
            u = float(units.get(lab, 0))
            row[lab] = (n / u * 1000) if u else 0.0
        monthly_rows.append(row)

    window_rows = []
    for label, (start, end) in DID_WINDOWS.items():
        mask = (rats["created_date"] >= pd.Timestamp(start)) & (rats["created_date"] < pd.Timestamp(end))
        g = rats[mask]
        counts = g.groupby("group").size()
        row = {"label": label, "start": start, "end": end}
        for lab in ("T", "C"):
            n = float(counts.get(lab, 0))
            u = float(units.get(lab, 0))
            row[lab] = (n / u * 1000) if u else 0.0
        window_rows.append(row)

    def _round4(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
        out = []
        for r in rows:
            rr = dict(r)
            for k in keys:
                rr[k] = round(float(rr[k]), 4)
            out.append(rr)
        return out

    doc = {
        "id": "did_containerization",
        "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "policy_date": DID_POLICY,
        "excluded_cd": list(DID_EXCLUDE_CD),
        "sources": [meta("rodent_311_history"), meta("pluto_xy")],
        "groups": {
            "T": {"label": "1~9세대(의무화)",
                  "units": int(units.get("T", 0)),
                  "buildings": int(buildings.get("T", 0))},
            "C": {"label": "10세대 이상(아직 아님)",
                  "units": int(units.get("C", 0)),
                  "buildings": int(buildings.get("C", 0))},
        },
        "monthly": _round4(monthly_rows, ("T", "C")),
        "windows": _round4(window_rows, ("T", "C")),
        "notes": (
            "311 쥐 민원 중 '쥐 목격'(Rat Sighting)만 쓰고 2025-08에서 끊었다. "
            "'쥐 흔적'·'생쥐 목격' 신고가 2025-09부터 갑자기 약 1/4로 줄어 분류가 바뀐 것으로 보이기 때문이다."
        ),
    }
    return save_lab("did_containerization", doc)


if __name__ == "__main__":
    names = sys.argv[1:] or ["small_denominator", "did"]
    for name in names:
        if name in ("did", "did_containerization"):
            did_containerization()
        elif name == "small_denominator":
            save_lab("small_denominator", small_denominator())
        else:
            raise SystemExit(f"알 수 없는 체험실: {name}")
