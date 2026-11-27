"""2025 시장 선거 ED 개표 → Census Tract 배분 (Phase 3B)."""
from __future__ import annotations

import csv

import geopandas as gpd
import pandas as pd

from fetch_ext import ELECTION_DIR, ED_VERSION, load_ext, meta, norm_bbl  # noqa: F401

BOE_COLS = [
    "AD", "ED", "County", "EDAD Status", "Event", "Party/Independent Body",
    "Office/Position Title", "District Key", "VoteFor", "Unit Name", "Tally",
]
CRS_NY = 2263  # 면적 계산용(피트)

CAND_MAP = {
    "Zohran Kwame Mamdani": "mamdani",
    "Andrew M. Cuomo": "cuomo",
    "Curtis A. Sliwa": "sliwa",
}


def parse_tally(s: pd.Series) -> pd.Series:
    """쉼표 제거 → to_numeric(errors='raise'), 빈 값은 0, int."""
    raw = s.copy()
    t = raw.astype(str).str.replace(",", "", regex=False).str.strip()
    empty = raw.isna() | t.isin({"", "nan", "None", "<NA>"})
    t = t.where(~empty, "0")
    return pd.to_numeric(t, errors="raise").astype(int)


def load_results() -> pd.DataFrame:
    """열: ed(int), candidate(str), votes(int)."""
    rows: list[dict] = []
    for path in sorted(ELECTION_DIR.glob("mayor_2025_*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as f:
            for raw in csv.reader(f):
                if len(raw) < 11:
                    continue
                vals = raw[-11:]
                rec = dict(zip(BOE_COLS, vals))
                unit = rec["Unit Name"]
                if " (" not in unit:
                    continue
                candidate = unit.split(" (", 1)[0]
                try:
                    ad = str(int(str(rec["AD"]).strip()))
                    ed_part = str(int(str(rec["ED"]).strip())).zfill(3)
                except (TypeError, ValueError):
                    continue
                ed = int(ad + ed_part)
                rows.append({"ed": ed, "candidate": candidate, "tally": rec["Tally"]})
    if not rows:
        return pd.DataFrame(columns=["ed", "candidate", "votes"])
    df = pd.DataFrame(rows)
    df["votes"] = parse_tally(df["tally"])
    out = df.groupby(["ed", "candidate"], as_index=False)["votes"].sum()
    return out[["ed", "candidate", "votes"]]


def ed_votes() -> pd.DataFrame:
    """ED별: ed, mamdani, cuomo, sliwa, other, total. total==0 ED는 제외."""
    r = load_results()
    if r.empty:
        return pd.DataFrame(columns=["ed", "mamdani", "cuomo", "sliwa", "other", "total"])
    r = r.copy()
    r["col"] = r["candidate"].map(CAND_MAP).fillna("other")
    piv = (r.groupby(["ed", "col"], as_index=False)["votes"].sum()
           .pivot(index="ed", columns="col", values="votes").fillna(0))
    for c in ("mamdani", "cuomo", "sliwa", "other"):
        if c not in piv.columns:
            piv[c] = 0
    piv = piv.reset_index()
    piv["total"] = piv["mamdani"] + piv["cuomo"] + piv["sliwa"] + piv["other"]
    piv = piv[piv["total"] > 0]
    return piv[["ed", "mamdani", "cuomo", "sliwa", "other", "total"]].astype(
        {"ed": int, "mamdani": int, "cuomo": int, "sliwa": int, "other": int, "total": int})


def load_ed_shapes() -> gpd.GeoDataFrame:
    """열: ed(int), geometry (EPSG:2263)."""
    matches = list((ELECTION_DIR / f"nyed_{ED_VERSION}").glob("**/nyed.shp"))
    if not matches:
        matches = list(ELECTION_DIR.glob("**/nyed.shp"))
    if not matches:
        raise FileNotFoundError(f"nyed.shp 없음: {ELECTION_DIR}")
    g = gpd.read_file(matches[0])
    g = g.rename(columns={"ElectDist": "ed"})
    g["ed"] = g["ed"].astype(int)
    if g.crs is None:
        g = g.set_crs(epsg=CRS_NY)
    else:
        g = g.to_crs(epsg=CRS_NY)
    return g[["ed", "geometry"]].copy()


def _area_weights(eds: list[int], ed_g: gpd.GeoDataFrame) -> pd.DataFrame:
    """세대가 없는 ED를 Tract 겹침 면적 비율로 배분. 분모는 ED 전체 면적."""
    from joined import TRACT_GEO

    if not eds:
        return pd.DataFrame(columns=["ed", "GEOID", "w", "method"])
    tracts_g = gpd.read_file(TRACT_GEO)
    if tracts_g.crs is None:
        tracts_g = tracts_g.set_crs("EPSG:4326")
    tracts_g = tracts_g.to_crs(epsg=CRS_NY)[["GEOID", "geometry"]]
    sub = ed_g[ed_g["ed"].isin(eds)][["ed", "geometry"]].copy()
    ed_area = sub.set_index("ed").geometry.area
    inter = gpd.overlay(sub, tracts_g, how="intersection")
    if inter.empty:
        return pd.DataFrame(columns=["ed", "GEOID", "w", "method"])
    inter["_area"] = inter.geometry.area
    inter["w"] = inter["_area"] / inter["ed"].map(ed_area)
    out = inter.groupby(["ed", "GEOID"], as_index=False)["w"].sum()
    out["method"] = "area"
    return out[["ed", "GEOID", "w", "method"]]

def ed_tract_weights() -> pd.DataFrame:
    """열: ed, GEOID, w, method('units'|'area')."""
    from joined import points_to_geoid

    pluto = load_ext("pluto_xy").copy()
    pluto = pluto[pluto["unitsres"].notna() & (pluto["unitsres"] > 0)]
    pluto = pluto[pluto["latitude"].notna() & pluto["longitude"].notna()].copy()
    pluto["GEOID"] = points_to_geoid(pluto)
    pluto = pluto[pluto["GEOID"].notna()].copy()

    ed_g = load_ed_shapes()
    pts = gpd.GeoDataFrame(
        pluto[["GEOID", "unitsres"]].copy(),
        geometry=gpd.points_from_xy(pluto["longitude"], pluto["latitude"]),
        crs="EPSG:4326",
    ).to_crs(epsg=CRS_NY)
    joined = gpd.sjoin(pts, ed_g, how="inner", predicate="within")
    units = (joined.groupby(["ed", "GEOID"], as_index=False)["unitsres"].sum()
             .rename(columns={"unitsres": "u"}))
    ed_u = units.groupby("ed")["u"].transform("sum")
    units["w"] = units["u"] / ed_u
    units["method"] = "units"
    units_w = units[["ed", "GEOID", "w", "method"]]

    votes = ed_votes()
    missing = sorted(set(votes["ed"]) - set(units_w["ed"].unique()))
    area_w = _area_weights(missing, ed_g)
    return pd.concat([units_w, area_w], ignore_index=True)


def _weights_all_area() -> pd.DataFrame:
    votes = ed_votes()
    return _area_weights(votes["ed"].tolist(), load_ed_shapes())


def tract_votes(method: str = "units") -> pd.DataFrame:
    """열: GEOID, mamdani, cuomo, sliwa, other, total, area_share.
    method='units': 세대 배분 + 세대 없는 ED만 면적.
    method='area': 모든 ED를 면적으로(99번 비교용).
    """
    votes = ed_votes()
    if method == "area":
        w = _weights_all_area()
    else:
        w = ed_tract_weights()
    m = votes.merge(w, on="ed", how="inner")
    for c in ("mamdani", "cuomo", "sliwa", "other", "total"):
        m[c] = m[c] * m["w"]
    by = m.groupby("GEOID", as_index=False)[["mamdani", "cuomo", "sliwa", "other", "total"]].sum()
    area_part = (m[m["method"] == "area"].groupby("GEOID")["total"].sum()
                 if "method" in m.columns else pd.Series(dtype=float))
    by["area_share"] = by["GEOID"].map(area_part).fillna(0.0) / by["total"].replace(0, pd.NA)
    by["area_share"] = by["area_share"].fillna(0.0)
    if method == "area":
        by["area_share"] = 1.0
    return by
