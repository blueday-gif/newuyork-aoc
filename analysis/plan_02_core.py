"""개요 문서의 우선 분석: 품질, 유형, 임차율, 공간 군집.

분석 단위는 Census Tract다. 인구 1,000명 미만은 상관·회귀·Moran's I에서 뺀다.
극단 Tract 36005042000은 삭제하지 않고, 포함·제외 결과를 나란히 남긴다.
난수 고정값: 42.

실행 (프로젝트 루트):
    py -3 analysis/plan_02_core.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import sparse, stats
import patsy
from statsmodels.sandbox.regression.gmm import IV2SLS
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.outliers_influence import variance_inflation_factor

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"
REPORT = ROOT / "reports" / "plan_02_core.md"
REQUESTS = Path(r"D:\project-ny311\data\processed\311_requests_clean.parquet")
POINTS = PROCESSED / "nyc311_point_geoid.parquet"
TIGER = ROOT / "data" / "raw" / "tl_2024_36_tract.zip"
TRACT_GEO = PROCESSED / "nyc311_tract_complaints.geojson"
OUTLIER = "36005042000"
POP_MIN = 1000
RNG = np.random.default_rng(42)

HOUSING = {
    "HEAT/HOT WATER",
    "PLUMBING",
    "PAINT/PLASTER",
    "DOOR/WINDOW",
    "WATER LEAK",
    "FLOORING/STAIRS",
    "ELECTRIC",
    "APPLIANCE",
    "GENERAL",
    "SAFETY",
    "OUTSIDE BUILDING",
    "Unsanitary Condition",
}
# Unsanitary Condition (title case) is rare; the bulk type is UNSANITARY CONDITION.
HOUSING.discard("Unsanitary Condition")

SANITATION = {
    "UNSANITARY CONDITION",
    "Dirty Condition",
    "Illegal Dumping",
    "Missed Collection",
    "Sanitation Condition",
    "Residential Disposal Complaint",
    "Overflowing Recycling Baskets",
    "Overflowing Litter Baskets",
    "Litter Basket / Request",
    "Dirty Conditions",
}

ROADS = {
    "Illegal Parking",
    "Blocked Driveway",
    "Street Condition",
    "Abandoned Vehicle",
    "Derelict Vehicles",
    "Traffic Signal Condition",
    "Street Light Condition",
    "Sidewalk Condition",
    "Snow or Ice",
    "Highway Condition",
    "Broken Muni Meter",
    "Broken Parking Meter",
    "Street Sign - Damaged",
    "Street Sign - Missing",
    "Curb Condition",
    "Bike Rack Condition",
    "Bus Stop Shelter Complaint",
    "Highway Sign - Damaged",
    "Highway Sign - Missing",
}

BUILDING = {
    "General Construction/Plumbing",
    "Building/Use",
    "Elevator",
    "Maintenance or Facility",
    "Construction Safety Enforcement",
    "Scaffold Safety",
    "Electrical",
    "Plumbing",
    "Boilers",
    "BEST/Site Safety",
}

PESTS = {
    "Rodent",
    "Mosquitoes",
    "Unsanitary Animal Pvt Property",
    "Animal in a Park",
    "Dead Animal",
    "Animal Abuse",
    "Unsanitary Pigeon Condition",
    "Harboring Bees/Wasps",
}

BOROUGH_311 = {
    "BRONX": "Bronx",
    "BROOKLYN": "Brooklyn (Kings)",
    "MANHATTAN": "Manhattan (New York)",
    "QUEENS": "Queens",
    "STATEN ISLAND": "Staten Island (Richmond)",
}


def classify(problem: object) -> str:
    if problem is None or (isinstance(problem, float) and np.isnan(problem)):
        return "미상"
    name = str(problem)
    if name.startswith("Noise"):
        return "소음"
    if name in HOUSING:
        return "주거환경"
    if name in SANITATION:
        return "위생"
    if name in ROADS:
        return "도로·교통"
    if name in PESTS:
        return "해충·동물"
    if name in BUILDING:
        return "건축·안전"
    return "기타"


def save(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(TABLES / name, index=False, encoding="utf-8-sig")


def spearman(frame: pd.DataFrame, x: str, y: str) -> tuple[float, float, int]:
    pair = frame[[x, y]].dropna()
    if len(pair) < 10:
        return np.nan, np.nan, int(len(pair))
    rho, pvalue = stats.spearmanr(pair[x], pair[y])
    return float(rho), float(pvalue), int(len(pair))


def load_requests() -> pd.DataFrame:
    requests = pd.read_parquet(
        REQUESTS,
        columns=[
            "unique_key",
            "problem",
            "borough",
            "latitude",
            "agency",
            "incident_address",
            "created_year",
            "created_month",
            "created_hour",
            "created_dow",
            "flag_system_duplicate",
        ],
    )
    points = pd.read_parquet(POINTS, columns=["unique_key", "GEOID"])
    merged = requests.merge(points, on="unique_key", how="left")
    merged["category"] = merged["problem"].map(classify)
    merged["borough_label"] = merged["borough"].map(BOROUGH_311)
    return merged


def category_map(requests: pd.DataFrame) -> pd.DataFrame:
    counts = requests.groupby(["problem", "category"], dropna=False).size().reset_index(name="n")
    counts = counts.sort_values("n", ascending=False)
    counts.to_csv(PROCESSED / "category_map.csv", index=False, encoding="utf-8-sig")
    summary = (
        counts.groupby("category", dropna=False)["n"]
        .sum()
        .reset_index()
        .sort_values("n", ascending=False)
    )
    summary["share"] = summary["n"] / summary["n"].sum()
    return summary


def quality_tables(requests: pd.DataFrame) -> dict[str, pd.DataFrame]:
    known = requests.loc[requests["problem"].notna()].copy()
    by_type = (
        known.groupby("problem")
        .agg(n=("unique_key", "size"), missing_xy=("latitude", lambda s: int(s.isna().sum())))
        .reset_index()
    )
    by_type["missing_pct"] = by_type["missing_xy"] / by_type["n"] * 100
    by_type = by_type.loc[by_type["n"] >= 5000].sort_values("missing_pct", ascending=False)

    by_borough = (
        requests.groupby(requests["borough_label"].fillna("(자치구 없음)"))
        .agg(n=("unique_key", "size"), missing_xy=("latitude", lambda s: int(s.isna().sum())))
        .reset_index(names="borough")
    )
    by_borough["missing_pct"] = by_borough["missing_xy"] / by_borough["n"] * 100

    outlier = requests.loc[requests["GEOID"] == OUTLIER]
    problems = (
        outlier.groupby(outlier["problem"].fillna("(없음)"))
        .size()
        .reset_index(name="n")
        .sort_values("n", ascending=False)
    )
    problems["share"] = problems["n"] / problems["n"].sum()
    addresses = (
        outlier.groupby(outlier["incident_address"].fillna("(주소 없음)"))
        .size()
        .reset_index(name="n")
        .sort_values("n", ascending=False)
        .head(15)
    )
    addresses["share"] = addresses["n"] / len(outlier)
    outlier_summary = pd.DataFrame(
        [
            {
                "GEOID": OUTLIER,
                "complaints": int(len(outlier)),
                "top_problem": problems.iloc[0]["problem"] if len(problems) else "",
                "top_problem_share": float(problems.iloc[0]["share"]) if len(problems) else np.nan,
                "top_address": addresses.iloc[0]["incident_address"] if len(addresses) else "",
                "top_address_n": int(addresses.iloc[0]["n"]) if len(addresses) else 0,
                "top_address_share": float(addresses.iloc[0]["share"]) if len(addresses) else np.nan,
                "duplicate_flag_rate": float(outlier["flag_system_duplicate"].mean()),
                "city_duplicate_flag_rate": float(requests["flag_system_duplicate"].mean()),
            }
        ]
    )
    return {
        "missing_type": by_type,
        "missing_borough": by_borough,
        "outlier_problems": problems.head(12),
        "outlier_addresses": addresses,
        "outlier_summary": outlier_summary,
    }


def time_tables(requests: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    month = (
        requests.groupby(["created_year", "created_month"], dropna=False)
        .agg(
            complaints=("unique_key", "size"),
            noise=("category", lambda s: int((s == "소음").sum())),
            housing=("category", lambda s: int((s == "주거환경").sum())),
        )
        .reset_index()
        .sort_values(["created_year", "created_month"])
    )
    month["label"] = pd.to_datetime(month["created_month"]).dt.strftime("%Y-%m")
    noise = requests.loc[requests["category"] == "소음"]
    heat = (
        noise.groupby(["created_dow", "created_hour"], dropna=False)
        .size()
        .reset_index(name="noise")
    )
    return month, heat


def tract_frame(requests: pd.DataFrame) -> pd.DataFrame:
    located = requests.loc[requests["GEOID"].notna()]
    counts = (
        located.groupby(["GEOID", "category"]).size().unstack(fill_value=0).reset_index()
    )
    acs = pd.read_csv(
        PROCESSED / "nyc_acs_2024_5yr.csv",
        dtype={"GEOID": str},
    )
    base = pd.read_csv(
        PROCESSED / "nyc311_tract_complaints.csv",
        dtype={"GEOID": str},
        usecols=["GEOID", "complaint_count", "complaints_per_1k"],
    )
    land = gpd.read_file(TIGER)[["GEOID", "ALAND"]].copy()
    land["GEOID"] = land["GEOID"].astype(str)
    tracts = acs.merge(base, on="GEOID", how="left", validate="one_to_one")
    tracts = tracts.merge(counts, on="GEOID", how="left")
    tracts = tracts.merge(land, on="GEOID", how="left")
    for col in ["소음", "주거환경", "위생", "도로·교통", "해충·동물", "건축·안전", "기타", "미상"]:
        if col not in tracts:
            tracts[col] = 0
        tracts[col] = tracts[col].fillna(0)
    area_km2 = tracts["ALAND"] / 1_000_000
    tracts["area_km2"] = area_km2.where(area_km2 > 0)
    tracts["pop_density"] = tracts["total_pop"] / tracts["area_km2"]
    for col, rate in (
        ("소음", "noise_rate"),
        ("주거환경", "housing_rate"),
        ("위생", "sanitation_rate"),
        ("도로·교통", "road_rate"),
        ("해충·동물", "pest_rate"),
        ("건축·안전", "building_rate"),
    ):
        tracts[rate] = (tracts[col] / tracts["total_pop"] * 1000).where(tracts["total_pop"] > 0)
    tracts["stable"] = tracts["total_pop"] >= POP_MIN
    return tracts


def relationship_tables(tracts: pd.DataFrame) -> dict[str, pd.DataFrame]:
    required = ["poverty_rate", "pre1950_share", "housing_age", "위생", "주거환경"]
    missing = [column for column in required if column not in tracts.columns]
    if missing:
        raise RuntimeError(
            "빈곤율·건축연도 열이 없습니다. 먼저 py -3 scripts/nyc_acs_2024.py --supplement 를 실행하세요: "
            + ", ".join(missing)
        )
    stable = tracts.loc[tracts["stable"]].copy()
    tests = [
        ("전체 민원율", "median_income", "complaints_per_1k", stable),
        ("전체 민원율", "renter_rate", "complaints_per_1k", stable),
        ("주거 민원율", "renter_rate", "housing_rate", stable),
        ("주거 민원율", "median_income", "housing_rate", stable),
        ("소음 민원율", "pop_density", "noise_rate", stable),
        ("소음 민원율", "renter_rate", "noise_rate", stable),
        ("위생 민원율", "renter_rate", "sanitation_rate", stable),
        ("해충 민원율", "renter_rate", "pest_rate", stable),
        ("위생 민원율", "poverty_rate", "sanitation_rate", stable),
        ("해충 민원율", "poverty_rate", "pest_rate", stable),
        ("주거 민원율", "pre1950_share", "housing_rate", stable),
        ("주거 민원율", "housing_age", "housing_rate", stable),
    ]
    rows = []
    for outcome, x, y, frame in tests:
        rho, pvalue, n = spearman(frame, x, y)
        rows.append(
            {"group": "시 전체", "outcome": outcome, "variable": x, "n": n, "rho": rho, "p_value": pvalue}
        )
    for borough, part in stable.groupby("borough"):
        rho, pvalue, n = spearman(part, "renter_rate", "complaints_per_1k")
        rows.append(
            {
                "group": borough,
                "outcome": "전체 민원율",
                "variable": "renter_rate",
                "n": n,
                "rho": rho,
                "p_value": pvalue,
            }
        )
    corr = pd.DataFrame(rows)
    reject, p_adj, _, _ = multipletests(corr["p_value"].fillna(1), method="fdr_bh")
    corr["p_fdr"] = p_adj
    corr["fdr_reject_0_05"] = reject

    quintiles = []
    quintile_specs = (
        ("median_income", "complaint_count", "complaints_per_1k", "전체 민원율"),
        ("renter_rate", "complaint_count", "complaints_per_1k", "전체 민원율"),
        ("poverty_rate", "위생", "sanitation_rate", "위생 민원율"),
        ("pre1950_share", "주거환경", "housing_rate", "주거 민원율"),
    )
    for column, count_col, rate_col, outcome in quintile_specs:
        part = stable.dropna(subset=[column, count_col, "total_pop", rate_col]).copy()
        part = part.loc[part["total_pop"] > 0]
        part["quintile"] = pd.qcut(part[column], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
        for quintile, group in part.groupby("quintile", observed=True):
            quintiles.append(
                {
                    "variable": column,
                    "outcome": outcome,
                    "quintile": str(quintile),
                    "tracts": len(group),
                    "pop_weighted_per_1k": group[count_col].sum() / group["total_pop"].sum() * 1000,
                    "median_rate": group[rate_col].median(),
                }
            )
    return {"correlations": corr, "quintiles": pd.DataFrame(quintiles)}


OLS_FORMULAS = {
    "core_borough": "complaints_per_1k ~ renter_rate + income_10k + C(borough)",
    "full": "complaints_per_1k ~ renter_rate + income_10k + density_10k + poverty_rate",
    "full_borough": (
        "complaints_per_1k ~ renter_rate + income_10k + density_10k + poverty_rate + C(borough)"
    ),
}
COUNT_FORMULA = (
    "complaint_count ~ renter_rate + income_10k + density_10k + poverty_rate + C(borough)"
)
SCALED_TERMS = {"renter_rate", "income_10k", "density_10k", "poverty_rate"}


def model_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """계획서 식에 필요한 열이 있는 Tract만 남기고 단위를 맞춘다."""
    part = frame.dropna(
        subset=[
            "complaints_per_1k",
            "renter_rate",
            "median_income",
            "pop_density",
            "poverty_rate",
            "borough",
        ]
    ).copy()
    part["income_10k"] = part["median_income"] / 10000
    part["density_10k"] = part["pop_density"] / 10000
    return part.reset_index(drop=True)


def fit_ols(frame: pd.DataFrame):
    part = model_frame(frame)
    model = smf.ols(OLS_FORMULAS["full_borough"], data=part).fit(cov_type="HC1")
    return model, part


def regression_table(model, model_name: str) -> pd.DataFrame:
    conf = model.conf_int()
    rows = []
    for term in model.params.index:
        rows.append(
            {
                "term": term,
                "coef": float(model.params[term]),
                "se": float(model.bse[term]),
                "p_value": float(model.pvalues[term]),
                "ci_low": float(conf.loc[term, 0]),
                "ci_high": float(conf.loc[term, 1]),
            }
        )
    table = pd.DataFrame(rows)
    exog = model.model.exog
    vifs = []
    for i, name in enumerate(model.model.exog_names):
        if name == "Intercept":
            vif = np.nan
        else:
            vif = float(variance_inflation_factor(exog, i))
        vifs.append(vif)
    table["vif"] = vifs
    table["r_squared"] = float(model.rsquared)
    table["adj_r_squared"] = float(model.rsquared_adj)
    table["n"] = int(model.nobs)
    table["model"] = model_name
    return table


def ols_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    part = model_frame(frame)
    tables = []
    for name, formula in OLS_FORMULAS.items():
        fitted = smf.ols(formula, data=part).fit(cov_type="HC1")
        tables.append(regression_table(fitted, name))
    return pd.concat(tables, ignore_index=True)


def count_model(frame: pd.DataFrame) -> pd.DataFrame:
    part = model_frame(frame)
    part = part.dropna(subset=["complaint_count", "total_pop"]).copy()
    part = part.loc[part["total_pop"] > 0]
    part["log_exposure"] = np.log(part["total_pop"] / 1000)
    poisson = smf.poisson(
        COUNT_FORMULA,
        data=part,
        offset=part["log_exposure"],
    ).fit(disp=0, cov_type="HC1", maxiter=200)
    dispersion = float(np.sum(np.asarray(poisson.resid_pearson) ** 2) / poisson.df_resid)
    used = poisson
    family = "poisson"
    if dispersion >= 2:
        try:
            used = smf.negativebinomial(
                COUNT_FORMULA,
                data=part,
                offset=part["log_exposure"],
            ).fit(disp=0, maxiter=200)
            family = "negative_binomial"
        except Exception:
            family = "poisson_overdispersed"
            used = poisson
    conf = used.conf_int()
    rows = []
    for name in used.params.index:
        if name.startswith("alpha"):
            continue
        coef = float(used.params[name])
        rows.append(
            {
                "family": family,
                "dispersion_pearson": dispersion,
                "term": name,
                "coef": coef,
                "irr": float(np.exp(coef)),
                "irr_per_10pp_or_10k": float(np.exp(coef * 0.1)) if name in SCALED_TERMS else np.nan,
                "p_value": float(used.pvalues[name]),
                "ci_low": float(conf.loc[name, 0]),
                "ci_high": float(conf.loc[name, 1]),
                "n": int(used.nobs),
                "model": "full_borough",
            }
        )
    return pd.DataFrame(rows)


def sensitivity(tracts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for threshold in (500, 1000, 2000):
        for drop_outlier in (False, True):
            part = tracts.loc[tracts["total_pop"] >= threshold].copy()
            if drop_outlier:
                part = part.loc[part["GEOID"] != OUTLIER]
            rho_r, p_r, n_r = spearman(part, "renter_rate", "complaints_per_1k")
            rho_i, p_i, n_i = spearman(part, "median_income", "complaints_per_1k")
            model, _ = fit_ols(part)
            rows.append(
                {
                    "pop_min": threshold,
                    "drop_outlier": drop_outlier,
                    "n_renter": n_r,
                    "renter_rho": rho_r,
                    "renter_p": p_r,
                    "n_income": n_i,
                    "income_rho": rho_i,
                    "income_p": p_i,
                    "renter_ols_per_10pp": float(model.params["renter_rate"] * 0.1),
                    "renter_ols_p": float(model.pvalues["renter_rate"]),
                    "income_ols_per_10k": float(model.params["income_10k"]),
                    "income_ols_p": float(model.pvalues["income_10k"]),
                    "r_squared": float(model.rsquared),
                    "model": "full_borough",
                }
            )
    return pd.DataFrame(rows)


def connected_queen(geo: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, sparse.csr_matrix]:
    """맞닿은 Tract를 이웃으로 두고, 이웃이 있는 행만 행 표준화 가중치로 남긴다."""
    geo = geo.reset_index(drop=True)
    pairs = gpd.sjoin(geo, geo, predicate="touches", how="inner")
    pairs = pairs.loc[pairs.index != pairs["index_right"]]
    rows = pairs.index.to_numpy()
    cols = pairs["index_right"].to_numpy()
    weights = sparse.coo_matrix(
        (np.ones(len(rows), dtype=float), (rows, cols)),
        shape=(len(geo), len(geo)),
    ).tocsr()
    weights.sum_duplicates()
    weights.data = np.ones_like(weights.data)
    degree = np.asarray(weights.sum(axis=1)).ravel()
    connected = degree > 0
    geo = geo.loc[connected].reset_index(drop=True)
    weights = weights[connected][:, connected]
    degree = np.asarray(weights.sum(axis=1)).ravel()
    return geo, sparse.diags(1 / degree) @ weights


def global_moran(values: np.ndarray, weights: sparse.csr_matrix, perms: int = 999) -> tuple[float, float, float]:
    centered = values - values.mean()
    n = len(centered)
    lagged = weights @ centered
    moran_i = float((n / weights.sum()) * (np.dot(centered, lagged) / np.dot(centered, centered)))
    expected = -1 / (n - 1)
    extreme = 1
    for _ in range(perms):
        shuffled = RNG.permutation(centered)
        lagged_s = weights @ shuffled
        stat = (n / weights.sum()) * (np.dot(shuffled, lagged_s) / np.dot(shuffled, shuffled))
        extreme += abs(stat) >= abs(moran_i)
    return moran_i, expected, extreme / (perms + 1)


def spatial_term_rows(
    estimator: str,
    names: list[str],
    params: np.ndarray,
    bse: np.ndarray,
    pvalues: np.ndarray,
    n: int,
    detail: str,
) -> list[dict]:
    rows = []
    for name, estimate, se, pvalue in zip(names, params, bse, pvalues):
        rows.append(
            {
                "estimator": estimator,
                "term": name,
                "estimate": float(estimate),
                "se": float(se),
                "p_value": float(pvalue),
                "n": n,
                "detail": detail,
            }
        )
    return rows


def residual_spatial(stable: pd.DataFrame) -> pd.DataFrame:
    """계획서 식 OLS 잔차의 Moran's I, 공간시차(2SLS), 공간오차(반복 GLS)."""
    part = model_frame(stable)
    geo = gpd.read_file(TRACT_GEO)[["GEOID", "geometry"]].copy()
    geo["GEOID"] = geo["GEOID"].astype(str)
    geo = geo.merge(part, on="GEOID", how="inner")
    geo, weights = connected_queen(geo)
    y_frame, x_frame = patsy.dmatrices(
        OLS_FORMULAS["full_borough"], geo, return_type="dataframe"
    )
    y = np.asarray(y_frame).ravel()
    x = np.asarray(x_frame)
    ols = smf.ols(OLS_FORMULAS["full_borough"], data=geo).fit()
    moran_i, expected, moran_p = global_moran(np.asarray(ols.resid), weights)
    rows = [
        {
            "estimator": "residual_moran",
            "term": "moran_i",
            "estimate": moran_i,
            "se": np.nan,
            "p_value": moran_p,
            "n": int(len(geo)),
            "detail": f"기댓값 {expected:.4f}, 순열 999회, 이웃 없는 Tract 제외",
        }
    ]

    lagged_y = weights @ y
    nonconstant = [i for i, name in enumerate(x_frame.columns) if name != "Intercept"]
    instruments = np.column_stack([x, weights @ x[:, nonconstant]])
    regressors = np.column_stack([lagged_y, x])
    sar = IV2SLS(y, regressors, instruments).fit()
    sar_names = ["Wy"] + list(x_frame.columns)
    rows.extend(
        spatial_term_rows(
            "sar_2sls",
            sar_names,
            np.asarray(sar.params),
            np.asarray(sar.bse),
            np.asarray(sar.pvalues),
            int(len(geo)),
            "공간시차. 도구변수는 X와 WX. 계수는 2SLS.",
        )
    )

    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    lam = 0.0
    for _ in range(15):
        residual = y - x @ beta
        lagged_residual = weights @ residual
        denom = float(np.dot(lagged_residual, lagged_residual))
        if denom == 0:
            break
        lam = float(np.clip(np.dot(lagged_residual, residual) / denom, -0.95, 0.95))
        beta = np.linalg.lstsq(x - lam * (weights @ x), y - lam * (weights @ y), rcond=None)[0]
    transformed = sm.OLS(y - lam * (weights @ y), x - lam * (weights @ x)).fit(cov_type="HC1")
    rows.append(
        {
            "estimator": "sem_gls",
            "term": "lambda",
            "estimate": lam,
            "se": np.nan,
            "p_value": np.nan,
            "n": int(len(geo)),
            "detail": "공간오차. λ는 잔차 회귀를 15회 반복한 값이고, 표준오차는 두지 않는다.",
        }
    )
    rows.extend(
        spatial_term_rows(
            "sem_gls",
            list(x_frame.columns),
            np.asarray(transformed.params),
            np.asarray(transformed.bse),
            np.asarray(transformed.pvalues),
            int(len(geo)),
            "공간오차 변환 뒤 HC1. λ의 불확실성은 계수 표준오차에 들어 있지 않다.",
        )
    )
    return pd.DataFrame(rows)


def kruskal_borough(stable: pd.DataFrame) -> pd.DataFrame:
    groups = [
        part["complaints_per_1k"].dropna().to_numpy()
        for _, part in stable.groupby("borough")
    ]
    result = stats.kruskal(*groups)
    n = int(stable["complaints_per_1k"].notna().sum())
    epsilon2 = float(result.statistic / (n - 1)) if n > 1 else np.nan
    return pd.DataFrame(
        [
            {
                "test": "Kruskal-Wallis 자치구별 민원율",
                "H": float(result.statistic),
                "p_value": float(result.pvalue),
                "epsilon_squared": epsilon2,
                "n": n,
                "groups": stable["borough"].nunique(),
            }
        ]
    )


def moran(tracts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Queen 이웃과, 섬 Tract에는 가까운 4개를 더해 LISA·Gi*를 계산한다.

    순열은 999회이고 난수 씨앗은 42다. 국지 유의성은 Benjamini–Hochberg FDR 5%다.
    """
    from scipy.spatial import cKDTree

    perms = 999
    rng = np.random.default_rng(42)
    geo = gpd.read_file(TRACT_GEO)[["GEOID", "geometry"]].copy()
    geo["GEOID"] = geo["GEOID"].astype(str)
    stable_ids = set(tracts.loc[tracts["stable"], "GEOID"])
    geo = geo.loc[geo["GEOID"].isin(stable_ids)].reset_index(drop=True)
    attrs = tracts.loc[tracts["stable"], ["GEOID", "complaints_per_1k", "borough"]].copy()
    geo = geo.merge(attrs, on="GEOID", how="inner")
    pairs = gpd.sjoin(geo, geo, predicate="touches", how="inner")
    pairs = pairs.loc[pairs["GEOID_left"] != pairs["GEOID_right"], ["GEOID_left", "GEOID_right"]]
    index = {geoid: i for i, geoid in enumerate(geo["GEOID"])}
    rows = pairs["GEOID_left"].map(index).to_numpy()
    cols = pairs["GEOID_right"].map(index).to_numpy()
    binary = sparse.coo_matrix(
        (np.ones(len(rows), dtype=float), (rows, cols)),
        shape=(len(geo), len(geo)),
    ).tocsr()
    binary.data[:] = 1
    binary = binary.tolil()
    degree = np.asarray(binary.sum(axis=1)).ravel()
    isolates = np.flatnonzero(degree == 0)
    centroids = geo.geometry.to_crs(2263).centroid
    xy = np.column_stack([centroids.x.to_numpy(), centroids.y.to_numpy()])
    neighbors = cKDTree(xy).query(xy, k=5)[1]
    for i in isolates:
        for j in neighbors[i, 1:]:
            binary[i, j] = 1
            binary[j, i] = 1
    binary = binary.tocsr()
    degree = np.asarray(binary.sum(axis=1)).ravel()
    weights = sparse.diags(1 / degree) @ binary

    values = geo["complaints_per_1k"].to_numpy(dtype=float)
    centered = values - values.mean()
    n = len(centered)
    moment2 = np.dot(centered, centered) / n
    lagged = weights @ centered
    local = centered * lagged / moment2
    global_i = float((n / weights.sum()) * (np.dot(centered, lagged) / np.dot(centered, centered)))
    expected = -1 / (n - 1)

    extreme = np.ones(n)
    global_extreme = 1
    for _ in range(perms):
        shuffled = rng.permutation(centered)
        moment_s = np.dot(shuffled, shuffled) / n
        lagged_s = weights @ shuffled
        local_s = shuffled * lagged_s / moment_s
        extreme += np.abs(local_s) >= np.abs(local)
        stat = (n / weights.sum()) * (np.dot(shuffled, lagged_s) / np.dot(shuffled, shuffled))
        global_extreme += abs(stat) >= abs(global_i)
    p_local = extreme / (perms + 1)
    p_global = global_extreme / (perms + 1)
    reject, p_fdr, _, _ = multipletests(p_local, method="fdr_bh")

    quadrant = np.full(n, "ns", dtype=object)
    raw_quadrant = np.full(n, "ns", dtype=object)
    high_self = centered > 0
    high_lag = lagged > 0
    raw = p_local < 0.05
    quadrant[reject & high_self & high_lag] = "HH"
    quadrant[reject & ~high_self & ~high_lag] = "LL"
    quadrant[reject & high_self & ~high_lag] = "HL"
    quadrant[reject & ~high_self & high_lag] = "LH"
    raw_quadrant[raw & high_self & high_lag] = "HH"
    raw_quadrant[raw & ~high_self & ~high_lag] = "LL"
    raw_quadrant[raw & high_self & ~high_lag] = "HL"
    raw_quadrant[raw & ~high_self & high_lag] = "LH"
    raw_hh = int((raw_quadrant == "HH").sum())
    raw_ll = int((raw_quadrant == "LL").sum())

    star = binary.tolil()
    star.setdiag(1)
    star = star.tocsr()
    star_sum = np.asarray(star.sum(axis=1)).ravel()
    squared = star.copy()
    squared.data = np.square(squared.data)
    star_sq = np.asarray(squared.sum(axis=1)).ravel()
    scale = np.sqrt(np.square(values - values.mean()).sum() / n)
    gi_z = (star @ values - values.mean() * star_sum) / (
        scale * np.sqrt((n * star_sq - np.square(star_sum)) / (n - 1))
    )
    gi_p = 2 * stats.norm.sf(np.abs(gi_z))
    gi_reject, _, _, _ = multipletests(gi_p, method="fdr_bh")
    gi = np.full(n, "ns", dtype=object)
    gi[gi_reject & (gi_z > 0)] = "hot"
    gi[gi_reject & (gi_z < 0)] = "cold"

    geo["lisa"] = quadrant
    geo["lisa_p05"] = raw_quadrant
    geo["lisa_p"] = p_local
    geo["lisa_p_fdr"] = p_fdr
    geo["gi"] = gi
    geo["gi_z"] = gi_z
    summary = pd.DataFrame(
        [
            {
                "n": n,
                "knn_linked": int(len(isolates)),
                "moran_i": global_i,
                "expected_i": expected,
                "p_value_perm": float(p_global),
                "perms": perms,
                "hh": int((quadrant == "HH").sum()),
                "ll": int((quadrant == "LL").sum()),
                "hl": int((quadrant == "HL").sum()),
                "lh": int((quadrant == "LH").sum()),
                "hh_p05": raw_hh,
                "ll_p05": raw_ll,
                "lisa_at_floor": int((p_local <= 1 / (perms + 1)).sum()),
                "gi_hot": int((gi == "hot").sum()),
                "gi_cold": int((gi == "cold").sum()),
            }
        ]
    )
    local = geo[
        ["GEOID", "borough", "complaints_per_1k", "lisa", "lisa_p05", "lisa_p", "lisa_p_fdr", "gi", "gi_z"]
    ].copy()
    return summary, local


def dashboard_map(tracts: pd.DataFrame, local: pd.DataFrame) -> None:
    geo = gpd.read_file(TRACT_GEO)
    geo["GEOID"] = geo["GEOID"].astype(str)
    keep = [
        "GEOID",
        "borough",
        "total_pop",
        "median_income",
        "renter_rate",
        "complaint_count",
        "complaints_per_1k",
        "pop_density",
        "noise_rate",
        "housing_rate",
        "sanitation_rate",
        "pest_rate",
        "road_rate",
    ]
    attrs = tracts[keep].merge(local[["GEOID", "lisa", "lisa_p05", "gi"]], on="GEOID", how="left")
    attrs["lisa"] = attrs["lisa"].fillna("제외")
    attrs["lisa_p05"] = attrs["lisa_p05"].fillna("제외")
    attrs["gi"] = attrs["gi"].fillna("제외")
    gwr_path = TABLES / "plan02_gwr_local.csv"
    if gwr_path.exists():
        gwr_local = pd.read_csv(gwr_path, dtype={"GEOID": str}, usecols=["GEOID", "renter_10pp"])
        gwr_local = gwr_local.rename(columns={"renter_10pp": "gwr_renter_10pp"})
        attrs = attrs.merge(gwr_local, on="GEOID", how="left")
    out = geo[["GEOID", "geometry"]].merge(attrs, on="GEOID", how="inner")
    out["geometry"] = out.geometry.simplify(0.0008, preserve_topology=True)
    out.to_file(PROCESSED / "tract_dashboard.geojson", driver="GeoJSON")


def fit_gwr(tracts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """적응형 이중제곱 커널 GWR. 이웃 수는 AICc가 가장 작은 후보를 쓴다."""
    from scipy.spatial import cKDTree

    part = model_frame(tracts.loc[tracts["stable"]])
    boundaries = gpd.read_file(TRACT_GEO)[["GEOID", "geometry"]]
    boundaries["GEOID"] = boundaries["GEOID"].astype(str)
    crs = boundaries.crs
    part = part.merge(boundaries, on="GEOID", how="inner")
    centroids = gpd.GeoSeries(part["geometry"].to_numpy(), crs=crs).to_crs(2263).centroid
    xy = np.column_stack([centroids.x.to_numpy(), centroids.y.to_numpy()])
    y = part["complaints_per_1k"].to_numpy(dtype=float)
    raw = np.column_stack(
        [
            np.ones(len(part)),
            part["renter_rate"].to_numpy(dtype=float),
            part["income_10k"].to_numpy(dtype=float),
            part["density_10k"].to_numpy(dtype=float),
            part["poverty_rate"].to_numpy(dtype=float),
        ]
    )
    scale = raw[:, 1:].std(axis=0)
    scale[scale == 0] = 1
    design = raw.copy()
    design[:, 1:] = raw[:, 1:] / scale
    names = ["Intercept", "renter_rate", "income_10k", "density_10k", "poverty_rate"]
    effect_scale = {
        "Intercept": 1.0,
        "renter_rate": 0.1,
        "income_10k": 1.0,
        "density_10k": 0.1,
        "poverty_rate": 0.1,
    }
    n, p = design.shape
    candidates = [k for k in (25, 30, 40, 60, 80, 120, 180, 280, 450, 700) if 20 < k < n]
    distance, neighbor = cKDTree(xy).query(xy, k=max(candidates))

    def fit_bandwidth(k: int):
        used = neighbor[:, :k]
        span = np.maximum(distance[:, :k][:, -1] * 1.01, 1.0)
        ratio = distance[:, :k] / span[:, None]
        weights = np.square(1 - np.square(np.minimum(ratio, 1)))
        weights[ratio >= 1] = 0
        coefs = np.empty((n, p))
        hat = np.empty(n)
        fitted = np.empty(n)
        for i in range(n):
            weight = weights[i]
            rows = design[used[i]]
            root = np.sqrt(weight)
            weighted_x = rows * root[:, None]
            weighted_y = y[used[i]] * root
            beta, *_ = np.linalg.lstsq(weighted_x, weighted_y, rcond=None)
            gram = weighted_x.T @ weighted_x
            try:
                gram_inv = np.linalg.inv(gram)
            except np.linalg.LinAlgError:
                gram_inv = np.linalg.pinv(gram)
            point = design[i]
            coefs[i] = beta
            fitted[i] = point @ beta
            here = np.flatnonzero(used[i] == i)
            self_weight = float(weight[here[0]]) if here.size else 0.0
            hat[i] = self_weight * float(point @ gram_inv @ point)
        residual = y - fitted
        rss = float(residual @ residual)
        trace = float(np.clip(hat, 0, None).sum())
        if rss <= 0 or trace >= n - 2:
            score = np.inf
        else:
            aic = n * np.log(rss / n) + n * np.log(2 * np.pi) + n + trace
            score = aic + 2 * trace * (trace + 1) / (n - trace - 1)
        return score, coefs, trace, rss

    best_k = candidates[0]
    best_score = np.inf
    best_pack = None
    for k in candidates:
        score, coefs, trace, rss = fit_bandwidth(k)
        print(f"  GWR k={k} AICc={score:.1f}")
        if score < best_score:
            best_k = k
            best_score = score
            best_pack = (coefs, trace, rss)
    coefs, trace, rss = best_pack
    coefs = coefs.copy()
    coefs[:, 1:] /= scale
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - rss / tss if tss else np.nan
    global_model = smf.ols(OLS_FORMULAS["full"], data=part).fit()
    global_resid = global_model.resid.to_numpy(dtype=float)
    global_rss = float(global_resid @ global_resid)
    global_trace = float(global_model.df_model + 1)
    global_aic = n * np.log(global_rss / n) + n * np.log(2 * np.pi) + n + global_trace
    global_aicc = global_aic + 2 * global_trace * (global_trace + 1) / (n - global_trace - 1)
    rows = []
    for index, name in enumerate(names):
        column = coefs[:, index]
        rows.append(
            {
                "term": name,
                "global_coef": float(global_model.params.get(name, np.nan)),
                "local_p10": float(np.quantile(column, 0.10)),
                "local_p50": float(np.quantile(column, 0.50)),
                "local_p90": float(np.quantile(column, 0.90)),
                "share_positive": float((column > 0).mean()),
                "effect_scale": effect_scale[name],
                "bandwidth_k": int(best_k),
                "aicc": float(best_score),
                "aicc_ols": float(global_aicc),
                "trace_s": trace,
                "n": n,
                "r2": float(r2),
                "kernel": "adaptive_bisquare",
                "bandwidth_at_grid_edge": int(best_k == min(candidates)),
            }
        )
    summary = pd.DataFrame(rows)
    local = pd.DataFrame(
        {
            "GEOID": part["GEOID"].astype(str).to_numpy(),
            "borough": part["borough"].to_numpy(),
            "renter_10pp": coefs[:, 1] * 0.1,
            "income_per_10k": coefs[:, 2],
            "density_per_1k": coefs[:, 3] * 0.1,
            "poverty_10pp": coefs[:, 4] * 0.1,
        }
    )
    borough = (
        local.groupby("borough", as_index=False)
        .agg(tracts=("GEOID", "size"), renter_10pp_median=("renter_10pp", "median"))
        .sort_values("borough")
    )
    return summary, local, borough


def attach_gwr_map(local: pd.DataFrame) -> None:
    path = PROCESSED / "tract_dashboard.geojson"
    geo = gpd.read_file(path)
    geo["GEOID"] = geo["GEOID"].astype(str)
    extra = local[["GEOID", "renter_10pp"]].rename(columns={"renter_10pp": "gwr_renter_10pp"})
    extra["GEOID"] = extra["GEOID"].astype(str)
    if "gwr_renter_10pp" in geo.columns:
        geo = geo.drop(columns=["gwr_renter_10pp"])
    geo = geo.merge(extra, on="GEOID", how="left")
    geo.to_file(path, driver="GeoJSON")


def write_report(
    coverage_n: int,
    categories: pd.DataFrame,
    quality: dict[str, pd.DataFrame],
    correlations: pd.DataFrame,
    quintiles: pd.DataFrame,
    ols: pd.DataFrame,
    counts: pd.DataFrame,
    sens: pd.DataFrame,
    kw: pd.DataFrame,
    moran_summary: pd.DataFrame,
    other_top: pd.DataFrame,
    spatial: pd.DataFrame,
) -> None:
    other_share = float(categories.loc[categories["category"] == "기타", "share"].sum())
    renter = correlations.query("group == '시 전체' and variable == 'renter_rate' and outcome == '전체 민원율'").iloc[0]
    income = correlations.query("group == '시 전체' and variable == 'median_income' and outcome == '전체 민원율'").iloc[0]
    housing = correlations.query("outcome == '주거 민원율' and variable == 'renter_rate'").iloc[0]
    noise = correlations.query("outcome == '소음 민원율' and variable == 'pop_density'").iloc[0]
    base = sens.query("pop_min == 1000 and drop_outlier == False").iloc[0]
    dropped = sens.query("pop_min == 1000 and drop_outlier == True").iloc[0]
    outlier = quality["outlier_summary"].iloc[0]
    moran_row = moran_summary.iloc[0]
    def ols_term(model_name: str, term: str) -> pd.Series:
        return ols.loc[(ols["model"] == model_name) & (ols["term"] == term)].iloc[0]

    ols_r = ols_term("full_borough", "renter_rate")
    ols_income = ols_term("full_borough", "income_10k")
    ols_density = ols_term("full_borough", "density_10k")
    ols_poverty = ols_term("full_borough", "poverty_rate")
    core_renter = ols_term("core_borough", "renter_rate")
    core_income = ols_term("core_borough", "income_10k")
    bare_renter = ols_term("full", "renter_rate")
    substantive = ols.loc[
        (ols["model"] == "full_borough")
        & ols["term"].isin(["renter_rate", "income_10k", "density_10k", "poverty_rate"])
    ]
    vif_row = substantive.loc[substantive["vif"].idxmax()]
    vif_label = {
        "renter_rate": "임차율",
        "income_10k": "소득",
        "density_10k": "인구밀도",
        "poverty_rate": "빈곤율",
    }.get(vif_row.term, vif_row.term)
    count_r = counts.loc[counts["term"] == "renter_rate"].iloc[0]
    residual_i = spatial.loc[
        (spatial["estimator"] == "residual_moran") & (spatial["term"] == "moran_i")
    ].iloc[0]
    sar_w = spatial.loc[(spatial["estimator"] == "sar_2sls") & (spatial["term"] == "Wy")].iloc[0]
    sar_renter = spatial.loc[
        (spatial["estimator"] == "sar_2sls") & (spatial["term"] == "renter_rate")
    ].iloc[0]
    sem_lambda = spatial.loc[(spatial["estimator"] == "sem_gls") & (spatial["term"] == "lambda")].iloc[0]
    sem_renter = spatial.loc[
        (spatial["estimator"] == "sem_gls") & (spatial["term"] == "renter_rate")
    ].iloc[0]
    poverty = correlations.query(
        "group == '시 전체' and variable == 'poverty_rate' and outcome == '위생 민원율'"
    ).iloc[0]
    pest_poverty = correlations.query(
        "group == '시 전체' and variable == 'poverty_rate' and outcome == '해충 민원율'"
    ).iloc[0]
    pre1950 = correlations.query(
        "group == '시 전체' and variable == 'pre1950_share' and outcome == '주거 민원율'"
    ).iloc[0]
    age = correlations.query(
        "group == '시 전체' and variable == 'housing_age' and outcome == '주거 민원율'"
    ).iloc[0]

    def span(variable: str) -> str:
        part = quintiles.loc[quintiles["variable"] == variable].set_index("quintile")
        return (
            f"Q1 {part.loc['Q1', 'pop_weighted_per_1k']:.0f} → "
            f"Q5 {part.loc['Q5', 'pop_weighted_per_1k']:.0f}"
        )

    def quintile_list(variable: str) -> str:
        part = quintiles.loc[quintiles["variable"] == variable].set_index("quintile")
        return ", ".join(
            f"{label} {part.loc[label, 'pop_weighted_per_1k']:.0f}"
            for label in ["Q1", "Q2", "Q3", "Q4", "Q5"]
        )

    year = pd.read_csv(PROCESSED / "nyc_acs_2024_5yr.csv", usecols=["median_year_built"])[
        "median_year_built"
    ].dropna()
    year_floor_n = int((year <= 1939).sum())
    year_n = int(year.shape[0])
    pre_q = quintiles.loc[quintiles["variable"] == "pre1950_share"].set_index("quintile")
    pre_q4 = float(pre_q.loc["Q4", "pop_weighted_per_1k"])
    pre_q5 = float(pre_q.loc["Q5", "pop_weighted_per_1k"])
    if pre_q5 < pre_q4:
        pre1950_tail = "Q4 다음 Q5는 조금 낮다."
    elif pre_q5 > pre_q4:
        pre1950_tail = "Q5가 가장 높다."
    else:
        pre1950_tail = "Q4와 Q5가 같다."

    gwr_lines: list[str] = []
    gwr_path = TABLES / "plan02_gwr_summary.csv"
    if gwr_path.exists():
        gwr = pd.read_csv(gwr_path)
        rent = gwr.loc[gwr["term"] == "renter_rate"].iloc[0]
        scale = float(rent.effect_scale)
        p10 = float(rent.local_p10) * scale
        p50 = float(rent.local_p50) * scale
        p90 = float(rent.local_p90) * scale
        if p10 > 0 and p90 > 0:
            direction = "10–90백분위의 부호는 같다. 임차율이 높을수록 민원율이 높은 방향은 지역마다 유지되고, 크기는 달라진다."
        elif p10 < 0 and p90 < 0:
            direction = "10–90백분위의 부호는 같다. 임차율이 높을수록 민원율이 낮은 방향은 지역마다 유지되고, 크기는 달라진다."
        elif float(rent.share_positive) >= 0.8:
            direction = "하위 10%는 부호가 반대다. 대부분은 임차율이 높을수록 민원율이 높은 쪽이다."
        else:
            direction = "10–90백분위의 부호가 다르다. 임차율과 민원율의 방향은 지역에 따라 바뀐다."
        if float(rent.aicc) < float(rent.aicc_ols):
            fit_phrase = "지역 계수를 허용한 쪽의 AICc가 더 작다."
        else:
            fit_phrase = "전역 식의 AICc가 더 작다."
        borough_gwr = pd.read_csv(TABLES / "plan02_gwr_borough.csv")
        borough_txt = ", ".join(
            f"{row.borough} {row.renter_10pp_median:.0f}" for row in borough_gwr.itertuples()
        )
        gwr_lines = [
            (
                f"지역 가중 회귀는 임차·소득·밀도·빈곤만 넣고, 네 변수가 같은 이웃 수를 쓴다. "
                f"가까운 {int(rent.bandwidth_k)}개 Tract에 이중제곱 가중을 두었고, 이 이웃 수는 후보 중 AICc가 가장 작은 값이다. "
                f"GWR AICc는 {float(rent.aicc):.0f}, 같은 식의 전역 OLS AICc는 {float(rent.aicc_ols):.0f}이다. {fit_phrase}"
                + (
                    " AICc는 후보 중 가장 짧은 이웃에서 가장 작았다."
                    if int(rent.bandwidth_at_grid_edge) == 1
                    else ""
                )
            ),
            (
                f"임차율 10%p의 지역 계수는 10백분위 {p10:.1f}건, 중앙값 {p50:.1f}건, 90백분위 {p90:.1f}건이다. "
                f"양수인 Tract는 {float(rent.share_positive) * 100:.0f}%다. {direction} "
                f"전역 계수(자치구 없음)는 {float(rent.global_coef) * scale:.1f}건이다."
            ),
            f"자치구별 임차율 10%p 지역 계수 중앙값은 {borough_txt}이다.",
        ]

        def band(term: str) -> str:
            row = gwr.loc[gwr["term"] == term].iloc[0]
            unit = float(row.effect_scale)
            return (
                f"{float(row.local_p10) * unit:.1f}, "
                f"{float(row.local_p50) * unit:.1f}, "
                f"{float(row.local_p90) * unit:.1f}"
            )

        gwr_lines.append(
            "같은 10·50·90백분위로 보면 "
            f"소득 1만 달러는 {band('income_10k')}, "
            f"밀도 1,000명/km²는 {band('density_10k')}, "
            f"빈곤 10%p는 {band('poverty_rate')}이다."
        )

    def higher_phrase(subject: str, rho: float, outcome: str) -> str:
        if rho > 0:
            return f"{subject}이 높을수록 {outcome} 순위가 높다."
        if rho < 0:
            return f"{subject}이 높을수록 {outcome} 순위가 낮다."
        return f"{subject}과 {outcome} 순위는 함께 움직이지 않는다."
    lines = [
        "# 개요 기준 핵심 분석",
        "",
        "분석계획서의 우선순위 세 가지를 계산했다. 임차율과 민원율, 민원 유형, 이웃 Tract와의 군집이다. 결과는 연관이며 같은 해의 인과가 아니다. 311은 2025-11-01부터 2026-10-31이고 ACS는 2024년 5개년 추정치다.",
        "",
        "## 유형 재분류",
        "",
        f"전체 {coverage_n:,}건을 소음, 주거환경, 위생, 도로·교통, 해충·동물, 건축·안전, 기타로 나눴다. 기타 비율은 {other_share * 100:.1f}%다. 매핑은 `data/processed/category_map.csv`에 있다.",
        "",
        "## 품질",
        "",
        f"Bronx Tract {OUTLIER}의 민원 {int(outlier.complaints):,}건 가운데 가장 많은 주소는 {outlier.top_address} ({outlier.top_address_share * 100:.1f}%)이다. 최다 유형은 {outlier.top_problem} ({outlier.top_problem_share * 100:.1f}%)이다.",
        f"시스템 중복 플래그 비율은 이 Tract {outlier.duplicate_flag_rate * 100:.2f}%, 시 전체 {outlier.city_duplicate_flag_rate * 100:.2f}%다.",
        "좌표가 없는 민원은 자치구가 비어 있는 행에 몰려 있다. 자치구가 있는 행의 좌표 결측은 1–4%대다.",
        "",
        "## 임차율과 민원율",
        "",
        f"인구 1,000명 이상 Tract에서 임차율과 전체 민원율의 Spearman ρ는 {renter.rho:.2f} (n={int(renter.n):,}, FDR p={renter.p_fdr:.3g})이다.",
        f"중위소득과의 ρ는 {income.rho:.2f} (n={int(income.n):,}, FDR p={income.p_fdr:.3g})이다.",
        f"임차율과 주거 민원율의 ρ는 {housing.rho:.2f}, 인구밀도와 소음 민원율의 ρ는 {noise.rho:.2f}이다.",
        "계획서 식은 임차율, 소득 1만 달러, 인구밀도 1만 명/km², 빈곤율, 자치구다. 표준오차는 HC1이다.",
        (
            f"이 식이 맞는 Tract {int(ols_r.n):,}개에서 임차율 10%p는 1,000명당 {ols_r.coef * 0.1:.1f}건 "
            f"(95% CI {ols_r.ci_low * 0.1:.1f}–{ols_r.ci_high * 0.1:.1f}), "
            f"빈곤율 10%p는 {ols_poverty.coef * 0.1:.1f}건 "
            f"(95% CI {ols_poverty.ci_low * 0.1:.1f}–{ols_poverty.ci_high * 0.1:.1f}), "
            f"인구밀도 1,000명/km²당 {ols_density.coef * 0.1:.1f}건, "
            f"소득 1만 달러는 {ols_income.coef:+.1f}건이다. R²는 {ols_r.r_squared:.2f}이다."
        ),
        (
            f"같은 표본에서 자치구를 빼면 임차율 10%p는 {bare_renter.coef * 0.1:.1f}건이다. "
            f"임차율과 소득만 넣고 자치구를 통제하면 임차율 10%p는 {core_renter.coef * 0.1:.1f}건이고 "
            f"소득 1만 달러는 {core_income.coef:+.1f}건이다. "
            f"소득의 순위 상관은 음수이고, 임차율과 자치구를 같이 넣은 핵심 모형에서는 부호가 양수다."
        ),
        f"계획서 식에서 설명변수 VIF가 가장 큰 항은 {vif_label} {vif_row.vif:.1f}이다.",
        f"카운트 모형({count_r.family}, Pearson 산포 {count_r.dispersion_pearson:.1f})에서 임차율 10%p 증가의 발생률비는 {count_r.irr_per_10pp_or_10k:.3f}이다. 이 모형도 밀도·빈곤·자치구를 포함한다.",
        (
            f"계획서 식 잔차의 Moran's I는 {residual_i.estimate:.3f} "
            f"(n={int(residual_i.n):,}, 순열 p={residual_i.p_value:.3f})이다. "
            f"공간시차 계수 ρ는 {sar_w.estimate:.3f} (p={sar_w.p_value:.3g})이고, "
            f"그때 임차율 10%p는 {sar_renter.estimate * 0.1:.1f}건이다. "
            f"공간오차 λ는 {sem_lambda.estimate:.3f}이고, 그때 임차율 10%p는 {sem_renter.estimate * 0.1:.1f}건이다."
        ),
        *gwr_lines,
        f"극단 Tract를 빼면 임차율 Spearman ρ는 {base.renter_rho:.2f}에서 {dropped.renter_rho:.2f}로 바뀐다. 방향은 유지된다.",
        f"자치구 간 민원율 분포 차이의 Kruskal-Wallis ε²는 {kw.iloc[0].epsilon_squared:.3f} (p={kw.iloc[0].p_value:.3g})이다.",
        "",
        "## 빈곤율과 주택 노후도",
        "",
        "빈곤율은 빈곤선 이하 인구를 빈곤 상태 판정 인구로 나눈 값이다. 주택 연령은 2024년에서 중위 건축연도를 뺀 값이고, 1950년 이전 비율은 1939년 이전 주택과 1940–1949년 주택을 건축연도 집계 주택으로 나눈 값이다.",
        f"인구 1,000명 이상 Tract에서 빈곤율과 위생 민원율의 Spearman ρ는 {poverty.rho:.2f} (n={int(poverty.n):,}, FDR p={poverty.p_fdr:.3g})이다. {higher_phrase('빈곤율', poverty.rho, '위생 민원율')} 가설 H4의 예상 방향은 양(+)이다.",
        f"빈곤율 5분위의 인구 가중 위생 민원율은 {span('poverty_rate')}이다.",
        f"빈곤율과 해충 민원율의 ρ는 {pest_poverty.rho:.2f} (n={int(pest_poverty.n):,}, FDR p={pest_poverty.p_fdr:.3g})이다. {higher_phrase('빈곤율', pest_poverty.rho, '해충 민원율')}",
        f"1950년 이전 주택 비율과 주거 민원율의 ρ는 {pre1950.rho:.2f} (n={int(pre1950.n):,}, FDR p={pre1950.p_fdr:.3g})이다. {higher_phrase('1950년 이전 주택 비율', pre1950.rho, '주거 민원율')}",
        f"주택 연령과 주거 민원율의 ρ는 {age.rho:.2f} (n={int(age.n):,}, FDR p={age.p_fdr:.3g})이다. {higher_phrase('주택 연령', age.rho, '주거 민원율')} 가설 H5의 예상 방향은 양(+)이다.",
        f"중위 건축연도가 1939년 이전 구간에 들어가면 요약표에는 1938로 적힌다. 건축연도가 있는 Tract {year_n:,}개 중 {year_floor_n:,}개가 이 값이라, 주택 연령은 오래된 주택끼리의 차이를 거의 구분하지 못한다.",
        f"1950년 이전 주택 비율 5분위의 인구 가중 주거 민원율은 {quintile_list('pre1950_share')}이다. {pre1950_tail}",
        "",
        "## 공간 군집",
        "",
        (
            f"인구 1,000명 이상 Tract {int(moran_row.n):,}개의 Moran's I는 {moran_row.moran_i:.3f} "
            f"(기댓값 {moran_row.expected_i:.4f}, 순열 {int(moran_row.perms)}회 p={moran_row.p_value_perm:.3f})이다. "
            f"맞닿은 이웃이 없는 {int(moran_row.knn_linked)}개 Tract는 가까운 4개 Tract를 이웃으로 넣었다."
        ),
        (
            f"FDR 5%에서 유의한 High-High는 {int(moran_row.hh)}개, Low-Low는 {int(moran_row.ll)}개, "
            f"High-Low는 {int(moran_row.hl)}개, Low-High는 {int(moran_row.lh)}개다. "
            f"보정 전 5%에서는 High-High {int(moran_row.hh_p05)}개, Low-Low {int(moran_row.ll_p05)}개다."
        ),
        (
            f"Getis-Ord Gi*에서 FDR 5% 핫스팟은 {int(moran_row.gi_hot)}개, "
            f"콜드스팟은 {int(moran_row.gi_cold)}개다. Gi*의 p값은 정규근사라 순열 LISA와 같은 기준이 아니다."
        ),
        (
            f"순열 p의 하한은 {1 / (int(moran_row.perms) + 1):.3f}이고, "
            f"그 하한에 닿은 Tract는 {int(moran_row.lisa_at_floor)}개다. "
            f"Tract가 {int(moran_row.n):,}개라 이 하한만으로는 FDR 5%를 통과하기 어렵다. "
            + (
                "전역 Moran's I는 유의하지만, 개별 Tract의 LISA는 FDR 뒤 유의하지 않다."
                if int(moran_row.hh + moran_row.ll + moran_row.hl + moran_row.lh) == 0
                else "FDR을 통과한 Tract만 군집 지도의 유의 색으로 표시한다."
            )
        ),
        "",
        "기타로 남은 건수가 큰 유형은 아래와 같다.",
        "",
    ]
    for row in other_top.head(8).itertuples():
        lines.append(f"- {row.problem}: {int(row.n):,}건")
    lines.extend(["", "표는 `outputs/tables/plan02_*.csv`, 지도용 경계는 `data/processed/tract_dashboard.geojson`이다.", ""])
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    print("311을 읽고 유형을 붙이는 중...")
    requests = load_requests()
    categories = category_map(requests)
    save(categories, "plan02_category_summary.csv")
    quality = quality_tables(requests)
    save(quality["missing_type"], "plan02_missing_by_type.csv")
    save(quality["missing_borough"], "plan02_missing_by_borough.csv")
    save(quality["outlier_problems"], "plan02_outlier_problems.csv")
    save(quality["outlier_addresses"], "plan02_outlier_addresses.csv")
    save(quality["outlier_summary"], "plan02_outlier_summary.csv")
    month, noise_hour = time_tables(requests)
    save(month, "plan02_monthly.csv")
    save(noise_hour, "plan02_noise_dow_hour.csv")
    other_top = (
        requests.loc[requests["category"] == "기타", "problem"]
        .value_counts()
        .head(15)
        .rename_axis("problem")
        .reset_index(name="n")
    )
    save(other_top, "plan02_other_top.csv")
    composition = (
        requests.loc[requests["borough_label"].notna()]
        .groupby(["borough_label", "category"])
        .size()
        .reset_index(name="n")
    )
    save(composition, "plan02_borough_category.csv")

    print("Tract 지표를 만드는 중...")
    tracts = tract_frame(requests)
    del requests
    keep_cols = [
        "GEOID",
        "borough",
        "total_pop",
        "median_income",
        "renter_rate",
        "complaint_count",
        "complaints_per_1k",
        "area_km2",
        "pop_density",
        "소음",
        "주거환경",
        "위생",
        "도로·교통",
        "해충·동물",
        "건축·안전",
        "기타",
        "noise_rate",
        "housing_rate",
        "sanitation_rate",
        "road_rate",
        "pest_rate",
        "building_rate",
        "poverty_rate",
        "pre1950_share",
        "median_year_built",
        "housing_age",
        "stable",
    ]
    save(tracts[keep_cols], "plan02_tracts.csv")

    relations = relationship_tables(tracts)
    save(relations["correlations"], "plan02_correlations.csv")
    save(relations["quintiles"], "plan02_quintiles.csv")

    print("회귀와 민감도...")
    stable = tracts.loc[tracts["stable"]]
    ols = ols_comparison(stable)
    save(ols, "plan02_ols.csv")
    counts = count_model(stable)
    save(counts, "plan02_count_model.csv")
    sens = sensitivity(tracts)
    save(sens, "plan02_sensitivity.csv")
    spatial = residual_spatial(stable)
    save(spatial, "plan02_residual_spatial.csv")
    kw = kruskal_borough(stable)
    save(kw, "plan02_kruskal.csv")

    print("Moran's I...")
    moran_summary, local = moran(tracts)
    save(moran_summary, "plan02_moran.csv")
    save(local, "plan02_lisa.csv")
    dashboard_map(tracts, local)
    print("GWR...")
    gwr_summary, gwr_local, gwr_borough = fit_gwr(tracts)
    save(gwr_summary, "plan02_gwr_summary.csv")
    save(gwr_local, "plan02_gwr_local.csv")
    save(gwr_borough, "plan02_gwr_borough.csv")
    attach_gwr_map(gwr_local)
    write_report(
        coverage_n=int(categories["n"].sum()),
        categories=categories,
        quality=quality,
        correlations=relations["correlations"],
        quintiles=relations["quintiles"],
        ols=ols,
        counts=counts,
        sens=sens,
        kw=kw,
        moran_summary=moran_summary,
        other_top=other_top,
        spatial=spatial,
    )
    print(categories.to_string(index=False))
    print(moran_summary.to_string(index=False))
    print(REPORT)


def _as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin(["true", "1"])


def save_models(tracts: pd.DataFrame):
    """계획서 식 회귀, 민감도, 잔차 공간상관을 저장한다."""
    stable = tracts.loc[tracts["stable"]]
    ols = ols_comparison(stable)
    save(ols, "plan02_ols.csv")
    counts = count_model(stable)
    save(counts, "plan02_count_model.csv")
    sens = sensitivity(tracts)
    save(sens, "plan02_sensitivity.csv")
    spatial = residual_spatial(stable)
    save(spatial, "plan02_residual_spatial.csv")
    return ols, counts, sens, spatial


def refresh_regression() -> None:
    """311 원본 없이 Tract 표로 회귀와 잔차 공간상관만 다시 계산한다."""
    tracts = pd.read_csv(TABLES / "plan02_tracts.csv", dtype={"GEOID": str})
    tracts["stable"] = _as_bool(tracts["stable"])
    print("회귀와 잔차 공간상관...")
    ols, counts, sens, spatial = save_models(tracts)
    categories = pd.read_csv(TABLES / "plan02_category_summary.csv")
    write_report(
        coverage_n=int(categories["n"].sum()),
        categories=categories,
        quality={"outlier_summary": pd.read_csv(TABLES / "plan02_outlier_summary.csv")},
        correlations=pd.read_csv(TABLES / "plan02_correlations.csv"),
        quintiles=pd.read_csv(TABLES / "plan02_quintiles.csv"),
        ols=ols,
        counts=counts,
        sens=sens,
        kw=pd.read_csv(TABLES / "plan02_kruskal.csv"),
        moran_summary=pd.read_csv(TABLES / "plan02_moran.csv"),
        other_top=pd.read_csv(TABLES / "plan02_other_top.csv"),
        spatial=spatial,
    )
    focus = ols.loc[
        ols["term"].isin(["renter_rate", "income_10k", "density_10k", "poverty_rate"]),
        ["model", "term", "coef", "p_value", "vif", "r_squared", "n"],
    ]
    print(focus.to_string(index=False))
    print(
        spatial.loc[spatial["term"].isin(["moran_i", "Wy", "lambda", "renter_rate"])].to_string(
            index=False
        )
    )
    print(REPORT)


def refresh_relationships() -> None:
    """311 원본을 다시 읽지 않고, 보충된 ACS로 상관·5분위·보고서를 다시 쓴다."""
    tracts = pd.read_csv(TABLES / "plan02_tracts.csv", dtype={"GEOID": str})
    acs = pd.read_csv(
        PROCESSED / "nyc_acs_2024_5yr.csv",
        dtype={"GEOID": str},
        usecols=["GEOID", "poverty_rate", "pre1950_share", "median_year_built", "housing_age"],
    )
    overlap = [column for column in acs.columns if column != "GEOID" and column in tracts.columns]
    if overlap:
        tracts = tracts.drop(columns=overlap)
    tracts = tracts.merge(acs, on="GEOID", how="left", validate="one_to_one")
    tracts["stable"] = _as_bool(tracts["stable"])
    save(tracts, "plan02_tracts.csv")
    relations = relationship_tables(tracts)
    save(relations["correlations"], "plan02_correlations.csv")
    save(relations["quintiles"], "plan02_quintiles.csv")
    ols, counts, sens, spatial = save_models(tracts)
    categories = pd.read_csv(TABLES / "plan02_category_summary.csv")
    write_report(
        coverage_n=int(categories["n"].sum()),
        categories=categories,
        quality={"outlier_summary": pd.read_csv(TABLES / "plan02_outlier_summary.csv")},
        correlations=relations["correlations"],
        quintiles=relations["quintiles"],
        ols=ols,
        counts=counts,
        sens=sens,
        kw=pd.read_csv(TABLES / "plan02_kruskal.csv"),
        moran_summary=pd.read_csv(TABLES / "plan02_moran.csv"),
        other_top=pd.read_csv(TABLES / "plan02_other_top.csv"),
        spatial=spatial,
    )
    show = relations["correlations"]
    show = show.loc[show["variable"].isin(["poverty_rate", "pre1950_share", "housing_age"])]
    print(show.to_string(index=False))
    print(REPORT)


def refresh_spatial() -> None:
    """저장된 Tract 집계로 LISA·Gi*와 지도·보고서를 다시 쓴다."""
    tracts = pd.read_csv(TABLES / "plan02_tracts.csv", dtype={"GEOID": str})
    tracts["stable"] = _as_bool(tracts["stable"])
    summary, local = moran(tracts)
    save(summary, "plan02_moran.csv")
    save(local, "plan02_lisa.csv")
    dashboard_map(tracts, local)
    sens = pd.read_csv(TABLES / "plan02_sensitivity.csv")
    sens["drop_outlier"] = _as_bool(sens["drop_outlier"])
    categories = pd.read_csv(TABLES / "plan02_category_summary.csv")
    write_report(
        coverage_n=int(categories["n"].sum()),
        categories=categories,
        quality={"outlier_summary": pd.read_csv(TABLES / "plan02_outlier_summary.csv")},
        correlations=pd.read_csv(TABLES / "plan02_correlations.csv"),
        quintiles=pd.read_csv(TABLES / "plan02_quintiles.csv"),
        ols=pd.read_csv(TABLES / "plan02_ols.csv"),
        counts=pd.read_csv(TABLES / "plan02_count_model.csv"),
        sens=sens,
        kw=pd.read_csv(TABLES / "plan02_kruskal.csv"),
        moran_summary=summary,
        other_top=pd.read_csv(TABLES / "plan02_other_top.csv"),
        spatial=pd.read_csv(TABLES / "plan02_residual_spatial.csv"),
    )
    print(summary.to_string(index=False))
    print(REPORT)


def refresh_gwr() -> None:
    """저장된 Tract 집계로 지역 가중 회귀, 지도, 보고서를 다시 쓴다."""
    tracts = pd.read_csv(TABLES / "plan02_tracts.csv", dtype={"GEOID": str})
    tracts["stable"] = _as_bool(tracts["stable"])
    summary, local, borough = fit_gwr(tracts)
    save(summary, "plan02_gwr_summary.csv")
    save(local, "plan02_gwr_local.csv")
    save(borough, "plan02_gwr_borough.csv")
    attach_gwr_map(local)
    sens = pd.read_csv(TABLES / "plan02_sensitivity.csv")
    sens["drop_outlier"] = _as_bool(sens["drop_outlier"])
    categories = pd.read_csv(TABLES / "plan02_category_summary.csv")
    write_report(
        coverage_n=int(categories["n"].sum()),
        categories=categories,
        quality={"outlier_summary": pd.read_csv(TABLES / "plan02_outlier_summary.csv")},
        correlations=pd.read_csv(TABLES / "plan02_correlations.csv"),
        quintiles=pd.read_csv(TABLES / "plan02_quintiles.csv"),
        ols=pd.read_csv(TABLES / "plan02_ols.csv"),
        counts=pd.read_csv(TABLES / "plan02_count_model.csv"),
        sens=sens,
        kw=pd.read_csv(TABLES / "plan02_kruskal.csv"),
        moran_summary=pd.read_csv(TABLES / "plan02_moran.csv"),
        other_top=pd.read_csv(TABLES / "plan02_other_top.csv"),
        spatial=pd.read_csv(TABLES / "plan02_residual_spatial.csv"),
    )
    print(summary.to_string(index=False))
    print(borough.to_string(index=False))
    print(REPORT)


if __name__ == "__main__":
    import sys

    if "--refresh-regression" in sys.argv:
        refresh_regression()
    elif "--refresh-relationships" in sys.argv:
        refresh_relationships()
    elif "--refresh-spatial" in sys.argv:
        refresh_spatial()
    elif "--refresh-gwr" in sys.argv:
        refresh_gwr()
    else:
        main()
