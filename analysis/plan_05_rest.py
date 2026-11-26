"""예측 해석, 민원 구성 군집, 잔차, 예측 구간, 최종 보고서.

원본 311 파일이 없어 민원 문장, 좌표 밀집, 일별 시계열은 계산하지 않는다.
난수 고정값: 42.

실행 (프로젝트 루트):
    py -3 analysis/plan_05_rest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.inspection import permutation_importance
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

import plan_02_core as core
import plan_05a_predict as ml

TABLES = ROOT / "outputs" / "tables"
REPORT = ROOT / "reports" / "plan_05_rest.md"
FINAL = ROOT / "reports" / "final_report.md"
MAP = ROOT / "data" / "processed" / "tract_dashboard.geojson"
SHARES = {
    "소음": "소음",
    "주거환경": "주거",
    "위생": "위생",
    "도로·교통": "도로",
    "해충·동물": "해충",
    "건축·안전": "건축",
}
FOCUS = ["renter_rate", "median_income", "pop_density", "poverty_rate", "housing_age", "pre1950_share"]


def save(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(TABLES / name, index=False)


def fit_model(frame: pd.DataFrame):
    features = ml.design(frame, use_borough=True)
    y = frame["complaints_per_1k"].to_numpy(dtype=float)
    weight = frame["total_pop"].to_numpy(dtype=float)
    model = ml.make_model("lightgbm")
    model.fit(features, y, sample_weight=weight)
    return features, y, weight, model


def shap_tables(frame: pd.DataFrame, features: pd.DataFrame, model) -> tuple[pd.DataFrame, pd.DataFrame]:
    contrib = model.predict(features, pred_contrib=True)
    values = contrib[:, :-1]
    rows = []
    for index, name in enumerate(features.columns):
        column = features[name].to_numpy(dtype=float)
        effect = values[:, index]
        valid = np.isfinite(column)
        high = np.nanmedian(column) if valid.any() else np.nan
        above = valid & (column >= high)
        below = valid & (column < high)
        if above.sum() < 20 or below.sum() < 20:
            direction = np.nan
        else:
            direction = float(effect[above].mean() - effect[below].mean())
        rows.append(
            {
                "term": name,
                "mean_abs": float(np.abs(effect).mean()),
                "high_minus_low": direction,
            }
        )
    summary = pd.DataFrame(rows).sort_values("mean_abs", ascending=False)
    outlier = frame["GEOID"].astype(str) == ml.OUTLIER
    detail = pd.DataFrame({"term": features.columns, "shap": values[np.flatnonzero(outlier)[0]]})
    return summary, detail


def pdp_table(features: pd.DataFrame, model) -> pd.DataFrame:
    rows = []
    for name in FOCUS:
        column = features[name].to_numpy(dtype=float)
        grid = np.quantile(column[np.isfinite(column)], np.linspace(0.05, 0.95, 11))
        grid = np.unique(grid)
        for value in grid:
            changed = features.copy()
            changed[name] = value
            rows.append(
                {
                    "term": name,
                    "value": float(value),
                    "mean_prediction": float(model.predict(changed).mean()),
                }
            )
    return pd.DataFrame(rows)


def permutation_table(frame: pd.DataFrame) -> pd.DataFrame:
    features = ml.design(frame, use_borough=True)
    y = frame["complaints_per_1k"].to_numpy(dtype=float)
    pieces = []
    for _fold, _label, train, test in ml.splits(frame, "spatial_block"):
        model = ml.make_model("lightgbm")
        model.fit(features.iloc[train], y[train], sample_weight=frame.iloc[train]["total_pop"])
        importance = permutation_importance(
            model,
            features.iloc[test],
            y[test],
            n_repeats=5,
            random_state=42,
            scoring="neg_mean_absolute_error",
        )
        pieces.append(pd.Series(importance.importances_mean, index=features.columns))
    mean = pd.concat(pieces, axis=1).mean(axis=1)
    return (
        pd.DataFrame({"term": mean.index, "mae_increase": mean.to_numpy()})
        .sort_values("mae_increase", ascending=False)
        .reset_index(drop=True)
    )


def residual_moran(oof: pd.DataFrame) -> pd.DataFrame:
    boundaries = gpd.read_file(core.TRACT_GEO)[["GEOID", "geometry"]]
    boundaries["GEOID"] = boundaries["GEOID"].astype(str)
    part = boundaries.merge(oof, on="GEOID", how="inner")
    part["residual"] = part["complaints_per_1k"] - part["pred"]
    connected, weights = core.connected_queen(part)
    values = connected["residual"].to_numpy(dtype=float)
    centered = values - values.mean()
    n = len(centered)
    lagged = weights @ centered
    stat = float((n / weights.sum()) * (np.dot(centered, lagged) / np.dot(centered, centered)))
    expected = -1 / (n - 1)
    rng = np.random.default_rng(42)
    extreme = 1
    for _ in range(999):
        shuffled = rng.permutation(centered)
        lagged_s = weights @ shuffled
        draw = (n / weights.sum()) * (np.dot(shuffled, lagged_s) / np.dot(shuffled, shuffled))
        extreme += abs(draw) >= abs(stat)
    return pd.DataFrame(
        [
            {
                "n": n,
                "moran_i": stat,
                "expected_i": expected,
                "p_value_perm": extreme / 1000,
                "perms": 999,
                "mean_residual": float(values.mean()),
                "share_above": float((values > 0).mean()),
            }
        ]
    )


def composition(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    part = frame.loc[frame["complaint_count"] > 0].copy()
    for column, short in SHARES.items():
        part[short] = part[column] / part["complaint_count"]
    share_cols = list(SHARES.values())
    matrix = part[share_cols].to_numpy(dtype=float)
    matrix = np.column_stack([matrix, np.log1p(part["complaints_per_1k"].to_numpy(dtype=float))])
    scaled = StandardScaler().fit_transform(matrix)
    scores = []
    for k in range(3, 9):
        labels = KMeans(n_clusters=k, n_init=20, random_state=42).fit_predict(scaled)
        scores.append({"k": k, "silhouette": float(silhouette_score(scaled, labels))})
    score_frame = pd.DataFrame(scores)
    best_k = int(score_frame.loc[score_frame["silhouette"].idxmax(), "k"])
    labels = KMeans(n_clusters=best_k, n_init=20, random_state=42).fit_predict(scaled)
    part["cluster"] = labels
    city = part[share_cols].median()
    names = {}
    used = set()
    for cluster, group in part.groupby("cluster"):
        excess = group[share_cols].median() - city
        lead = excess.idxmax()
        name = f"{lead} 중심" if float(excess[lead]) >= 0.03 else "혼합"
        if name in used:
            higher = group["complaints_per_1k"].median() >= part["complaints_per_1k"].median()
            name = f"{name} {'높음' if higher else '낮음'}"
        used.add(name)
        names[cluster] = name
    part["complaint_type"] = part["cluster"].map(names)
    profile = (
        part.groupby("complaint_type", as_index=False)
        .agg(
            tracts=("GEOID", "size"),
            rate_median=("complaints_per_1k", "median"),
            income_median=("median_income", "median"),
            renter_median=("renter_rate", "median"),
            **{column: (column, "median") for column in share_cols},
        )
        .sort_values("tracts", ascending=False)
    )
    tests = []
    for column, label in (("median_income", "중위소득"), ("renter_rate", "임차율")):
        groups = [
            group[column].dropna().to_numpy()
            for _, group in part.groupby("complaint_type")
            if group[column].notna().sum() > 0
        ]
        result = stats.kruskal(*groups)
        n = int(part[column].notna().sum())
        tests.append(
            {
                "variable": label,
                "H": float(result.statistic),
                "p_value": float(result.pvalue),
                "epsilon_squared": float(result.statistic / (n - 1)) if n > 1 else np.nan,
                "n": n,
            }
        )
    pca = PCA(n_components=2, random_state=42).fit(scaled)
    loadings = pd.DataFrame(
        pca.components_.T,
        index=share_cols + ["log_rate"],
        columns=["axis_1", "axis_2"],
    ).reset_index(names="term")
    loadings["explained_1"] = float(pca.explained_variance_ratio_[0])
    loadings["explained_2"] = float(pca.explained_variance_ratio_[1])
    forest = IsolationForest(n_estimators=500, contamination=0.02, random_state=42)
    flags = forest.fit_predict(np.nan_to_num(scaled, nan=0.0))
    anomalies = part.loc[flags == -1, ["GEOID", "borough", "complaints_per_1k", "complaint_type", *share_cols]]
    anomalies = anomalies.sort_values("complaints_per_1k", ascending=False)
    assigned = part[["GEOID", "complaint_type"]].copy()
    return score_frame, profile, pd.DataFrame(tests), loadings, anomalies, assigned


def conformal(frame: pd.DataFrame) -> pd.DataFrame:
    features = ml.design(frame, use_borough=True)
    y = frame["complaints_per_1k"].to_numpy(dtype=float)
    weight = frame["total_pop"].to_numpy(dtype=float)
    rows = []
    xy = frame[["cx", "cy"]].to_numpy()
    blocks = KMeans(n_clusters=25, n_init=10, random_state=42).fit_predict(xy)
    for fold, (train, test) in enumerate(
        __import__("sklearn.model_selection", fromlist=["GroupKFold"]).GroupKFold(n_splits=5).split(frame, y, blocks)
    ):
        train_blocks = np.unique(blocks[train])
        rng = np.random.default_rng(42 + fold)
        cal_blocks = set(rng.choice(train_blocks, size=max(1, len(train_blocks) // 5), replace=False))
        cal = np.isin(blocks[train], list(cal_blocks))
        fit_idx = train[~cal]
        cal_idx = train[cal]
        model = ml.make_model("lightgbm")
        model.fit(features.iloc[fit_idx], y[fit_idx], sample_weight=weight[fit_idx])
        cal_gap = np.abs(y[cal_idx] - model.predict(features.iloc[cal_idx]))
        width = float(np.quantile(cal_gap, 0.9 * (1 + 1 / len(cal_gap))))
        pred = model.predict(features.iloc[test])
        covered = np.abs(y[test] - pred) <= width
        rows.append(
            {
                "fold": fold,
                "n_test": int(len(test)),
                "width": width,
                "coverage": float(covered.mean()),
            }
        )
    return pd.DataFrame(rows)


def partial_renter(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.loc[frame["renter_rate"].notna()].reset_index(drop=True)
    controls = [column for column in ml.NUMERIC if column != "renter_rate"]
    y = frame["complaints_per_1k"].to_numpy(dtype=float)
    renter = frame["renter_rate"].to_numpy(dtype=float)
    y_resid = np.zeros(len(frame))
    r_resid = np.zeros(len(frame))
    for _fold, _label, train, test in ml.splits(frame, "spatial_block"):
        x_train = frame.iloc[train][controls]
        x_test = frame.iloc[test][controls]
        y_model = ml.make_model("hgb")
        y_model.set_params(loss="squared_error")
        y_model.fit(x_train, y[train], sample_weight=frame.iloc[train]["total_pop"])
        r_model = ml.make_model("hgb")
        r_model.set_params(loss="squared_error")
        r_model.fit(x_train, renter[train])
        y_resid[test] = y[test] - y_model.predict(x_test)
        r_resid[test] = renter[test] - r_model.predict(x_test)
    fit = sm.OLS(y_resid, sm.add_constant(r_resid)).fit(cov_type="HC1")
    return pd.DataFrame(
        [
            {
                "term": "renter_rate",
                "coef": float(fit.params[1]),
                "se": float(fit.bse[1]),
                "p_value": float(fit.pvalues[1]),
                "per_10pp": float(fit.params[1] * 0.1),
                "n": int(len(frame)),
            }
        ]
    )


def pdp_sentence(pdp: pd.DataFrame, term: str, unit: str) -> str:
    part = pdp.loc[pdp["term"] == term].sort_values("value")
    low = float(part["mean_prediction"].iloc[0])
    high = float(part["mean_prediction"].iloc[-1])
    if high > low + 5:
        direction = "값이 커질수록 평균 예측 민원율이 높다"
    elif low > high + 5:
        direction = "값이 커질수록 평균 예측 민원율이 낮다"
    else:
        direction = "평균 예측 민원율의 변화가 작다"
    return f"{unit}: {direction} ({low:.0f}에서 {high:.0f})."


def write_reports(
    shap: pd.DataFrame,
    pdp: pd.DataFrame,
    perm: pd.DataFrame,
    moran: pd.DataFrame,
    scores: pd.DataFrame,
    profile: pd.DataFrame,
    tests: pd.DataFrame,
    anomalies: pd.DataFrame,
    bands: pd.DataFrame,
    partial: pd.DataFrame,
) -> None:
    moran_row = moran.iloc[0]
    renter = shap.loc[shap["term"] == "renter_rate"].iloc[0]
    best = scores.loc[scores["silhouette"].idxmax()]
    band = bands["coverage"].mean()
    partial_row = partial.iloc[0]
    top_perm = perm.iloc[0]
    outlier_flag = ml.OUTLIER in set(anomalies["GEOID"].astype(str))
    lines = [
        "# 예측 해석과 민원 구성",
        "",
        "LightGBM의 기여도는 로그 민원율 척도의 SHAP이다. 방향은 그 변수가 중앙값 이상인 Tract의 평균 기여에서 중앙값 미만의 평균 기여를 뺀 값이다. 이것은 연관이며 인과가 아니다.",
        f"평균 절대 기여가 가장 큰 항목은 {shap.iloc[0].term} ({shap.iloc[0].mean_abs:.3f})이다. 임차율의 높은 쪽 기여 차이는 {renter.high_minus_low:+.3f}이다.",
        f"공간 블록 검증에서 섞었을 때 MAE가 가장 많이 늘어나는 변수는 {top_perm.term} ({top_perm.mae_increase:.1f})이다.",
        pdp_sentence(pdp, "renter_rate", "임차율"),
        pdp_sentence(pdp, "median_income", "중위소득"),
        pdp_sentence(pdp, "pop_density", "인구밀도"),
        pdp_sentence(pdp, "poverty_rate", "빈곤율"),
        (
            f"공간 교차검증 잔차의 Moran's I는 {moran_row.moran_i:.3f} "
            f"(n={int(moran_row.n):,}, 순열 999회 p={moran_row.p_value_perm:.3f})이다. "
            f"평균 잔차는 {moran_row.mean_residual:.0f}건으로 양수지만, 예측보다 높은 Tract는 {moran_row.share_above:.0%}다. "
            "평균을 끌어올린 것은 일부 Tract의 큰 초과다. "
            "이 잔차가 크다고 해서 그 지역의 문제가 더 심각하다고 단정하지 않는다. 신고 성향의 차이일 수 있다."
        ),
        (
            f"민원 구성 군집은 실루엣이 가장 높은 {int(best.k)}개다 (실루엣 {best.silhouette:.3f}). "
            "군집 특성은 민원 비율과 민원율만 썼고, 소득과 임차율은 군집을 만든 뒤에 비교했다."
        ),
        f"중위소득의 군집 간 Kruskal-Wallis ε²는 {tests.loc[tests.variable=='중위소득','epsilon_squared'].iloc[0]:.3f}이고, 임차율은 {tests.loc[tests.variable=='임차율','epsilon_squared'].iloc[0]:.3f}이다.",
        (
            f"Isolation Forest가 구성이 특이한 Tract로 표시한 곳은 {len(anomalies)}개다. "
            + (
                f"극단 Tract {ml.OUTLIER}이 이 목록에 있다."
                if outlier_flag
                else f"극단 Tract {ml.OUTLIER}은 이 목록에 없다."
            )
            + " 자동으로 삭제하지 않았다."
        ),
        (
            f"공간 블록으로 나눈 90% 예측 구간의 검증 포함 비율은 {band:.0%}이고, "
            f"구간 폭의 중앙값은 {bands['width'].median():.0f}건/1,000명이다."
        ),
        (
            f"소득·밀도·빈곤·주택 특성을 뺀 뒤 남은 임차율 10%p의 조건부 연관은 {partial_row.per_10pp:.1f}건 "
            f"(HC1 p={partial_row.p_value:.3g})이다. 횡단면이라 인과 효과가 아니다."
        ),
        "",
        "원본 311 파일이 없어 민원 문장, 건물 좌표 밀집, 일별 시계열은 계산하지 못했다. 월별 합계만 남아 있다.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    write_final(shap, pdp, moran_row, profile, tests, anomalies, bands, partial_row, best)


def write_final(shap, pdp, moran_row, profile, tests, anomalies, bands, partial_row, best) -> None:
    categories = pd.read_csv(TABLES / "plan02_category_summary.csv")
    total = int(categories["n"].sum())
    other = float(categories.loc[categories["category"] == "기타", "share"].sum())
    corr = pd.read_csv(TABLES / "plan02_correlations.csv")
    ols = pd.read_csv(TABLES / "plan02_ols.csv")
    moran = pd.read_csv(TABLES / "plan02_moran.csv").iloc[0]
    gwr = pd.read_csv(TABLES / "plan02_gwr_summary.csv")
    cv = pd.read_csv(TABLES / "plan05a_cv_summary.csv")
    monthly = pd.read_csv(TABLES / "plan02_monthly.csv")

    def rho(variable: str, outcome: str) -> pd.Series:
        hit = corr.loc[
            (corr["group"] == "시 전체") & (corr["variable"] == variable) & (corr["outcome"] == outcome)
        ]
        return hit.iloc[0]

    def coef(model: str, term: str) -> pd.Series:
        return ols.loc[(ols["model"] == model) & (ols["term"] == term)].iloc[0]

    def score(model: str, scheme: str, drop: bool) -> pd.Series:
        flag = cv["drop_outlier"].astype(str).str.lower().isin(["true", "1"])
        hit = cv.loc[(cv["model"] == model) & (cv["scheme"] == scheme) & (flag == drop)]
        return hit.iloc[0]

    renter = rho("renter_rate", "전체 민원율")
    income = rho("median_income", "전체 민원율")
    poverty = rho("poverty_rate", "위생 민원율")
    old = rho("pre1950_share", "주거 민원율")
    full = coef("full_borough", "renter_rate")
    rent_gwr = gwr.loc[gwr["term"] == "renter_rate"].iloc[0]
    spatial_lgb = score("lightgbm", "spatial_block", False)
    spatial_poi = score("poisson", "spatial_block", False)
    noise_peak = monthly.loc[monthly["noise"].idxmax(), "label"]
    housing_peak = monthly.loc[monthly["housing"].idxmax(), "label"]
    cluster_txt = ", ".join(
        f"{row.complaint_type} {int(row.tracts)}개" for row in profile.itertuples()
    )
    lines = [
        "# 뉴욕시 311 Tract 분석 최종 보고",
        "",
        "단위는 Census Tract다. 311은 2025-11-01부터 2026-10-31이고 ACS는 2024년 5개년이다. 두 시점이 달라 같은 해의 인과로 읽지 않는다. 인구 1,000명 미만은 상관, 회귀, 예측에서 빼었고, Bronx 36005042000은 삭제하지 않았다.",
        "",
        "## 자료와 하지 않은 계산",
        "",
        f"좌표가 있는 민원을 Tract에 붙인 집계를 썼다. 전체 {total:,}건 중 기타 유형은 {other * 100:.1f}%다. 원본 민원 파일이 현재 경로에 없어 문장 주제, 건물 단위 밀집, 일별 시계열은 계산하지 못했다. 월 합계에서는 소음이 {noise_peak}에, 주거 민원이 {housing_peak}에 가장 많다. 외부 점검 자료(주택 위반, 쥐 점검)도 없어 신고 성향을 민원 밖으로 보정하지 못했다.",
        "",
        "## 사회경제 연관",
        "",
        f"인구 1,000명 이상 Tract에서 임차율과 전체 민원율의 Spearman ρ는 {renter.rho:.2f} (n={int(renter.n):,})이다. 중위소득과 전체 민원율의 ρ는 {income.rho:.2f}이다. 빈곤율과 위생 민원율의 ρ는 {poverty.rho:.2f}이고, 1950년 이전 주택 비율과 주거 민원율의 ρ는 {old.rho:.2f}이다.",
        (
            f"임차율, 소득, 밀도, 빈곤, 자치구를 같이 넣은 선형 모형에서 임차율 10%p는 {full.coef * 0.1:.1f}건이고 "
            f"R²는 {full.r_squared:.2f}이다. 소득의 이변량 순위 상관은 음수이고, 임차율과 자치구를 같이 넣으면 소득 계수는 양수다. "
            f"지역 가중 회귀에서 임차율 10%p의 10·50·90백분위는 "
            f"{rent_gwr.local_p10 * rent_gwr.effect_scale:.1f}, "
            f"{rent_gwr.local_p50 * rent_gwr.effect_scale:.1f}, "
            f"{rent_gwr.local_p90 * rent_gwr.effect_scale:.1f}건이다. "
            f"양수인 Tract는 {rent_gwr.share_positive:.0%}다."
        ),
        (
            f"다른 사회경제 변수를 부스팅으로 걷어 낸 뒤 남은 임차율 10%p는 {partial_row.per_10pp:.1f}건이다. "
            "이것도 조건부 연관이다."
        ),
        "",
        "## 공간",
        "",
        (
            f"민원율 Moran's I는 {moran.moran_i:.3f} (순열 {int(moran.perms)}회 p={moran.p_value_perm:.3f})이다. "
            f"FDR 5%의 국지 군집은 High-High {int(moran.hh)}개, Low-Low {int(moran.ll)}개다. "
            f"보정 전 5%에서는 High-High {int(moran.hh_p05)}개, Low-Low {int(moran.ll_p05)}개다. "
            f"Gi* 핫스팟은 {int(moran.gi_hot)}개다. "
            "개별 Tract의 LISA는 순열 p의 하한과 검정 개수 때문에 FDR을 통과하지 못했다."
        ),
        (
            f"사회경제 모형이 설명하지 못한 잔차도 공간적으로 모여 있다. "
            f"교차검증 잔차의 Moran's I는 {moran_row.moran_i:.3f} (p={moran_row.p_value_perm:.3f})이다."
        ),
        "",
        "## 예측",
        "",
        (
            f"공간 블록 검증에서 Poisson 회귀 D²는 {spatial_poi.d2_mean:.3f}, LightGBM D²는 {spatial_lgb.d2_mean:.3f}이다. "
            f"LightGBM의 Spearman ρ는 {spatial_lgb.spearman_mean:.2f}, 상위 20% 적중률은 {spatial_lgb.top20_mean:.0%}다. "
            "Poisson 회귀의 D²가 더 높지만, 그 차이는 폴드 표준편차 안에 있다. "
            "한 자치구를 통째로 빼면 예측은 그 자치구로 잘 넘어가지 않는다."
        ),
        (
            f"변수 기여와 부분의존은 `reports/plan_05_rest.md`에 있다. "
            f"90% 예측 구간의 공간 블록 포함 비율은 {bands['coverage'].mean():.0%}다."
        ),
        "",
        "## 민원 구성",
        "",
        f"민원 비율로 나눈 유형은 {int(best.k)}개다 (실루엣 {best.silhouette:.3f}): {cluster_txt}.",
        (
            f"이 유형 사이의 중위소득 ε²는 {tests.loc[tests.variable=='중위소득','epsilon_squared'].iloc[0]:.3f}, "
            f"임차율 ε²는 {tests.loc[tests.variable=='임차율','epsilon_squared'].iloc[0]:.3f}이다. "
            f"구성이 특이한 Tract는 {len(anomalies)}개이고 삭제하지 않았다."
        ),
        "",
        "## 읽는 법",
        "",
        "임차율이 높은 Tract에서 민원율이 높은 연관은 순위 상관, 선형 모형, 지역 가중 회귀의 중앙값, 조건부 잔차에서 같은 방향이다. 크기는 지역마다 다르고, 하위 꼬리에서는 부호가 반대인 곳도 있다. 예측력이 있는 모형을 자원 배분에 쓰면, 사회경제 변수로 예상한 것보다 신고가 적은 지역이 우선순위에서 밀릴 수 있다. 잔차가 음수인 지역을 문제가 적은 지역으로 보면 안 된다.",
        "",
        "표는 `outputs/tables/plan02_*.csv`, `plan05a_*.csv`, `plan05b_*.csv`, `plan05c_*.csv`, `plan05d_*.csv`에 있다.",
        "",
    ]
    FINAL.write_text("\n".join(lines), encoding="utf-8")


def attach_map(oof: pd.DataFrame, assigned: pd.DataFrame) -> None:
    geo = gpd.read_file(MAP)
    geo["GEOID"] = geo["GEOID"].astype(str)
    extra = oof[["GEOID"]].copy()
    extra["GEOID"] = extra["GEOID"].astype(str)
    extra["oof_residual"] = oof["complaints_per_1k"] - oof["pred"]
    assigned = assigned.copy()
    assigned["GEOID"] = assigned["GEOID"].astype(str)
    for column in ("oof_residual", "complaint_type"):
        if column in geo.columns:
            geo = geo.drop(columns=[column])
    geo = geo.merge(extra, on="GEOID", how="left").merge(assigned, on="GEOID", how="left")
    geo.to_file(MAP, driver="GeoJSON")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame = ml.load_frame().reset_index(drop=True)
    features, _y, _w, model = fit_model(frame)
    print("SHAP, PDP, permutation...")
    shap, outlier = shap_tables(frame, features, model)
    pdp = pdp_table(features, model)
    perm = permutation_table(frame)
    save(shap, "plan05b_shap.csv")
    save(outlier, "plan05b_outlier_shap.csv")
    save(pdp, "plan05b_pdp.csv")
    save(perm, "plan05b_perm.csv")
    print("residual Moran...")
    oof = pd.read_csv(TABLES / "plan05a_oof.csv", dtype={"GEOID": str})
    moran = residual_moran(oof)
    save(moran, "plan05b_residual_moran.csv")
    print("clusters...")
    scores, profile, tests, loadings, anomalies, assigned = composition(frame)
    save(scores, "plan05c_silhouette.csv")
    save(profile, "plan05c_profile.csv")
    save(tests, "plan05c_kruskal.csv")
    save(loadings, "plan05c_pca.csv")
    save(anomalies, "plan05c_anomaly.csv")
    save(assigned, "plan05c_assign.csv")
    print("conformal and partial association...")
    bands = conformal(frame)
    partial = partial_renter(frame)
    save(bands, "plan05d_conformal.csv")
    save(partial, "plan05d_partial.csv")
    attach_map(oof, assigned)
    write_reports(shap, pdp, perm, moran, scores, profile, tests, anomalies, bands, partial)
    print(shap.head(8).to_string(index=False))
    print(profile.to_string(index=False))
    print(moran.to_string(index=False))
    print(partial.to_string(index=False))
    print(FINAL)


if __name__ == "__main__":
    main()
