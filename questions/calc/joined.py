"""311과 외부 자료를 결합해 문항의 결합 결과를 만든다 (Phase 3A·3B).
실행: py -3 questions/calc/joined.py [번호 ...]
결과는 questions/data/joined/q###.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BORO_KO, INC_Q, Q5, ROOT, category, load_311, records,  # noqa: E402
                    tracts, with_tract)
from fetch_ext import load_ext, meta, norm_bbl  # noqa: E402
from part07 import HPD_KO, has_bbl  # noqa: E402
from part10 import WEATHER, flood  # noqa: E402

JOINED_OUT = Path(__file__).resolve().parents[1] / "data" / "joined"
TRACT_GEO = ROOT / "data" / "processed" / "nyc_acs_2024_5yr.geojson"
RAT_FOUND = ["Failed for Rat Activity", "Failed for Rat Activity and Other Reason"]
HEAT_VIOL = r"27-2029|27-2031"
PERIOD = ("2025-11-01", "2026-10-31")


def points_to_geoid(df: pd.DataFrame, lat: str = "latitude", lon: str = "longitude") -> pd.Series:
    """좌표 → Census Tract GEOID. 못 찾으면 NA. df.index에 맞춘 시리즈."""
    import geopandas as gpd

    out = pd.Series(pd.NA, index=df.index, dtype=object)
    ok = df[lat].notna() & df[lon].notna()
    if not ok.any():
        return out
    pts = gpd.GeoDataFrame(
        {"_i": df.index[ok].to_numpy()},
        geometry=gpd.points_from_xy(df.loc[ok, lon], df.loc[ok, lat]),
        crs="EPSG:4326",
    )
    tracts_g = gpd.read_file(TRACT_GEO)
    if tracts_g.crs is None:
        tracts_g = tracts_g.set_crs("EPSG:4326")
    else:
        tracts_g = tracts_g.to_crs("EPSG:4326")
    tracts_g = tracts_g[["GEOID", "geometry"]]
    joined = gpd.sjoin(pts, tracts_g, how="left", predicate="within")
    joined = joined.drop_duplicates("_i", keep="first")
    out.loc[joined["_i"].to_numpy()] = joined["GEOID"].to_numpy()
    return out


def heat_violations(v: pd.DataFrame) -> pd.DataFrame:
    return v[v["novdescription"].astype(str).str.contains(HEAT_VIOL, na=False)].copy()


def source(name: str) -> dict:
    m = meta(name)
    return {k: m[k] for k in ("name", "dataset", "url", "period", "rows", "fetched_at")}


def save_joined(qid, sources, metrics, charts, tables=None, numbers=None) -> Path:
    JOINED_OUT.mkdir(parents=True, exist_ok=True)
    doc = {
        "id": qid,
        "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sources": sources,
        "metrics": metrics,
        "charts": charts,
        "tables": tables or [],
        "numbers": numbers or {},
    }
    path = JOINED_OUT / f"q{qid:03d}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", path.name)
    return path


def _in_period(s: pd.Series, start: str, end: str) -> pd.Series:
    d = pd.to_datetime(s).dt.normalize()
    return (d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end))


def _noaa_daily() -> pd.DataFrame:
    w = load_ext("noaa_centralpark").copy()
    w["DATE"] = pd.to_datetime(w["DATE"]).dt.normalize()
    return w


# ── q057 ───────────────────────────────────────────────────────────

def q057(df: pd.DataFrame) -> None:
    start, end = "2025-11-01", "2026-03-31"
    heat = df[(df.problem == "HEAT/HOT WATER") & _in_period(df.date, start, end)]
    idx = pd.date_range(start, end, freq="D")
    daily = heat.groupby("date").size().reindex(idx, fill_value=0).rename("난방 민원")
    w = _noaa_daily().set_index("DATE")
    m = pd.DataFrame({"난방 민원": daily, "최저기온(°C)": w["TMIN"].reindex(idx)})
    m = m.dropna(subset=["최저기온(°C)"])

    below = m[m["최저기온(°C)"] < 0]
    mid = m[(m["최저기온(°C)"] >= 0) & (m["최저기온(°C)"] < 10)]
    med_b = float(below["난방 민원"].median()) if len(below) else float("nan")
    med_m = float(mid["난방 민원"].median()) if len(mid) else float("nan")
    ratio = round(med_b / med_m, 1) if med_m and med_m > 0 else float("nan")
    rho, _ = spearmanr(m["최저기온(°C)"], m["난방 민원"])
    rho = float(rho)

    bins = [-np.inf, -10, -5, 0, 5, 10, np.inf]
    labels = ["-10 미만", "-10~-5", "-5~0", "0~5", "5~10", "10 이상"]
    m = m.copy()
    m["최저기온 구간"] = pd.cut(m["최저기온(°C)"], bins=bins, labels=labels, right=False)
    bar = (m.groupby("최저기온 구간", observed=True)["난방 민원"].median()
           .reindex(labels).rename("하루 난방 민원").reset_index())
    bar["하루 난방 민원"] = bar["하루 난방 민원"].round(1)

    save_joined(
        57,
        sources=[source("noaa_centralpark")],
        metrics=[
            {"label": "0°C 미만 날의 하루 중앙값", "value": f"{med_b:,.0f}건", "help": f"{len(below)}일"},
            {"label": "0~10°C 날의 하루 중앙값", "value": f"{med_m:,.0f}건", "help": f"{len(mid)}일"},
            {"label": "배율", "value": f"{ratio:.1f}배",
             "help": "BuildingHealthX는 0°C 아래에서 약 2배라고 보고했다"},
            {"label": "순위 상관(최저기온 vs 민원)", "value": f"{rho:.2f}"},
        ],
        charts=[
            {"title": "최저기온 구간별 하루 난방 민원(중앙값)", "kind": "bar",
             "x": "최저기온 구간", "y": "하루 난방 민원", "rows": records(bar),
             "caption": "같은 겨울 안에서 추운 날일수록 신고가 많다. 요일·연휴 효과는 빼지 않았다."},
            {"title": "최저기온과 하루 난방 민원", "kind": "scatter",
             "x": "최저기온(°C)", "y": "난방 민원", "trend": True,
             "rows": records(m[["최저기온(°C)", "난방 민원"]])},
        ],
        numbers={
            "days_below0": int(len(below)),
            "days_0_10": int(len(mid)),
            "median_below0": round(med_b, 1),
            "median_0_10": round(med_m, 1),
            "ratio": ratio,
            "spearman": round(rho, 2),
        },
    )


# ── q058 ───────────────────────────────────────────────────────────

def q058(df: pd.DataFrame) -> None:
    start, end = "2026-06-01", "2026-08-31"
    s = df[_in_period(df.date, start, end)].copy()
    det = s.detail.astype(str)
    outage = s[(s.problem == "ELECTRIC") & (det == "POWER OUTAGE")]
    hyd = s[s.problem.astype(str).isin(["Water System", "Water Maintenance"])
            & det.str.contains("Hydrant Running", case=False)]
    idx = pd.date_range(start, end, freq="D")
    d_out = outage.groupby("date").size().reindex(idx, fill_value=0)
    d_hyd = hyd.groupby("date").size().reindex(idx, fill_value=0)
    w = _noaa_daily().set_index("DATE")
    tmin = w["TMIN"].reindex(idx)
    tropical = tmin > 20
    n_trop = int(tropical.fillna(False).sum())

    def _mean(series, mask):
        m = mask.fillna(False)
        return float(series[m].mean()) if m.any() else float("nan")

    out_t, out_o = _mean(d_out, tropical), _mean(d_out, ~tropical)
    hyd_t, hyd_o = _mean(d_hyd, tropical), _mean(d_hyd, ~tropical)
    ratio_out = round(out_t / out_o, 1) if out_o and out_o > 0 else float("nan")
    ratio_hyd = round(hyd_t / hyd_o, 1) if hyd_o and hyd_o > 0 else float("nan")

    rows = pd.DataFrame([
        {"민원": "정전", "날": "열대야", "하루 평균": round(out_t, 1)},
        {"민원": "정전", "날": "그 밖의 날", "하루 평균": round(out_o, 1)},
        {"민원": "소화전 열림", "날": "열대야", "하루 평균": round(hyd_t, 1)},
        {"민원": "소화전 열림", "날": "그 밖의 날", "하루 평균": round(hyd_o, 1)},
    ])
    save_joined(
        58,
        sources=[source("noaa_centralpark")],
        metrics=[
            {"label": "열대야 일수", "value": f"{n_trop}일", "help": "최저기온 20°C 초과, 6~8월"},
            {"label": "정전 민원 배율", "value": f"{ratio_out:.1f}배"},
            {"label": "소화전 민원 배율", "value": f"{ratio_hyd:.1f}배"},
        ],
        charts=[{
            "title": "여름 하루 평균 민원: 열대야 vs 그 밖의 날", "kind": "group",
            "x": "민원", "color": "날", "y": "하루 평균",
            "colors": {"열대야": "#c94f6d", "그 밖의 날": "#9fb3d1"},
            "rows": records(rows),
            "caption": "열대야에는 냉방 부하로 정전이, 더위를 피하려 소화전을 여는 일이 늘어난다는 가설을 확인한다.",
        }],
    )


# ── q096 ───────────────────────────────────────────────────────────

def q096(df: pd.DataFrame) -> None:
    start, end = PERIOD
    idx = pd.date_range(start, end, freq="D")
    p, d = df.problem.astype(str), df.detail.astype(str)
    w = _noaa_daily().set_index("DATE")
    pairs = [
        ("눈·얼음", "SNOW"),
        ("난방·온수", "TMIN"),
        ("빗물받이 막힘·도로 침수", "PRCP"),
        ("소화전 열림", "TMAX"),
    ]
    table_rows = []
    metrics = []
    for lab, var in pairs:
        daily = df[WEATHER[lab](p, d)].groupby("date").size().reindex(idx, fill_value=0)
        weather = w[var].reindex(idx)
        both = pd.DataFrame({"민원": daily, "날씨": weather}).dropna()
        rho0, _ = spearmanr(both["민원"], both["날씨"])
        # 다음 날: t+1 민원 vs t 날씨
        nxt = pd.DataFrame({
            "민원": daily.shift(-1),
            "날씨": weather,
        }).dropna()
        rho1, _ = spearmanr(nxt["민원"], nxt["날씨"])
        rho0, rho1 = float(rho0), float(rho1)
        table_rows.append({
            "민원": lab, "기상 변수": var,
            "같은 날 ρ": round(rho0, 2), "다음 날 ρ": round(rho1, 2),
        })
        best = rho0 if abs(rho0) >= abs(rho1) else rho1
        when = "같은 날" if abs(rho0) >= abs(rho1) else "다음 날"
        metrics.append({"label": lab, "value": f"{best:.2f}", "help": f"{var} · {when}"})

    prcp = w["PRCP"].reindex(idx)
    flood_daily = df[WEATHER["빗물받이 막힘·도로 침수"](p, d)].groupby("date").size().reindex(idx, fill_value=0)
    scat = pd.DataFrame({"강수량(mm)": prcp, "민원": flood_daily}).dropna()

    save_joined(
        96,
        sources=[source("noaa_centralpark")],
        metrics=metrics,
        charts=[{
            "title": "강수량과 하루 침수 관련 민원", "kind": "scatter",
            "x": "강수량(mm)", "y": "민원", "trend": True,
            "rows": records(scat),
            "caption": "비가 많이 온 날 신고가 솟는다. 같은 강수량에도 날마다 차이가 크다.",
        }],
        tables=[{"title": "날씨 민원과 기상 변수의 순위 상관", "rows": table_rows}],
    )


# ── q007 ───────────────────────────────────────────────────────────

def q007(df: pd.DataFrame) -> None:
    start, end = "2025-11-01", "2026-05-31"
    heat = df[(df.problem == "HEAT/HOT WATER") & _in_period(df.date, start, end)].copy()
    heat["bbl_n"] = norm_bbl(heat["bbl"])
    heat = heat[heat["bbl_n"].notna()]
    by_c = heat.groupby("bbl_n").size().rename("난방 민원")
    addr = heat.groupby("bbl_n")["addr_n"].agg(lambda s: s.mode().iat[0] if len(s.mode()) else "")

    v = heat_violations(load_ext("hpd_violations"))
    v = v[_in_period(v["inspectiondate"], start, end)].copy()
    v["bbl_n"] = norm_bbl(v["bbl"])
    v = v[v["bbl_n"].notna()]
    by_v = v.groupby("bbl_n").size().rename("위반")

    j = pd.concat([by_c, by_v], axis=1).fillna(0)
    j["난방 민원"] = j["난방 민원"].astype(int)
    j["위반"] = j["위반"].astype(int)
    n_all = len(j)
    both = (j["난방 민원"] > 0) & (j["위반"] > 0)
    only_c = (j["난방 민원"] > 0) & (j["위반"] == 0)
    only_v = (j["난방 민원"] == 0) & (j["위반"] > 0)
    ten_zero = (j["난방 민원"] >= 10) & (j["위반"] == 0)

    def pct(n):
        return round(n / n_all * 100, 1) if n_all else 0.0

    bins_lab = ["1건", "2–4건", "5–9건", "10–49건", "50건 이상"]
    reported = j[j["난방 민원"] > 0].copy()
    reported["건물당 민원"] = pd.cut(
        reported["난방 민원"],
        bins=[0, 1, 4, 9, 49, np.inf],
        labels=bins_lab,
        right=True,
    )
    bar = (reported.assign(_has_v=reported["위반"] > 0)
           .groupby("건물당 민원", observed=True)["_has_v"]
           .mean().mul(100).reindex(bins_lab)
           .rename("위반 있는 건물(%)").reset_index())
    bar["위반 있는 건물(%)"] = bar["위반 있는 건물(%)"].round(1)

    top = (j[ten_zero].sort_values("난방 민원", ascending=False).head(10)
           .reset_index().rename(columns={"bbl_n": "BBL"}))
    top["주소"] = top["BBL"].map(addr)
    top = top[["BBL", "난방 민원", "주소"]]

    save_joined(
        7,
        sources=[source("hpd_violations")],
        metrics=[
            {"label": "신고됐고 위반도 있는 건물", "value": f"{int(both.sum()):,}동",
             "help": f"{pct(int(both.sum())):.1f}%"},
            {"label": "신고됐지만 위반이 없는 건물", "value": f"{int(only_c.sum()):,}동",
             "help": f"{pct(int(only_c.sum())):.1f}%"},
            {"label": "위반은 있는데 신고가 없던 건물", "value": f"{int(only_v.sum()):,}동",
             "help": f"{pct(int(only_v.sum())):.1f}%"},
            {"label": "10건 이상 신고·위반 0 건물", "value": f"{int(ten_zero.sum()):,}동"},
        ],
        charts=[{
            "title": "건물당 난방 민원 수와 위반이 확인된 비율", "kind": "bar",
            "x": "건물당 민원", "y": "위반 있는 건물(%)", "rows": records(bar),
            "caption": "많이 신고된 건물일수록 위반이 확인되는 비율이 높은지 본다. 위반 없음은 '문제없음'이 아니라 '점검에서 확인 못 함'일 수 있다.",
        }],
        tables=[{"title": "10건 이상 신고됐는데 위반이 없는 건물 상위 10", "rows": records(top)}],
    )


# ── q072 ───────────────────────────────────────────────────────────

def q072(df: pd.DataFrame) -> None:
    hpd = has_bbl(df[df.agency.astype(str) == "HPD"])
    hpd = hpd[hpd.problem.astype(str).isin(list(HPD_KO))].copy()
    hpd["bbl_n"] = norm_bbl(hpd["bbl"])
    hpd = hpd[hpd["bbl_n"].notna()]
    m = pd.crosstab(hpd["bbl_n"], hpd.problem.astype(str)).gt(0)
    ntype = m.sum(axis=1)

    def bucket(n):
        if n == 1:
            return "1가지"
        if n <= 3:
            return "2–3가지"
        if n <= 5:
            return "4–5가지"
        return "6가지 이상"

    order = ["1가지", "2–3가지", "4–5가지", "6가지 이상"]
    bld = pd.DataFrame({"ntype": ntype, "묶음": ntype.map(bucket)})

    v = load_ext("hpd_violations").copy()
    v = v[_in_period(v["inspectiondate"], "2024-11-01", "2025-10-31")]
    v["bbl_n"] = norm_bbl(v["bbl"])
    v = v[v["bbl_n"].notna()]
    prior = v.groupby("bbl_n").size().rename("이전 위반")
    prior_c = v[v["class"].astype(str) == "C"].groupby("bbl_n").size().rename("C위반")

    pluto = load_ext("pluto").copy()
    pluto["bbl_n"] = norm_bbl(pluto["bbl"])
    pluto = pluto[pluto["bbl_n"].notna() & (pluto["unitsres"] > 0)]
    units = pluto.groupby("bbl_n")["unitsres"].first()

    bld = bld.join(prior, how="left").join(prior_c, how="left").join(units.rename("unitsres"), how="left")
    bld["이전 위반"] = bld["이전 위반"].fillna(0)
    bld["C위반"] = bld["C위반"].fillna(0)
    n_bld = len(bld)
    with_u = bld["unitsres"].notna()
    pluto_pct = round(with_u.mean() * 100, 1)
    use = bld[with_u].copy()

    rows = []
    raw_per: dict[str, float] = {}
    for lab in order:
        g = use[use["묶음"] == lab]
        n_b = len(g)
        u_sum = float(g["unitsres"].sum())
        v_sum = float(g["이전 위반"].sum())
        c_sum = float(g["C위반"].sum())
        per_raw = (v_sum / u_sum) if u_sum else 0.0
        raw_per[lab] = per_raw
        c_pct = round(c_sum / v_sum * 100, 1) if v_sum else 0.0
        rows.append({
            "민원 유형 수": lab,
            "건물 수": n_b,
            "세대 수 합": int(u_sum),
            "이전 위반 합": int(v_sum),
            "세대당 이전 위반": round(per_raw, 2),
            "C등급 비율(%)": c_pct,
        })
    tbl = pd.DataFrame(rows)
    per6 = raw_per["6가지 이상"]
    per1 = raw_per["1가지"]
    ratio = round(per6 / per1, 1) if per1 else float("nan")

    save_joined(
        72,
        sources=[source("hpd_violations"), source("pluto")],
        metrics=[
            {"label": "PLUTO 세대 수가 붙은 건물", "value": f"{pluto_pct:.1f}%",
             "help": f"{int(with_u.sum()):,} / {n_bld:,}동"},
            {"label": "6가지 이상 건물의 세대당 이전 위반", "value": f"{per6:.2f}"},
            {"label": "1가지 건물의 세대당 이전 위반", "value": f"{per1:.2f}"},
            {"label": "배율", "value": f"{ratio:.1f}배",
             "help": "ikrar.dev는 12~44배라고 보고했다(기간·정의가 다르다)"},
        ],
        charts=[{
            "title": "민원 유형 수별 세대당 신고 이전 1년 위반", "kind": "bar",
            "x": "민원 유형 수", "y": "세대당 이전 위반",
            "rows": records(tbl[["민원 유형 수", "세대당 이전 위반"]]),
            "caption": "311 기간(2025-11~) 이전 1년의 위반이다. '신고 → 점검 → 위반'의 행정 순환을 피하려고 시간을 앞으로 뺐다.",
        }],
        tables=[{"title": "민원 유형 수별 이전 위반", "rows": records(tbl)}],
    )


# ── q075 ───────────────────────────────────────────────────────────

def q075(df: pd.DataFrame) -> None:
    d = df.copy()
    d["bbl_n"] = norm_bbl(d["bbl"])
    with_bbl = d[d["bbl_n"].notna()]
    pluto = load_ext("pluto").copy()
    pluto["bbl_n"] = norm_bbl(pluto["bbl"])
    pluto = pluto[pluto["bbl_n"].notna() & (pluto["unitsres"] > 0)]
    units = pluto.groupby("bbl_n")["unitsres"].first()

    linked = with_bbl.merge(units.rename("unitsres"), left_on="bbl_n", right_index=True, how="inner")
    link_pct = round(len(linked) / len(with_bbl) * 100, 1) if len(with_bbl) else 0.0
    linked = linked.copy()
    linked["분야"] = category(linked["problem"])
    linked["건물 규모"] = pd.cut(
        linked["unitsres"],
        bins=[0, 2, 9, 49, 99, np.inf],
        labels=["1–2세대", "3–9세대", "10–49세대", "50–99세대", "100세대 이상"],
        right=True,
    )
    order = ["1–2세대", "3–9세대", "10–49세대", "50–99세대", "100세대 이상"]
    blds = linked.groupby("bbl_n").agg(unitsres=("unitsres", "first"), 규모=("건물 규모", "first"))
    n_blds = len(blds)

    rows = []
    chart_rows = []
    rates_raw: dict[str, float] = {}
    for lab in order:
        g = linked[linked["건물 규모"] == lab]
        b = blds[blds["규모"] == lab]
        u_sum = float(b["unitsres"].sum())
        n_b = len(b)
        row = {"건물 규모": lab, "건물 수": n_b, "세대 수 합": int(u_sum)}
        for cat in ("주거환경", "소음"):
            n = int((g["분야"] == cat).sum())
            rate_raw = (n / u_sum * 100) if u_sum else 0.0
            rate = round(rate_raw, 1)
            row[f"{cat} 민원"] = n
            row[f"{cat} 100세대당"] = rate
            chart_rows.append({"건물 규모": lab, "분야": cat, "100세대당 민원": rate})
            if cat == "주거환경":
                rates_raw[lab] = rate_raw
        rows.append(row)
    tbl = pd.DataFrame(rows)
    den = rates_raw.get("1–2세대")
    ratio = round(rates_raw["100세대 이상"] / den, 1) if den else float("nan")

    save_joined(
        75,
        sources=[source("pluto")],
        metrics=[
            {"label": "PLUTO 주거 필지와 연결된 민원", "value": f"{link_pct:.1f}%",
             "help": f"{len(linked):,} / {len(with_bbl):,}건"},
            {"label": "연결된 건물", "value": f"{n_blds:,}동"},
            {"label": "주거환경: 100세대 이상 ÷ 1–2세대", "value": f"{ratio:.1f}배"},
        ],
        charts=[{
            "title": "건물 규모별 100세대당 민원", "kind": "group",
            "x": "건물 규모", "color": "분야", "y": "100세대당 민원",
            "colors": {"주거환경": "#2457a7", "소음": "#e07b39"},
            "rows": chart_rows,
            "caption": "같은 동네 안의 비교가 아니라 시 전체 비교다. 대형 건물이 몰린 동네의 특성이 섞여 있다.",
        }],
        tables=[{"title": "건물 규모별 민원", "rows": records(tbl)}],
    )


# ── q097 ───────────────────────────────────────────────────────────

def q097(df: pd.DataFrame, dt: pd.DataFrame) -> None:
    t = tracts()
    t_idx = t.set_index("GEOID")

    rodent_311 = dt[dt.problem.astype(str) == "Rodent"]
    heat_311 = dt[dt.problem.astype(str) == "HEAT/HOT WATER"]

    insp = load_ext("rodent_inspections").copy()
    n_insp = len(insp)
    insp["GEOID"] = points_to_geoid(insp)
    insp_ok = insp[insp["GEOID"].notna() & insp["GEOID"].isin(t_idx.index)]
    coord_pct = round(insp["GEOID"].notna().mean() * 100, 1)
    rat_ok = insp_ok[insp_ok["result"].astype(str).isin(RAT_FOUND)]
    n_rat_found = int(insp["result"].astype(str).isin(RAT_FOUND).sum())

    hv = heat_violations(load_ext("hpd_violations"))
    hv = hv[_in_period(hv["inspectiondate"], *PERIOD)].copy()
    hv["GEOID"] = points_to_geoid(hv)
    hv_ok = hv[hv["GEOID"].notna() & hv["GEOID"].isin(t_idx.index)]

    pop = t.groupby("inc_q", observed=True)["total_pop"].sum().reindex(INC_Q)
    rent = t.groupby("inc_q", observed=True)["renter_occupied"].sum().reindex(INC_Q)

    r311 = rodent_311.groupby("inc_q", observed=True).size().reindex(INC_Q, fill_value=0)
    r_insp = rat_ok.groupby(rat_ok["GEOID"].map(t_idx["inc_q"]), observed=True).size().reindex(INC_Q, fill_value=0)
    h311 = heat_311.groupby("inc_q", observed=True).size().reindex(INC_Q, fill_value=0)
    h_viol = hv_ok.groupby(hv_ok["GEOID"].map(t_idx["inc_q"]), observed=True).size().reindex(INC_Q, fill_value=0)

    rows = []
    chart_rat = []
    for q in INC_Q:
        r_raw = float(r311[q]) / float(pop[q]) * 1000 if pop[q] else 0.0
        i_raw = float(r_insp[q]) / float(pop[q]) * 1000 if pop[q] else 0.0
        r_rate = round(r_raw, 1)
        i_rate = round(i_raw, 1)
        r_ratio = round(r_raw / i_raw, 2) if i_raw else float("nan")
        h_raw = float(h311[q]) / float(rent[q]) * 1000 if rent[q] else 0.0
        v_raw = float(h_viol[q]) / float(rent[q]) * 1000 if rent[q] else 0.0
        h_rate = round(h_raw, 1)
        v_rate = round(v_raw, 1)
        h_ratio = round(h_raw / v_raw, 2) if v_raw else float("nan")
        rows.append({
            "소득 5분위": q,
            "311 쥐 신고": r_rate,
            "점검에서 쥐 확인": i_rate,
            "쥐: 신고 ÷ 확인": r_ratio,
            "311 난방 신고": h_rate,
            "HPD 난방 위반": v_rate,
            "난방: 신고 ÷ 위반": h_ratio,
        })
        chart_rat += [
            {"소득 5분위": q, "지표": "311 쥐 신고", "1,000명당": r_rate},
            {"소득 5분위": q, "지표": "점검에서 쥐 확인", "1,000명당": i_rate},
        ]
    tbl = pd.DataFrame(rows)
    ratio_bar = tbl[["소득 5분위", "쥐: 신고 ÷ 확인"]].copy()

    type_counts = insp["inspection_type"].astype(str).value_counts()
    type_rows = []
    for typ, n in type_counts.items():
        sub = insp[insp["inspection_type"].astype(str) == typ]
        found = sub["result"].astype(str).isin(RAT_FOUND).mean() * 100
        type_rows.append({
            "inspection_type": typ,
            "건수": int(n),
            "쥐 확인 비율(%)": round(float(found), 1),
        })

    a = float(tbl.loc[tbl["소득 5분위"] == INC_Q[0], "쥐: 신고 ÷ 확인"].iat[0])
    b = float(tbl.loc[tbl["소득 5분위"] == INC_Q[-1], "쥐: 신고 ÷ 확인"].iat[0])
    ha = float(tbl.loc[tbl["소득 5분위"] == INC_Q[0], "난방: 신고 ÷ 위반"].iat[0])
    hb = float(tbl.loc[tbl["소득 5분위"] == INC_Q[-1], "난방: 신고 ÷ 위반"].iat[0])

    save_joined(
        97,
        sources=[source("rodent_inspections"), source("hpd_violations")],
        metrics=[
            {"label": "쥐 점검(12개월)", "value": f"{n_insp:,}건", "help": f"쥐 확인 {n_rat_found:,}건"},
            {"label": "좌표로 Tract를 찾은 점검", "value": f"{coord_pct:.1f}%"},
            {"label": "쥐: 신고 ÷ 확인(최하위 → 최상위 소득)", "value": f"{a:.2f} → {b:.2f}"},
            {"label": "난방: 신고 ÷ 위반(최하위 → 최상위 소득)", "value": f"{ha:.2f} → {hb:.2f}"},
        ],
        charts=[
            {"title": "소득 5분위별 쥐: 신고와 점검 확인(1,000명당)", "kind": "group",
             "x": "소득 5분위", "color": "지표", "y": "1,000명당", "rows": chart_rat},
            {"title": "신고 ÷ 확인 배율(쥐)", "kind": "bar",
             "x": "소득 5분위", "y": "쥐: 신고 ÷ 확인", "rows": records(ratio_bar),
             "caption": ("배율이 크면 확인된 문제에 비해 신고가 많은 동네, 작으면 적은 동네다. "
                         "점검은 신고로 시작하기도 하고(행정 순환) 신고 없이 지역 단위로 하기도 해서 두 값은 독립이 아니다.")},
        ],
        tables=[
            {"title": "소득 5분위별 신고와 점검", "rows": records(tbl)},
            {"title": "점검 종류별 건수", "rows": type_rows},
        ],
    )


# ── q100 ───────────────────────────────────────────────────────────

def q100(df: pd.DataFrame, dt: pd.DataFrame) -> None:
    sensors = load_ext("floodnet_sensors").copy()
    tidal = sensors["tidally_influenced"].astype(str).str.strip().str.lower().isin(
        {"yes", "y", "true", "1"})
    sensors = sensors[~tidal].copy()
    sensors["GEOID"] = points_to_geoid(sensors)
    sensors = sensors[sensors["GEOID"].notna()]
    sensor_ids = set(sensors["sensor_id"].astype(str))
    sens_geoid = sensors.set_index(sensors["sensor_id"].astype(str))["GEOID"]

    events = load_ext("floodnet_events").copy()
    events = events[events["sensor_id"].astype(str).isin(sensor_ids)].copy()
    events["날짜"] = pd.to_datetime(events["flood_start_time"]).dt.normalize()
    events["sensor_id"] = events["sensor_id"].astype(str)
    # 센서-날짜 단위 중복 제거(그날 최대 깊이)
    ev = (events.sort_values("max_depth_inches", ascending=False)
          .drop_duplicates(["sensor_id", "날짜"], keep="first"))
    ev["GEOID"] = ev["sensor_id"].map(sens_geoid)
    ev = ev[ev["GEOID"].notna()]

    fl = flood(dt)
    fl_counts = fl.groupby(["GEOID", "date"]).size().rename("n").reset_index()
    fl_set = {
        (str(g), pd.Timestamp(d).normalize().strftime("%Y-%m-%d"))
        for g, d in zip(fl_counts["GEOID"], fl_counts["date"])
    }

    def has_311(row):
        g = str(row["GEOID"])
        d0 = pd.Timestamp(row["날짜"]).normalize()
        d1 = d0 + pd.Timedelta(days=1)
        return ((g, d0.strftime("%Y-%m-%d")) in fl_set
                or (g, d1.strftime("%Y-%m-%d")) in fl_set)

    ev = ev.copy()
    ev["신고있음"] = ev.apply(has_311, axis=1)

    def depth_bucket(x):
        if pd.isna(x):
            return None
        if x < 4:
            return "4인치 미만"
        if x < 12:
            return "4–12인치"
        return "12인치 이상"

    depth_order = ["4인치 미만", "4–12인치", "12인치 이상"]
    ev["침수 깊이"] = ev["max_depth_inches"].map(depth_bucket)
    ev = ev[ev["침수 깊이"].notna()]

    n_sensors = sensors["sensor_id"].nunique()
    n_events = len(ev)
    share = round(ev["신고있음"].mean() * 100, 1) if n_events else 0.0
    deep = ev[ev["침수 깊이"] == "12인치 이상"]
    deep_share = round(deep["신고있음"].mean() * 100, 1) if len(deep) else 0.0

    tbl_rows = []
    chart_rows = []
    for lab in depth_order:
        g = ev[ev["침수 깊이"] == lab]
        n = len(g)
        yes = int(g["신고있음"].sum())
        pct = round(yes / n * 100, 1) if n else 0.0
        tbl_rows.append({"침수 깊이": lab, "센서-날짜": n, "신고 있음": yes, "비율(%)": pct})
        chart_rows.append({"침수 깊이": lab, "311 신고 있음(%)": pct})

    save_joined(
        100,
        sources=[source("floodnet_sensors"), source("floodnet_events")],
        metrics=[
            {"label": "분석한 센서", "value": f"{n_sensors}개", "help": "조수 영향 센서 제외"},
            {"label": "센서가 잡은 침수(센서-날짜)", "value": f"{n_events:,}건"},
            {"label": "311 신고가 함께 있었던 비율", "value": f"{share:.1f}%"},
            {"label": "12인치 이상 침수의 신고 비율", "value": f"{deep_share:.1f}%"},
        ],
        charts=[{
            "title": "침수 깊이별 311 신고가 함께 있었던 비율", "kind": "bar",
            "x": "침수 깊이", "y": "311 신고 있음(%)", "rows": chart_rows,
            "caption": ("센서가 물을 잡은 날, 같은 Tract에서 아무도 신고하지 않은 경우가 '보이지 않는 침수'다. "
                        "센서 위치와 민원 위치가 같은 거리는 아니다."),
        }],
        tables=[{"title": "침수 깊이별 신고 동반", "rows": tbl_rows}],
    )


# ── q017·q099 (선거 결합) ──────────────────────────────────────────

def _tract_complaint_rate(dt: pd.DataFrame) -> pd.DataFrame:
    """분석 대상 Tract의 1,000명당 민원. 반올림 전 값."""
    t = tracts()
    n = dt.groupby("GEOID").size().rename("n_comp")
    out = t.merge(n, on="GEOID", how="left")
    out["n_comp"] = out["n_comp"].fillna(0)
    out["comp_per_1k"] = out["n_comp"] / out["total_pop"] * 1000
    return out


def _election_tract_frame(dt: pd.DataFrame, method: str = "units") -> pd.DataFrame:
    """Tract 민원율 + 선거 배분. total < 100인 Tract는 득표율 NaN."""
    import elections

    base = _tract_complaint_rate(dt)
    tv = elections.tract_votes(method=method)
    m = base.merge(tv, on="GEOID", how="inner")
    m["mamdani_share"] = np.where(m["total"] >= 100, m["mamdani"] / m["total"], np.nan)
    m["votes_per_1k"] = m["total"] / m["total_pop"] * 1000
    m["임차율 5분위"] = m["ren_q"].astype(str)
    m["소득 5분위"] = m["inc_q"].astype(str)
    return m


def q017(df: pd.DataFrame, dt: pd.DataFrame) -> None:
    import elections

    m = _election_tract_frame(dt, method="units")
    ed = elections.ed_votes()
    votes_total = int(ed["total"].sum())
    votes_mamdani = int(ed["mamdani"].sum())
    city_share = votes_mamdani / votes_total if votes_total else float("nan")
    dropped = int((m["total"] < 100).sum())
    use = m[m["total"] >= 100].copy()

    rho_raw, _ = spearmanr(use["mamdani_share"], use["comp_per_1k"])
    rho_rent, _ = spearmanr(use["mamdani_share"], use["renter_rate"])
    rho_raw, rho_rent = float(rho_raw), float(rho_rent)

    rho_within: list[float] = []
    chart1_rows = []
    table_rows = []
    for q in Q5:
        g = use[use["ren_q"] == q]
        if len(g) >= 2:
            r, _ = spearmanr(g["mamdani_share"], g["comp_per_1k"])
            r = float(r)
        else:
            r = float("nan")
        rho_within.append(r)
        mam_sum = float(g["mamdani"].sum())
        tot_sum = float(g["total"].sum())
        pop_sum = float(g["total_pop"].sum())
        n_sum = float(g["n_comp"].sum())
        share_pct = mam_sum / tot_sum * 100 if tot_sum else float("nan")
        rate = n_sum / pop_sum * 1000 if pop_sum else float("nan")
        chart1_rows += [
            {"임차율 5분위": q, "지표": "맘다니 득표율(%)", "값": round(share_pct, 2)},
            {"임차율 5분위": q, "지표": "1,000명당 민원(÷10)", "값": round(rate / 10, 2)},
        ]
        table_rows.append({
            "임차율 5분위": q,
            "Tract 수": int(len(g)),
            "득표율(%)": round(share_pct, 1),
            "1,000명당 민원": round(rate, 1),
            "ρ(분위 안)": None if pd.isna(r) else round(r, 2),
        })
    rho_med = float(np.nanmedian(rho_within)) if rho_within else float("nan")

    scatter = use.copy()
    scatter["맘다니 득표율(%)"] = (scatter["mamdani_share"] * 100).round(2)
    scatter["1,000명당 민원"] = scatter["comp_per_1k"].round(2)

    save_joined(
        17,
        sources=[source("elections"), source("pluto_xy")],
        metrics=[
            {"label": "맘다니 득표율(시 전체)", "value": f"{city_share * 100:.1f}%",
             "help": f"{votes_mamdani:,} / {votes_total:,}"},
            {"label": "ρ: 득표율 × 1,000명당 민원(통제 없음)", "value": f"{rho_raw:.2f}"},
            {"label": "ρ: 득표율 × 임차율", "value": f"{rho_rent:.2f}"},
            {"label": "ρ: 임차율 5분위 안에서(중앙값)", "value": f"{rho_med:.2f}"},
        ],
        charts=[
            {"title": "임차율 5분위별 득표율과 민원율", "kind": "group",
             "x": "임차율 5분위", "color": "지표", "y": "값", "rows": chart1_rows,
             "caption": "두 지표 모두 임차율을 따라 오른다. 공통 원인을 통제하지 않은 상관은 믿기 어렵다."},
            {"title": "Tract별 맘다니 득표율과 민원율", "kind": "scatter",
             "x": "맘다니 득표율(%)", "y": "1,000명당 민원", "color": "임차율 5분위",
             "rows": records(scatter[["맘다니 득표율(%)", "1,000명당 민원", "임차율 5분위"]])},
        ],
        tables=[{"title": "임차율 5분위별 득표율·민원·상관", "rows": table_rows}],
        numbers={
            "rho_raw": round(rho_raw, 2),
            "rho_rent": round(rho_rent, 2),
            "rho_within": [None if pd.isna(x) else round(float(x), 2) for x in rho_within],
            "n_tracts": int(len(use)),
            "dropped_small_total": dropped,
            "votes_total": votes_total,
            "votes_mamdani": votes_mamdani,
        },
    )


def q099(df: pd.DataFrame, dt: pd.DataFrame) -> None:
    import elections

    units = _election_tract_frame(dt, method="units")
    area = _election_tract_frame(dt, method="area")
    ed = elections.ed_votes()
    votes_total = float(ed["total"].sum())
    allocated = float(units["total"].sum())
    share_allocated = allocated / votes_total if votes_total else float("nan")
    area_votes = float((units["total"] * units["area_share"]).sum())
    share_area = area_votes / allocated if allocated else float("nan")

    w = elections.ed_tract_weights()
    n_ed = int(ed["ed"].nunique())  # 표가 있는 ED만 센다
    n_ed_area = int(w.loc[w["method"] == "area", "ed"].nunique())

    both = units[["GEOID", "boro_acs", "mamdani_share", "total", "comp_per_1k", "votes_per_1k", "inc_q"]].merge(
        area[["GEOID", "mamdani_share"]].rename(columns={"mamdani_share": "mamdani_share_area"}),
        on="GEOID", how="inner")
    both = both[both["total"] >= 100].copy()
    both = both[both["mamdani_share"].notna() & both["mamdani_share_area"].notna()]
    rho_methods, _ = spearmanr(both["mamdani_share"], both["mamdani_share_area"])
    rho_methods = float(rho_methods)
    both["diff_pp"] = (both["mamdani_share"] - both["mamdani_share_area"]) * 100
    both["abs_diff_pp"] = both["diff_pp"].abs()
    median_abs = float(both["abs_diff_pp"].median()) if len(both) else float("nan")

    top = both.nlargest(10, "abs_diff_pp").copy()
    top["자치구"] = top["boro_acs"].map(BORO_KO)
    top["Tract"] = top.apply(
        lambda r: f"{r['GEOID']} ({r['자치구']})", axis=1)
    top["차이(%p)"] = top["abs_diff_pp"].round(2)

    chart2_rows = []
    for q in INC_Q:
        g = units[units["inc_q"] == q]
        pop = float(g["total_pop"].sum())
        votes = float(g["total"].sum())
        comps = float(g["n_comp"].sum())
        v_rate = votes / pop * 1000 if pop else 0.0
        c_rate = comps / pop * 1000 if pop else 0.0
        chart2_rows += [
            {"소득 5분위": q, "지표": "주민 1,000명당 표(÷2)", "값": round(v_rate / 2, 2)},
            {"소득 5분위": q, "지표": "1,000명당 민원(÷2)", "값": round(c_rate / 2, 2)},
        ]

    save_joined(
        99,
        sources=[source("elections"), source("pluto_xy")],
        metrics=[
            {"label": "Tract로 옮긴 표", "value": f"{share_allocated * 100:.1f}%",
             "help": f"{allocated:,.0f} / {votes_total:,.0f}"},
            {"label": "면적으로 옮긴 표", "value": f"{share_area * 100:.1f}%"},
            {"label": "ρ: 세대 배분 × 면적 배분 득표율", "value": f"{rho_methods:.2f}"},
            {"label": "두 방법 득표율 차이(중앙값, %p)", "value": f"{median_abs:.2f}"},
        ],
        charts=[
            {"title": "배분 방법 차이(|%p|) 상위 10 Tract", "kind": "barh",
             "x": "차이(%p)", "y": "Tract",
             "rows": records(top[["Tract", "차이(%p)"]]),
             "caption": "차이는 소수 Tract에 몰려 있다. 사람이 고르게 살지 않는 선거구(공원·대단지가 낀 곳 등)에서는 면적 배분이 틀리기 쉽다."},
            {"title": "소득 5분위별 주민 1,000명당 표와 민원", "kind": "group",
             "x": "소득 5분위", "color": "지표", "y": "값", "rows": chart2_rows},
        ],
        numbers={
            "share_allocated": round(share_allocated, 4),
            "share_area": round(share_area, 4),
            "rho_methods": round(rho_methods, 2),
            "median_abs_diff_pp": round(median_abs, 2),
            "n_ed": n_ed,
            "n_ed_area": n_ed_area,
        },
    )


# ── CLI ────────────────────────────────────────────────────────────

FUNCS = {
    7: "q007", 17: "q017", 57: "q057", 58: "q058", 72: "q072",
    75: "q075", 96: "q096", 97: "q097", 99: "q099", 100: "q100",
}


def main(argv: list[str] | None = None) -> None:
    want = {int(a) for a in (argv if argv is not None else sys.argv[1:])} or set(FUNCS)
    need_df = want & {7, 17, 57, 58, 72, 75, 96, 97, 99, 100}
    need_dt = want & {17, 97, 99, 100}
    df = load_311() if need_df else None
    dt = with_tract(df) if need_dt else None

    if 57 in want:
        q057(df)
    if 58 in want:
        q058(df)
    if 96 in want:
        q096(df)
    if 7 in want:
        q007(df)
    if 17 in want:
        q017(df, dt)
    if 72 in want:
        q072(df)
    if 75 in want:
        q075(df)
    if 97 in want:
        q097(df, dt)
    if 99 in want:
        q099(df, dt)
    if 100 in want:
        q100(df, dt)


if __name__ == "__main__":
    main()
