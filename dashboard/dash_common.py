"""대시보드가 읽는 분석 표 경로."""

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
MAP_PATH = ROOT / "data" / "processed" / "tract_dashboard.geojson"

BOROUGH_SHORT = {
    "Bronx": "Bronx",
    "Brooklyn (Kings)": "Brooklyn",
    "Manhattan (New York)": "Manhattan",
    "Queens": "Queens",
    "Staten Island (Richmond)": "Staten Island",
}


def table(name: str) -> pd.DataFrame:
    path = TABLES / name
    return _table(name, path.stat().st_mtime_ns)


@st.cache_data(ttl="1h")
def _table(name: str, mtime_ns: int) -> pd.DataFrame:
    del mtime_ns
    frame = pd.read_csv(TABLES / name)
    if "GEOID" in frame.columns:
        frame["GEOID"] = frame["GEOID"].astype(str).str.replace(r"\.0$", "", regex=True)
    return frame


def borough_short(series: pd.Series) -> pd.Series:
    return series.map(BOROUGH_SHORT).fillna(series)
