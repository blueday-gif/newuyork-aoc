"""문항별 통계 계산에 쓰는 공통 도구.
311 원본은 저장소 밖에 있다(data/external/SOURCE.txt). 한 번 읽은 열은 스크래치가 아니라
questions/.cache/에 parquet으로 저장해 다음 계산을 빠르게 한다(.gitignore 대상).
"""
import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

QDIR = Path(__file__).resolve().parents[1]
ROOT = QDIR.parent
RAW = Path(os.environ.get("NY311_RAW", r"D:/project-ny311/data/processed/311_requests_2020_present.parquet"))
CACHE = QDIR / ".cache" / "slim.parquet"
DATA_OUT = QDIR / "data"

COLS = {
    "Unique Key": "key", "Created Date": "created", "Closed Date": "closed", "Agency": "agency",
    "Problem (formerly Complaint Type)": "problem", "Problem Detail (formerly Descriptor)": "detail",
    "Incident Address": "addr", "Borough": "borough", "Resolution Description": "resolution",
    "BBL": "bbl", "Location Type": "loc_type",
    "Council District": "cd", "Open Data Channel Type": "channel", "Incident Zip": "zip",
}

BORO_ACS = {"Bronx": "BRONX", "Brooklyn (Kings)": "BROOKLYN", "Manhattan (New York)": "MANHATTAN",
            "Queens": "QUEENS", "Staten Island (Richmond)": "STATEN ISLAND"}
BORO_KO = {"BRONX": "브롱크스", "BROOKLYN": "브루클린", "MANHATTAN": "맨해튼",
           "QUEENS": "퀸스", "STATEN ISLAND": "스태튼아일랜드"}


def load_311() -> pd.DataFrame:
    """민원 1건 = 1행. 날짜, 처리시간(시간), 주소 정규화 열을 붙인다."""
    import pyarrow.parquet as pq
    fresh = (CACHE.exists() and CACHE.stat().st_mtime > RAW.stat().st_mtime
             and set(COLS.values()) <= set(pq.ParquetFile(CACHE).schema_arrow.names))  # 열을 추가하면 다시 만든다
    if fresh:
        df = pd.read_parquet(CACHE)
    else:
        df = pd.read_parquet(RAW, columns=list(COLS)).rename(columns=COLS)
        for c in ["agency", "problem", "borough", "loc_type", "cd", "channel"]:
            df[c] = df[c].astype("category")
        CACHE.parent.mkdir(exist_ok=True)
        df.to_parquet(CACHE)
    df["hours"] = (df.closed - df.created).dt.total_seconds() / 3600
    df.loc[df.hours < 0, "hours"] = np.nan
    df["date"] = df.created.dt.normalize()
    df["addr_n"] = df.addr.fillna("").str.upper().str.replace(r"\s+", " ", regex=True).str.strip()
    return df


def acs() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "processed" / "nyc_acs_2024_5yr.csv", dtype={"GEOID": str})


def borough_pop() -> pd.Series:
    """자치구 인구(ACS 2024 5개년). 색인은 311의 자치구 표기(대문자)."""
    return acs().groupby("borough").total_pop.sum().rename(index=BORO_ACS)


INC_Q = ["Q1(최저)", "Q2", "Q3", "Q4", "Q5(최고)"]


Q5 = ["Q1(최저)", "Q2", "Q3", "Q4", "Q5(최고)"]
RACE_KO = {"hispanic_rate": "히스패닉", "black_rate": "흑인", "white_rate": "백인", "asian_rate": "아시아계"}
MAJOR_KO = {"hispanic_rate": "히스패닉 다수", "black_rate": "흑인 다수", "white_rate": "백인 다수",
            "asian_rate": "아시아계 다수", "no_majority": "과반 없음"}
MAJOR_ORDER = ["히스패닉 다수", "과반 없음", "흑인 다수", "백인 다수", "아시아계 다수"]


def tracts() -> pd.DataFrame:
    """분석 대상 Tract(인구 1,000명 이상)와 5분위. 기존 story_01·story_03 계산과 같은 기준.
    inc_q 소득, ren_q 임차율, old_q 1950년 이전 주택 비율(동점은 순위로 나눔).
    자치구 열 이름은 boro_acs(311의 borough와 겹치지 않게)."""
    a = acs()
    a = a[a.total_pop >= 1000].copy()
    a["inc_q"] = pd.qcut(a.median_income, 5, labels=INC_Q)
    a["ren_q"] = pd.qcut(a.renter_rate, 5, labels=Q5)
    a["old_q"] = pd.qcut(a.pre1950_share.rank(method="first"), 5, labels=Q5)
    a["boro_acs"] = a.borough.map(BORO_ACS)
    a["his_q"] = pd.qcut(a.hispanic_rate, 5, labels=Q5)
    race = list(RACE_KO)
    a["major"] = a[race].idxmax(axis=1).where(a[race].max(axis=1) >= 0.5, "no_majority").map(MAJOR_KO)
    return a[["GEOID", "boro_acs", "total_pop", "renter_occupied", "median_income", "renter_rate",
              "pre1950_share", "poverty_rate", *race, "inc_q", "ren_q", "old_q", "his_q", "major"]]


def with_tract(df: pd.DataFrame) -> pd.DataFrame:
    """민원에 Tract(GEOID)와 5분위를 붙인다. Tract를 못 찾았거나 인구가 적은 Tract는 빠진다."""
    pg = pd.read_parquet(ROOT / "data" / "processed" / "nyc311_point_geoid.parquet").rename(columns={"unique_key": "key"})
    return df.merge(pg, on="key", how="inner").merge(tracts(), on="GEOID", how="inner")


def category(problem: pd.Series) -> pd.Series:
    """민원 유형 → 7개 분야(주거환경, 소음, 도로·교통, 위생, 해충·동물, 건축·안전, 기타)."""
    cm = pd.read_csv(ROOT / "data" / "processed" / "category_map.csv", encoding="utf-8-sig")
    return problem.astype(str).map(dict(zip(cm.problem, cm.category))).fillna("기타")


def tract_rates(dt: pd.DataFrame, cats: list[str] | None = None) -> pd.DataFrame:
    """Tract별 1,000명당 민원율. rate는 전체, 나머지는 분야별(cat 열이 있어야 함). 민원 0건 Tract도 남긴다."""
    t = tracts().set_index("GEOID")
    t["n"] = dt.groupby("GEOID").size()
    t["rate"] = t.n.fillna(0) / t.total_pop * 1000
    for c in cats or []:
        t[c] = dt[dt.cat == c].groupby("GEOID").size().reindex(t.index).fillna(0) / t.total_pop * 1000
    return t.reset_index()


def classify(text: pd.Series, rules: list[tuple[str, str]], other: str = "기타") -> pd.Series:
    """결과문(Resolution)을 규칙 순서대로 분류한다. rules: [(정규식, 분류명)]"""
    t = text.fillna("").str.lower()
    out = pd.Series(other, index=text.index)
    done = pd.Series(False, index=text.index)
    for pat, name in rules:
        hit = ~done & t.str.contains(pat, regex=True)
        out[hit] = name
        done |= hit
    return out


HPD_RULES = [
    (r"duplicate", "중복으로 묶음"),
    (r"restored|was corrected|were corrected", "복구됐다고 확인(전화·세입자)"),
    (r"not able to gain access|unable to", "점검 못 함(문을 못 엶)"),
    (r"violations? (?:were|was) issued", "위반 발부"),
    (r"did not violate|no violation", "점검했으나 위반 없음"),
    (r"conducted or attempted", "점검(결과는 HPD 사이트)"),
    (r"still open", "미해결, 집주인에 통보"),
]


def records(frame: pd.DataFrame) -> list[dict]:
    """JSON에 넣을 수 있게 바꾼다(날짜는 문자열, NaN은 None)."""
    out = frame.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    out = out.astype(object).where(out.notna(), None)
    return [{k: (v.item() if hasattr(v, "item") else v) for k, v in r.items()} for r in out.to_dict("records")]


def save(qid: int, metrics: list, charts: list, tables: list | None = None, numbers: dict | None = None):
    """문항 통계를 questions/data/q###.json으로 저장한다.
    metrics: [{"label", "value", "help"}]
    charts: [{"title", "kind", "x", "y", "color"?, "rows", "x_title"?, "y_title"?, "caption"?}]
    """
    DATA_OUT.mkdir(exist_ok=True)
    doc = {"id": qid, "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": str(RAW.name),
           "metrics": metrics, "charts": charts, "tables": tables or [], "numbers": numbers or {}}
    path = DATA_OUT / f"q{qid:03d}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", path.name)
