"""311 민원 좌표를 ACS Census Tract에 붙여 Tract별 접수율을 만든다.

입력
- D:\\project-ny311\\data\\processed\\311_requests_clean.parquet
  2025-11-01 ~ 2026-10-31 뉴욕시 311 (unique_key, latitude, longitude)
- data/processed/nyc_acs_2024_5yr.geojson

출력 (data/processed)
- nyc311_tract_complaints.csv
- nyc311_tract_complaints.geojson
- nyc311_point_geoid.parquet  (민원 키와 소속 GEOID만)
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REQUESTS_PATH = Path(r"D:\project-ny311\data\processed\311_requests_clean.parquet")
ACS_PATH = PROCESSED / "nyc_acs_2024_5yr.geojson"
SUMMARY_CSV = PROCESSED / "nyc311_tract_complaints.csv"
SUMMARY_GEOJSON = PROCESSED / "nyc311_tract_complaints.geojson"
POINT_GEOID = PROCESSED / "nyc311_point_geoid.parquet"

ACS_COLUMNS = [
    "GEOID",
    "borough",
    "median_income",
    "renter_rate",
    "hispanic_rate",
    "black_rate",
    "white_rate",
    "asian_rate",
    "total_pop",
    "geometry",
]


def main() -> None:
    print("311 좌표를 읽는 중...")
    df_311 = pd.read_parquet(
        REQUESTS_PATH,
        columns=["unique_key", "latitude", "longitude"],
    )
    before = len(df_311)
    df_311 = df_311.dropna(subset=["latitude", "longitude"])
    print(f"좌표 있는 민원: {len(df_311):,} / {before:,}")

    gdf_311 = gpd.GeoDataFrame(
        df_311,
        geometry=gpd.points_from_xy(df_311["longitude"], df_311["latitude"]),
        crs="EPSG:4326",
    )

    print("ACS Tract 경계를 읽는 중...")
    nyc_acs = gpd.read_file(ACS_PATH)
    if nyc_acs.crs is None:
        nyc_acs = nyc_acs.set_crs("EPSG:4326")
    else:
        nyc_acs = nyc_acs.to_crs("EPSG:4326")
    nyc_acs = nyc_acs[ACS_COLUMNS]

    print("공간 결합 중...")
    joined = gpd.sjoin(gdf_311, nyc_acs, how="inner", predicate="within")
    outside = len(gdf_311) - len(joined)
    print(f"Tract 안에 들어온 민원: {len(joined):,} (경계 밖 {outside:,})")

    joined[["unique_key", "GEOID"]].to_parquet(POINT_GEOID, index=False)

    counts = (
        joined.groupby("GEOID", as_index=False)
        .agg(complaint_count=("unique_key", "count"))
    )
    tract_summary = nyc_acs.drop(columns="geometry").merge(
        counts, on="GEOID", how="left"
    )
    tract_summary["complaint_count"] = (
        tract_summary["complaint_count"].fillna(0).astype("int64")
    )
    population = tract_summary["total_pop"]
    tract_summary["complaints_per_1k"] = (
        tract_summary["complaint_count"] / population * 1000
    ).where(population > 0)

    tract_summary = tract_summary.sort_values(
        "complaints_per_1k", ascending=False, na_position="last"
    )
    tract_summary.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")

    summary_gdf = nyc_acs[["GEOID", "geometry"]].merge(
        tract_summary, on="GEOID", how="left"
    )
    summary_gdf.to_file(SUMMARY_GEOJSON, driver="GeoJSON")

    matched_complaints = int(tract_summary["complaint_count"].sum())
    print(f"Tract 수: {len(tract_summary):,}")
    print(f"집계된 민원: {matched_complaints:,}")
    print(f"CSV: {SUMMARY_CSV}")
    print(f"GeoJSON: {SUMMARY_GEOJSON}")
    print(f"민원-GEOID: {POINT_GEOID}")


if __name__ == "__main__":
    main()
