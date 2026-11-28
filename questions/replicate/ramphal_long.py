"""Ramphal 등(2022) 방식 재현: 2010~2025년 7월 소음 민원, 소득 4분위별 증가율.

실행(저장소 루트): py -3 questions/replicate/ramphal_long.py
입력(G 드라이브 local_data/ny311):
  data/raw/2010_2019_noise/noise_2010_2019.csv   소음 민원 2010~2019 (공개 API, 월별 수집)
  data/raw/2020_2026_noise/noise_2020_2026.csv   소음 민원 2020~2026.10 (공개 API)
  external/acs_2015_2019/tract_2015_2019.parquet  ACS 2015~2019 5년, Tract 인구·중위소득(make_acs_tract.py 없이 이 파일을 쓴다)
  external/tiger_2010_tract/tl_2010_36_tract10.zip 2010 Tract 경계
기준 열:
  - Tract는 2010년 경계로 통일한다(ACS 2015~2019가 2010 경계). 2020년 이후 좌표도 2010 경계에 붙인다.
  - 인구는 ACS 2015~2019 값을 모든 해에 고정해 쓴다(연도별 인구 자료가 없다). 한계로 적는다.
  - 소득 4분위: 뉴욕시 Tract 중 인구 1,000명 이상·소득 있는 곳을 개수 기준으로 4등분.
  - 이상치 주소 655 E 230th St·672 E 231st St는 본 분석에서 뺀다. 민감도 표에 세 경우(포함, 655만 제외, 둘 다 제외)를 함께 낸다.
  - 평년 기준은 2015~2019년이다(2014년 자료 체계 변화 때문).
출력: questions/replicate/out/ramphal_long/
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = ROOT / "local_data" / "ny311"
OUT = HERE / "out" / "ramphal_long"
NYC_COUNTIES = ["005", "047", "061", "081", "085"]
# 이상치 주소: 한 주소에서 한 해 7월 1만 건 이상이 나온 곳. 655는 11~12월, 672는 2021~2022년 7월에 집중.
OUTLIERS = {"655 E 230th St": r"^655 (EAST|E) 230", "672 E 231st St": r"^672 (EAST|E) 231"}
MODES = ["포함", "655 제외", "655·672 제외"]  # 본 분석은 "655·672 제외"
BASE_YEARS = range(2016, 2020)  # 평년 기준 2015~2019(2014년 자료 체계 변화 이후; 2015년 증가율은 2014년과 비교되므로 뺀다)
CHUNK = 400_000
QL = ["Q1(저소득)", "Q2", "Q3", "Q4(고소득)"]
PER = 100_000


def tracts() -> gpd.GeoDataFrame:
    shp = gpd.read_file("zip://" + str(LOCAL / "external/tiger_2010_tract/tl_2010_36_tract10.zip"))
    shp = shp[shp.COUNTYFP10.isin(NYC_COUNTIES)][["GEOID10", "geometry"]].rename(columns={"GEOID10": "GEOID"})
    acs = pd.read_parquet(LOCAL / "external/acs_2015_2019/tract_2015_2019.parquet")
    acs = acs[acs.GEOID.str[:5].isin(["36005", "36047", "36061", "36081", "36085"])]
    t = shp.merge(acs, on="GEOID", how="inner")
    t = t[(t.total_pop >= 1000) & t.median_income.notna() & (t.median_income > 0)].copy()
    t["q"] = pd.qcut(t.median_income.rank(method="first"), 4, labels=QL)
    return t.to_crs("EPSG:4326")


def july_counts(path: Path, tr: gpd.GeoDataFrame, label: str) -> tuple[pd.DataFrame, list[dict]]:
    """CSV를 조각으로 읽어 7월 소음 민원만 Tract에 붙이고 연도·분위별로 센다."""
    log = []
    total = missing_xy = july = 0
    parts = []
    for chunk in pd.read_csv(path, chunksize=CHUNK, usecols=["created_date", "complaint_type", "latitude",
                                                            "longitude", "incident_address"],
                             dtype={"complaint_type": str, "incident_address": str}):
        total += len(chunk)
        d = pd.to_datetime(chunk.created_date, errors="coerce")
        chunk = chunk.assign(year=d.dt.year, month=d.dt.month,
                             addr=chunk.incident_address.fillna("").str.upper().str.replace(r"\s+", " ", regex=True))
        chunk = chunk[chunk.month == 7]
        july += len(chunk)
        xy = chunk.latitude.notna() & chunk.longitude.notna()
        missing_xy += int((~xy).sum())
        chunk = chunk[xy]
        if chunk.empty:
            continue
        pts = gpd.GeoDataFrame(chunk, geometry=gpd.points_from_xy(chunk.longitude, chunk.latitude),
                               crs="EPSG:4326")
        j = gpd.sjoin(pts, tr[["GEOID", "q", "geometry"]], how="inner", predicate="within")
        flag = pd.Series("", index=j.index)
        for name, rx in OUTLIERS.items():
            flag[j.addr.str.contains(rx, regex=True)] = name
        parts.append(j.assign(flag=flag).groupby(["year", "q", "flag"], observed=True).size())
    counts = pd.concat(parts).groupby(level=[0, 1, 2], observed=True).sum().rename("n").reset_index()
    log.append({"자료": label, "전체 행": total, "7월 행": july, "좌표 없음(7월)": missing_xy,
                "Tract 안(7월, 분석 대상)": int(counts.n.sum()),
                "비고": "좌표가 있어도 분석 대상 Tract 밖이면 빠진다"})
    return counts, log


def rates(counts: pd.DataFrame, tr: gpd.GeoDataFrame, mode: str) -> pd.DataFrame:
    c = counts.copy()
    drop = {"655 제외": ["655 E 230th St"], "655·672 제외": ["655 E 230th St", "672 E 231st St"]}.get(mode, [])
    c = c[~c.flag.isin(drop)]
    c = c.groupby(["year", "q"], observed=True).n.sum().reset_index()
    pop = tr.groupby("q", observed=True).total_pop.sum()
    c["pop"] = c.q.map(pop).astype(float)
    c["rate"] = c.n / c["pop"] * PER
    return c


def growth_table(r: pd.DataFrame) -> pd.DataFrame:
    p = r.pivot(index="year", columns="q", values="rate").reindex(columns=QL)
    g = p.pct_change() * 100
    rows = []
    for q in QL:
        base = g.loc[list(BASE_YEARS), q]
        rows.append({"분위": q,
                     "7월 2019 (10만 명당)": p.loc[2019, q],
                     "7월 2020 (10만 명당)": p.loc[2020, q],
                     "2019→2020 증가율(%)": g.loc[2020, q],
                     "2015~2019 평년 증가율 평균(%)": base.mean(),
                     "2015~2019 증가율 범위(%)": f"{base.min():.0f} ~ {base.max():.0f}"})
    t = pd.DataFrame(rows)
    return t


def yearly(r: pd.DataFrame) -> pd.DataFrame:
    p = r.pivot(index="year", columns="q", values="rate").reindex(columns=QL)
    g = p.pct_change() * 100
    out = pd.concat({"7월 10만 명당": p, "전년 7월 대비 증가율(%)": g}, axis=1)
    return out.round(1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tr = tracts()
    c1, log1 = july_counts(LOCAL / "data/raw/2010_2019_noise/noise_2010_2019.csv", tr, "2010~2019")
    c2, log2 = july_counts(LOCAL / "data/raw/2020_2026_noise/noise_2020_2026.csv", tr, "2020~2026.10")
    counts = pd.concat([c1, c2], ignore_index=True)
    counts = counts.groupby(["year", "q", "flag"], observed=True).n.sum().reset_index()

    main_r = rates(counts, tr, "655·672 제외")
    all_r = rates(counts, tr, "포함")
    r655 = rates(counts, tr, "655 제외")

    main_y = yearly(main_r)
    all_y = yearly(all_r)
    main_g = growth_table(main_r)
    all_g = growth_table(all_r)

    sens = []
    for lab, r in [("본 분석(655·672 제외)", main_r), ("655만 제외", r655), ("포함", all_r)]:
        g = growth_table(r).set_index("분위")
        sens.append({"분석": lab, **{f"{q} 2019→2020(%)": g.loc[q, "2019→2020 증가율(%)"] for q in QL},
                     **{f"{q} 평년 평균(%)": g.loc[q, "2015~2019 평년 증가율 평균(%)"] for q in QL}})
    sens = pd.DataFrame(sens)

    tract_n = tr.groupby("q", observed=True).agg(Tract=("GEOID", "size"), 인구=("total_pop", "sum"),
                                                 소득최저=("median_income", "min"), 소득최고=("median_income", "max"))
    tract_n.reset_index().to_csv(OUT / "01_tracts_by_quartile.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(log1 + log2).to_csv(OUT / "02_join_log.csv", index=False, encoding="utf-8-sig")
    main_y.to_csv(OUT / "03_july_by_year_main.csv", encoding="utf-8-sig")
    all_y.to_csv(OUT / "04_july_by_year_all.csv", encoding="utf-8-sig")
    main_g.to_csv(OUT / "05_growth_2019_2020_main.csv", index=False, encoding="utf-8-sig", float_format="%.1f")
    all_g.to_csv(OUT / "06_growth_2019_2020_all.csv", index=False, encoding="utf-8-sig", float_format="%.1f")
    sens.to_csv(OUT / "07_sensitivity.csv", index=False, encoding="utf-8-sig", float_format="%.1f")

    pd.set_option("display.width", 220, "display.max_columns", 20, "display.float_format", "{:,.1f}".format)
    print("== 분위 구성")
    print(tract_n.to_string())
    print("== 조인 기록")
    print(pd.DataFrame(log1 + log2).to_string(index=False))
    print("== 7월 10만 명당 (본 분석)")
    print(main_y.to_string())
    print("== 2019→2020 증가율 (본 분석)")
    print(main_g.to_string(index=False))
    print("== 민감도")
    print(sens.to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
