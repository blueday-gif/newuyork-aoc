"""공개 외부 자료 내려받기 (Phase 3A·3B).
실행: py -3 questions/calc/fetch_ext.py [이름 ...] [--refresh]
원자료는 저장소 밖 EXT_DIR에 둔다.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import requests

EXT_DIR = Path(os.environ.get("NY311_EXT", "D:/ny311/external"))
SODA = "https://data.cityofnewyork.us/resource/{id}.csv"
PAGE = 50_000

DATASETS: dict[str, dict] = {
    "hpd_violations": dict(
        id="wvxf-dwi5",
        select="violationid,bbl,bin,class,inspectiondate,novissueddate,novdescription,rentimpairing,latitude,longitude",
        where="inspectiondate between '2024-11-01T00:00:00' and '2026-10-31T23:59:59'",
        order="violationid", period="2024-11-01~2026-10-31",
        chunk_col="inspectiondate", chunk_range=("2024-11-01", "2026-10-31")),
    "rodent_inspections": dict(
        id="p937-wjvj",
        select="job_id,inspection_date,inspection_type,result,bbl,borough,latitude,longitude",
        where="inspection_date between '2025-11-01T00:00:00' and '2026-10-31T23:59:59'",
        order=":id", period="2025-11-01~2026-10-31"),
    "pluto": dict(
        id="64uk-42ks",
        select="bbl,borocode,bldgclass,landuse,unitsres,unitstotal,yearbuilt,numfloors,bct2020",
        where="unitsres > 0", order="bbl", period="최신판"),
    "pluto_xy": dict(
        id="64uk-42ks", select="bbl,cd,latitude,longitude,unitsres",
        where="unitsres > 0", order="bbl", period="최신판"),
    "floodnet_events": dict(
        id="aq7i-eu5q",
        select="sensor_id,flood_start_time,flood_end_time,max_depth_inches,duration_mins",
        where="flood_start_time between '2025-11-01T00:00:00' and '2026-10-31T23:59:59'",
        order="sensor_id,flood_start_time", period="2025-11-01~2026-10-31"),
    "floodnet_sensors": dict(
        id="kb2e-tjy3",
        select="sensor_id,sensor_name,date_installed,date_removed,tidally_influenced,borough,latitude,longitude",
        where=None, order="sensor_id", period="전체"),
    "rodent_311_history": dict(
        id="erm2-nwe9",
        select="unique_key,created_date,descriptor,bbl,incident_zip,borough,latitude,longitude",
        where="complaint_type='Rodent' and created_date between '2020-01-01T00:00:00' and '2026-10-31T23:59:59'",
        order="unique_key", period="2020-01-01~2026-10-31",
        chunk_col="created_date", chunk_range=("2020-01-01", "2026-10-31")),
}
NOAA = dict(
    url="https://www.ncei.noaa.gov/access/services/data/v1",
    params=dict(dataset="daily-summaries", stations="USW00094728", startDate="2025-11-01", endDate="2026-10-31",
                dataTypes="TMIN,TMAX,PRCP,SNOW", units="metric", format="csv"),
    period="2025-11-01~2026-10-31")

ELECTION_DIR = EXT_DIR / "elections"
BOE = ("https://www.vote.nyc/sites/default/files/pdf/election_results/2025/"
       "20251104General%20Election/{code}%20Mayor%20Citywide%20EDLevel.csv")
BOE_BOROS = {
    "manhattan": "00100100000New%20York",
    "bronx": "00200100000Bronx",
    "brooklyn": "00300100000Kings",
    "queens": "00400100000Queens",
    "staten_island": "00500100000Richmond",
}
DCP_ED = "https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/election-districts/nyed_{v}.zip"
ED_VERSION = "25c"

NUM_COLS = {
    "unitsres", "unitstotal", "yearbuilt", "numfloors", "max_depth_inches", "duration_mins",
    "latitude", "longitude", "TMIN", "TMAX", "PRCP", "SNOW", "cd",
}
RETRY_WAITS = (10, 30, 90, 180)
TIMEOUT = 300
UA = {"User-Agent": "Mozilla/5.0"}


def norm_bbl(s: pd.Series) -> pd.Series:
    """BBL을 10자리 문자열로 정규화. 유효하지 않으면 NA."""
    t = s.astype(str).str.strip().str.split(".", n=1).str[0]
    ok = t.str.fullmatch(r"[1-5]\d{9}") & (t != "0000000000")
    return t.where(ok, pd.NA)


def _is_date_col(name: str) -> bool:
    n = name.lower()
    return "date" in n or n.endswith("_time") or name == "DATE"


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if _is_date_col(c):
            out[c] = pd.to_datetime(out[c], errors="coerce")
        elif c in NUM_COLS:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        elif c.lower() == "bbl":
            out[c] = norm_bbl(out[c])
    return out


def _get(url: str, params: dict | None = None,
         headers: dict | None = None) -> requests.Response:
    last_err: Exception | None = None
    for i, wait in enumerate((0, *RETRY_WAITS)):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if r.status_code == 503 or r.status_code >= 400:
                if i < len(RETRY_WAITS):
                    last_err = requests.HTTPError(f"{r.status_code} {url}", response=r)
                    continue
                r.raise_for_status()
            return r
        except requests.RequestException as e:
            last_err = e
            if i >= len(RETRY_WAITS):
                raise
    raise last_err  # type: ignore[misc]


def _write(name: str, df: pd.DataFrame, meta_doc: dict) -> Path:
    EXT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXT_DIR / f"{name}.parquet"
    df.to_parquet(path, index=False)
    (EXT_DIR / f"{name}.meta.json").write_text(
        json.dumps(meta_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved {path} ({len(df):,}행)")
    return path


def _month_windows(start: str, end: str) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """chunk_range를 달 단위 창으로 나누고, 시작·끝은 범위 안으로 자른다."""
    lo = pd.Timestamp(start).normalize()
    hi = pd.Timestamp(end).normalize()
    cur = lo.replace(day=1)
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    while cur <= hi:
        next_month = cur + pd.offsets.MonthBegin(1)
        last = next_month - pd.Timedelta(days=1)
        w0 = max(cur, lo)
        w1 = min(last, hi)
        if w0 <= w1:
            windows.append((w0, w1))
        cur = next_month
    return windows


def _pages(url: str, spec: dict, where: str | None, name: str,
           label: str | None = None, running: int = 0) -> tuple[list[pd.DataFrame], str, int]:
    """한 where 조건 안에서 $offset 페이지를 넘긴다. 첫 요청 URL과 누적 행 수를 반환."""
    frames: list[pd.DataFrame] = []
    offset = 0
    first_url = ""
    total = running
    while True:
        params: dict = {
            "$select": spec["select"],
            "$order": spec["order"],
            "$limit": PAGE,
            "$offset": offset,
        }
        if where is not None:
            params["$where"] = where
        if not first_url:
            first_url = f"{url}?{urlencode(params)}"
        r = _get(url, params)
        chunk = pd.read_csv(io.StringIO(r.text), dtype=str)
        frames.append(chunk)
        total += len(chunk)
        if label is not None:
            print(f"{name} {label}: 누적 {total:,}행")
        else:
            print(f"{name}: {total:,}행")
        if len(chunk) < PAGE:
            break
        offset += PAGE
    return frames, first_url, total


def fetch_soda(name: str, refresh: bool = False) -> Path:
    if name not in DATASETS:
        raise KeyError(f"알 수 없는 자료: {name}")
    path = EXT_DIR / f"{name}.parquet"
    if path.exists() and not refresh:
        return path
    spec = DATASETS[name]
    url = SODA.format(id=spec["id"])
    frames: list[pd.DataFrame] = []
    first_url = ""

    if spec.get("chunk_col"):
        chunk_col = spec["chunk_col"]
        base_where = spec["where"]
        total = 0
        for w0, w1 in _month_windows(*spec["chunk_range"]):
            label = f"{w0:%Y-%m}"
            window_where = (
                f"({base_where}) and {chunk_col} between "
                f"'{w0:%Y-%m-%d}T00:00:00' and '{w1:%Y-%m-%d}T23:59:59'"
            )
            part, part_url, total = _pages(url, spec, window_where, name, label=label, running=total)
            if not first_url:
                first_url = part_url
            frames.extend(part)
    else:
        frames, first_url, _ = _pages(url, spec, spec["where"], name)

    df = _coerce(pd.concat(frames, ignore_index=True) if frames else pd.DataFrame())
    if spec.get("chunk_col"):
        key = spec["order"]
        if key and not key.startswith(":"):
            before = len(df)
            df = df.drop_duplicates(subset=[key], keep="first")
            n_dup = before - len(df)
            if n_dup > 0:
                print(f"{name}: 중복 {n_dup:,}행 제거")
    meta_doc = {
        "name": name,
        "dataset": spec["id"],
        "url": first_url,
        "period": spec["period"],
        "rows": len(df),
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    return _write(name, df, meta_doc)


def fetch_noaa(refresh: bool = False) -> Path:
    name = "noaa_centralpark"
    path = EXT_DIR / f"{name}.parquet"
    if path.exists() and not refresh:
        return path
    params = dict(NOAA["params"])
    first_url = f"{NOAA['url']}?{urlencode(params)}"
    r = _get(NOAA["url"], params)
    print(f"{name}: 받는 중…")
    df = _coerce(pd.read_csv(io.StringIO(r.text), dtype=str))
    print(f"{name}: {len(df):,}행")
    meta_doc = {
        "name": name,
        "dataset": "NCEI daily-summaries USW00094728",
        "url": first_url,
        "period": NOAA["period"],
        "rows": len(df),
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    return _write(name, df, meta_doc)


def load_ext(name: str) -> pd.DataFrame:
    path = EXT_DIR / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} 없음. py -3 questions/calc/fetch_ext.py {name}")
    return pd.read_parquet(path)


def meta(name: str) -> dict:
    path = EXT_DIR / f"{name}.meta.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} 없음. py -3 questions/calc/fetch_ext.py {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_files(refresh: bool = False) -> Path:
    """BOE 2025 시장 선거 ED 개표 CSV와 DCP 선거구 경계를 받는다. 이름은 elections."""
    ELECTION_DIR.mkdir(parents=True, exist_ok=True)
    csv_paths = {boro: ELECTION_DIR / f"mayor_2025_{boro}.csv" for boro in BOE_BOROS}
    zip_path = ELECTION_DIR / f"nyed_{ED_VERSION}.zip"
    extract_dir = ELECTION_DIR / f"nyed_{ED_VERSION}"
    first_url = BOE.format(code=next(iter(BOE_BOROS.values())))
    all_ready = all(p.exists() for p in csv_paths.values()) and zip_path.exists()
    if all_ready and list(extract_dir.glob("**/nyed.shp")) and not refresh:
        meta_path = EXT_DIR / "elections.meta.json"
        if not meta_path.exists():
            rows = sum(
                sum(1 for _ in p.open(encoding="utf-8-sig")) for p in csv_paths.values())
            meta_doc = {
                "name": "elections",
                "dataset": "NYC BOE 2025 General ED-level Mayor + DCP nyed_25c",
                "url": first_url,
                "period": "2025-11-04",
                "rows": rows,
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            meta_path.write_text(
                json.dumps(meta_doc, ensure_ascii=False, indent=1), encoding="utf-8")
        return ELECTION_DIR

    total_rows = 0
    for boro, code in BOE_BOROS.items():
        url = BOE.format(code=code)
        dest = csv_paths[boro]
        if dest.exists() and not refresh:
            total_rows += sum(1 for _ in dest.open(encoding="utf-8-sig"))
            continue
        print(f"elections {boro}: 받는 중…")
        r = _get(url, headers=UA)
        dest.write_bytes(r.content)
        n = sum(1 for _ in dest.open(encoding="utf-8-sig"))
        total_rows += n
        print(f"elections {boro}: {n:,}행 → {dest.name}")

    if refresh or not zip_path.exists():
        zip_url = DCP_ED.format(v=ED_VERSION)
        print(f"elections nyed_{ED_VERSION}: 받는 중…")
        r = _get(zip_url, headers=UA)
        zip_path.write_bytes(r.content)
    if refresh or not list(extract_dir.glob("**/nyed.shp")):
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        shp = list(extract_dir.glob("**/nyed.shp"))
        if not shp:
            raise FileNotFoundError(f"nyed.shp 없음: {extract_dir}")
        print(f"elections nyed_{ED_VERSION}: {shp[0]}")
    total_rows = sum(sum(1 for _ in p.open(encoding="utf-8-sig")) for p in csv_paths.values())

    meta_doc = {
        "name": "elections",
        "dataset": "NYC BOE 2025 General ED-level Mayor + DCP nyed_25c",
        "url": first_url,
        "period": "2025-11-04",
        "rows": total_rows,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    (EXT_DIR / "elections.meta.json").write_text(
        json.dumps(meta_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved elections ({total_rows:,}행)")
    return ELECTION_DIR


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="NYC 외부 자료 내려받기")
    p.add_argument("names", nargs="*", help="자료 이름(없으면 전부)")
    p.add_argument("--refresh", action="store_true", help="있어도 다시 받기")
    args = p.parse_args(argv)
    names = args.names or [*DATASETS, "noaa_centralpark", "elections"]
    for name in names:
        if name == "noaa_centralpark":
            fetch_noaa(refresh=args.refresh)
        elif name == "elections":
            fetch_files(refresh=args.refresh)
        else:
            fetch_soda(name, refresh=args.refresh)


if __name__ == "__main__":
    main(sys.argv[1:])
