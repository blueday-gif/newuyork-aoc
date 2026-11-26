"""뉴욕시 Census Tract ACS 2024 5-Year 속성과 TIGER 경계를 결합한다.

산출물 (data/processed, WGS84)
- nyc_acs_2024_5yr.csv
- nyc_acs_2024_5yr.geojson

Census Data API는 요청마다 키가 필요하다.
무료 키: https://api.census.gov/data/key_signup.html

실행 예 (PowerShell, 프로젝트 루트)
    $env:CENSUS_API_KEY = "발급받은키"
    py -3 scripts/nyc_acs_2024.py

이미 받은 CSV에 빈곤율·건축연도만 붙일 때 (API 키 불필요)
    py -3 scripts/nyc_acs_2024.py --supplement
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

# 뉴욕시 5개 자치구 County FIPS (State FIPS: 36 = New York)
NYC_COUNTIES = {
    "005": "Bronx",
    "047": "Brooklyn (Kings)",
    "061": "Manhattan (New York)",
    "081": "Queens",
    "085": "Staten Island (Richmond)",
}

# ACS 2024 5-Year Estimates
# https://api.census.gov/data/2024/acs/acs5/variables.html
VARIABLES = {
    "NAME": "tract_name",
    "B01003_001E": "total_pop",  # 총인구
    "B19013_001E": "median_income",  # 가구 중위소득 ($)
    "B25003_001E": "total_housing",  # 점유 가구 수
    "B25003_002E": "owner_occupied",  # 자가 가구 수
    "B25003_003E": "renter_occupied",  # 임차 가구 수
    "B03002_001E": "race_total",  # 인종·히스패닉 집계 총인구
    "B03002_003E": "white_nh",  # 비히스패닉 백인
    "B03002_004E": "black_nh",  # 비히스패닉 흑인
    "B03002_006E": "asian_nh",  # 비히스패닉 아시아인
    "B03002_012E": "hispanic",  # 히스패닉/라티노
    "B16004_001E": "lang_total",  # 5세 이상 언어 집계 인구
    "B17001_001E": "poverty_universe",  # 빈곤 상태 판정 인구
    "B17001_002E": "poverty_below",  # 빈곤선 이하 인구
    "B25035_001E": "median_year_built",  # 중위 건축연도
    "B25034_001E": "structures_total",  # 건축연도를 아는 주택 수
    "B25034_010E": "structures_1940_1949",
    "B25034_011E": "structures_1939_earlier",
}

# 가설 H4·H5. API 키가 없으면 같은 2024년 5개년 요약 파일에서 이 열만 보충한다.
SUMMARY_BASE = (
    "https://www2.census.gov/programs-surveys/acs/summary_file/"
    "2024/table-based-SF/data/5YRData/"
)
SUMMARY_KEEP = {
    "acsdt5y2024-b17001.dat": {
        "B17001_E001": "poverty_universe",
        "B17001_E002": "poverty_below",
    },
    "acsdt5y2024-b25035.dat": {"B25035_E001": "median_year_built"},
    "acsdt5y2024-b25034.dat": {
        "B25034_E001": "structures_total",
        "B25034_E010": "structures_1940_1949",
        "B25034_E011": "structures_1939_earlier",
    },
}
NYC_COUNTY = {"36005", "36047", "36061", "36081", "36085"}
HOUSING_REFERENCE_YEAR = 2024
POVERTY_HOUSING_COLUMNS = [
    "poverty_universe",
    "poverty_below",
    "poverty_rate",
    "median_year_built",
    "housing_age",
    "structures_total",
    "structures_1940_1949",
    "structures_1939_earlier",
    "pre1950_share",
]

ACS_URL = "https://api.census.gov/data/2024/acs/acs5"
TIGER_URL = "https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_36_tract.zip"
USER_AGENT = "nyc-acs-2024/1.0 (local research script)"


def rate(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """분모가 0이거나 결측이면 결측으로 둔 비율."""
    out = numerator / denominator
    return out.where(denominator > 0)


def add_poverty_housing(frame: pd.DataFrame) -> pd.DataFrame:
    """빈곤율, 1950년 이전 주택 비율, 2024년 기준 주택 연령을 붙인다."""
    out = frame.copy()
    out["poverty_rate"] = rate(out["poverty_below"], out["poverty_universe"])
    pre1950 = out["structures_1940_1949"] + out["structures_1939_earlier"]
    out["pre1950_share"] = rate(pre1950, out["structures_total"])
    year = out["median_year_built"]
    age = HOUSING_REFERENCE_YEAR - year
    out["housing_age"] = age.where(year.between(1800, HOUSING_REFERENCE_YEAR))
    return out


def nyc_tract_geoid(geo_id: str) -> str | None:
    """요약 파일 GEO_ID에서 뉴욕시 Tract 11자리를 꺼낸다."""
    token = geo_id.strip().strip('"')
    prefix = "1400000US"
    if not token.startswith(prefix):
        return None
    geoid = token[len(prefix) :]
    if len(geoid) == 11 and geoid[:5] in NYC_COUNTY:
        return geoid
    return None


def _summary_table(filename: str, columns: dict[str, str]) -> pd.DataFrame:
    """전국 요약 파일을 흘려 읽으며 뉴욕시 Tract 행만 남긴다."""
    response = requests.get(
        SUMMARY_BASE + filename,
        stream=True,
        timeout=300,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    lines = response.iter_lines()
    header = next(lines).decode("utf-8").rstrip("\r").split("|")
    geo_i = header.index("GEO_ID")
    index = {source: header.index(source) for source in columns}
    rows: list[dict[str, str]] = []
    for raw in lines:
        if not raw:
            continue
        parts = raw.decode("utf-8").rstrip("\r").split("|")
        geoid = nyc_tract_geoid(parts[geo_i])
        if geoid is None:
            continue
        row = {"GEOID": geoid}
        for source, i in index.items():
            row[columns[source]] = parts[i] if i < len(parts) else ""
        rows.append(row)
    response.close()
    frame = pd.DataFrame(rows).drop_duplicates("GEOID")
    for column in columns.values():
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame.loc[frame[column] < 0, column] = pd.NA
    print(f"{filename}: 뉴욕시 Tract {len(frame):,}개")
    return frame


def fetch_poverty_housing_summary() -> pd.DataFrame:
    """API 키 없이 ACS 2024 5개년 요약 파일에서 H4·H5 변수를 만든다."""
    print("Census API 키가 없어 2024년 5개년 요약 파일에서 빈곤·건축연도를 받는 중...")
    frames = [_summary_table(name, columns) for name, columns in SUMMARY_KEEP.items()]
    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="GEOID", how="outer")
    return add_poverty_housing(merged)


def supplement_csv(csv_path: Path) -> pd.DataFrame:
    """기존 ACS CSV에 빈곤율과 건축연도 열을 붙인다. 경계 파일은 바꾸지 않는다."""
    existing = pd.read_csv(csv_path, dtype={"GEOID": str, "state": str, "county": str, "tract": str})
    extra = fetch_poverty_housing_summary()
    overlap = [column for column in POVERTY_HOUSING_COLUMNS if column in existing.columns]
    if overlap:
        existing = existing.drop(columns=overlap)
    merged = existing.merge(extra, on="GEOID", how="left", validate="one_to_one")
    matched = int(merged["poverty_universe"].notna().sum())
    print(f"기존 Tract {len(merged):,}개 중 빈곤 모집단이 있는 Tract {matched:,}개")
    merged.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"ACS 데이터 갱신: {csv_path}")
    return merged


def fetch_acs(api_key: str) -> pd.DataFrame:
    """뉴욕시 5개 자치구의 Census Tract ACS 표를 한 번에 받는다."""
    params = {
        "get": ",".join(VARIABLES.keys()),
        "for": "tract:*",
        "in": "state:36 county:" + ",".join(NYC_COUNTIES.keys()),
        "key": api_key,
    }
    response = requests.get(
        ACS_URL,
        params=params,
        timeout=180,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()

    body = response.text.lstrip()
    if not body.startswith("["):
        raise RuntimeError(
            "Census API가 JSON 대신 다른 응답을 돌려줬습니다. "
            "API 키가 빠졌거나 유효하지 않은지 확인하세요.\n"
            + body[:400]
        )

    raw = response.json()
    if len(raw) < 2:
        raise RuntimeError("Census API 결과에 데이터 행이 없습니다.")

    frame = pd.DataFrame(raw[1:], columns=raw[0])
    frame = frame.rename(columns=VARIABLES)

    # 11자리 GEOID = state(2) + county(3) + tract(6)
    frame["GEOID"] = frame["state"] + frame["county"] + frame["tract"]
    frame["borough"] = frame["county"].map(NYC_COUNTIES)

    num_cols = [name for name in VARIABLES.values() if name != "tract_name"]
    for col in num_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
        # -666666666 등 센서스 결측 코드
        frame.loc[frame[col] < 0, col] = pd.NA

    frame["renter_rate"] = rate(frame["renter_occupied"], frame["total_housing"])
    frame["hispanic_rate"] = rate(frame["hispanic"], frame["race_total"])
    frame["black_rate"] = rate(frame["black_nh"], frame["race_total"])
    frame["white_rate"] = rate(frame["white_nh"], frame["race_total"])
    frame["asian_rate"] = rate(frame["asian_nh"], frame["race_total"])
    frame["owner_rate"] = rate(frame["owner_occupied"], frame["total_housing"])
    return add_poverty_housing(frame)


def fetch_nyc_tracts(cache_zip: Path) -> gpd.GeoDataFrame:
    """뉴욕주 Tract 경계를 받아 5개 자치구만 남긴다."""
    if not cache_zip.exists() or cache_zip.stat().st_size < 1000:
        cache_zip.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(
            TIGER_URL,
            stream=True,
            timeout=180,
            headers={"User-Agent": USER_AGENT},
        ) as response:
            response.raise_for_status()
            with cache_zip.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        handle.write(chunk)

    tracts = gpd.read_file(cache_zip)
    nyc = tracts.loc[
        tracts["COUNTYFP"].isin(NYC_COUNTIES.keys()),
        ["GEOID", "geometry"],
    ].copy()
    return nyc


def build_geodata(tracts: gpd.GeoDataFrame, acs: pd.DataFrame) -> gpd.GeoDataFrame:
    merged = tracts.merge(acs, on="GEOID", how="inner")
    # GeoJSON은 경위도(WGS84)로 저장한다. TIGER 원본은 NAD83(EPSG:4269).
    if merged.crs is None:
        merged = merged.set_crs(4269)
    return merged.to_crs(4326)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="뉴욕시 Census Tract ACS 2024 5-Year 데이터와 경계를 저장합니다."
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("CENSUS_API_KEY", ""),
        help="Census API 키. 생략하면 환경변수 CENSUS_API_KEY 를 사용합니다.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="프로젝트 루트. CSV·GeoJSON은 data/processed, TIGER zip은 data/raw 에 저장합니다.",
    )
    parser.add_argument(
        "--supplement",
        action="store_true",
        help="이미 받은 ACS CSV에 빈곤율과 건축연도만 붙입니다. 경계는 다시 쓰지 않습니다.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root: Path = args.out_dir
    processed = root / "data" / "processed"
    if args.supplement:
        csv_path = processed / "nyc_acs_2024_5yr.csv"
        if not csv_path.exists():
            print(f"보충할 ACS 파일이 없습니다: {csv_path}", file=sys.stderr)
            return 1
        supplement_csv(csv_path)
        return 0

    api_key = args.key.strip()
    if not api_key:
        print(
            "Census API 키가 필요합니다.\n"
            "1) https://api.census.gov/data/key_signup.html 에서 무료 키를 발급받으세요.\n"
            "2) PowerShell:  $env:CENSUS_API_KEY = \"발급받은키\"\n"
            "3) py -3 scripts/nyc_acs_2024.py",
            file=sys.stderr,
        )
        return 1

    raw = root / "data" / "raw"
    processed.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)

    print("ACS 2024 5-Year Tract 데이터를 받는 중...")
    acs = fetch_acs(api_key)
    csv_path = processed / "nyc_acs_2024_5yr.csv"
    acs.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"ACS 데이터 저장 완료: {len(acs)}개 Census Tract -> {csv_path}")

    print("TIGER/Line 2024 Tract 경계를 읽는 중...")
    tracts = fetch_nyc_tracts(raw / "tl_2024_36_tract.zip")
    print(f"뉴욕시 Tract 경계: {len(tracts)}개")

    geo = build_geodata(tracts, acs)
    geo_path = processed / "nyc_acs_2024_5yr.geojson"
    geo.to_file(geo_path, driver="GeoJSON")
    print(f"GeoJSON 저장 완료: {len(geo)}개 Tract -> {geo_path}")

    unmatched = len(acs) - len(geo)
    if unmatched:
        print(f"경계와 결합되지 않은 ACS Tract: {unmatched}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
