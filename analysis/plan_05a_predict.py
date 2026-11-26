"""Tract 민원율 예측. 기준 모형과 부스팅을 공간 교차검증으로 비교한다.

설명변수는 ACS와 자치구뿐이다. 민원 건수, 유형 비율, 이웃 민원율, 좌표는 넣지 않는다.
인구 1,000명 미만은 뺀다. 극단 Tract는 넣은 결과와 뺀 결과를 같이 남긴다.
난수 고정값: 42.

실행 (프로젝트 루트):
    py -3 analysis/plan_05a_predict.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import d2_tweedie_score, mean_absolute_error, mean_poisson_deviance
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"
REPORT = ROOT / "reports" / "plan_05a_predict.md"
TRACT_GEO = PROCESSED / "nyc311_tract_complaints.geojson"
OUTLIER = "36005042000"
NUMERIC = [
    "median_income",
    "renter_rate",
    "pop_density",
    "poverty_rate",
    "housing_age",
    "pre1950_share",
]


def load_frame() -> pd.DataFrame:
    tracts = pd.read_csv(TABLES / "plan02_tracts.csv", dtype={"GEOID": str})
    tracts = tracts.loc[tracts["total_pop"] >= 1000].copy()
    boundaries = gpd.read_file(TRACT_GEO)[["GEOID", "geometry"]]
    boundaries["GEOID"] = boundaries["GEOID"].astype(str)
    centroids = boundaries.geometry.to_crs(2263).centroid
    boundaries["cx"] = centroids.x.to_numpy()
    boundaries["cy"] = centroids.y.to_numpy()
    tracts = tracts.merge(boundaries[["GEOID", "cx", "cy"]], on="GEOID", how="inner")
    return tracts.reset_index(drop=True)


def design(frame: pd.DataFrame, use_borough: bool) -> pd.DataFrame:
    features = frame[NUMERIC].astype(float)
    if use_borough:
        dummies = pd.get_dummies(frame["borough"], prefix="borough", dtype=float)
        features = pd.concat([features, dummies], axis=1)
    return features


def make_model(name: str):
    if name == "poisson":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            PoissonRegressor(alpha=1e-3, max_iter=1000),
        )
    if name == "forest":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestRegressor(
                n_estimators=300,
                min_samples_leaf=20,
                max_features="sqrt",
                random_state=42,
                n_jobs=-1,
            ),
        )
    if name == "hgb":
        return HistGradientBoostingRegressor(
            loss="poisson",
            learning_rate=0.05,
            max_leaf_nodes=15,
            min_samples_leaf=30,
            max_iter=300,
            random_state=42,
        )
    if name == "lightgbm":
        return LGBMRegressor(
            objective="poisson",
            learning_rate=0.05,
            num_leaves=15,
            min_child_samples=30,
            n_estimators=300,
            random_state=42,
            verbose=-1,
        )
    raise KeyError(name)


def fit_predict(name: str, x_train, y_train, w_train, x_test):
    if name == "dummy":
        baseline = float(np.average(y_train, weights=w_train))
        return np.full(len(x_test), baseline)
    model = make_model(name)
    if hasattr(model, "steps"):
        model.fit(x_train, y_train, **{f"{model.steps[-1][0]}__sample_weight": w_train})
    else:
        model.fit(x_train, y_train, sample_weight=w_train)
    return np.clip(model.predict(x_test), 1e-6, None)


def top20_hit(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if np.unique(y_pred).size < 2:
        return np.nan
    k = max(1, int(round(0.2 * len(y_true))))
    pred_top = set(np.argsort(y_pred)[-k:])
    actual_top = set(np.argsort(y_true)[-k:])
    return len(pred_top & actual_top) / k


def fold_metrics(y_true, y_pred, w_true, y_train, w_train) -> dict[str, float]:
    pred = np.clip(y_pred, 1e-6, None)
    baseline = np.full_like(pred, float(np.average(y_train, weights=w_train)))
    if np.unique(pred).size < 2:
        rho = np.nan
    else:
        rho = float(spearmanr(y_true, pred).statistic)
    return {
        "deviance": float(mean_poisson_deviance(y_true, pred, sample_weight=w_true)),
        "deviance_dummy": float(mean_poisson_deviance(y_true, baseline, sample_weight=w_true)),
        "d2": float(d2_tweedie_score(y_true, pred, power=1, sample_weight=w_true)),
        "mae": float(mean_absolute_error(y_true, pred)),
        "spearman": rho,
        "top20_hit": float(top20_hit(y_true, pred)),
    }


def splits(frame: pd.DataFrame, scheme: str):
    if scheme == "spatial_block":
        blocks = KMeans(n_clusters=25, n_init=10, random_state=42).fit_predict(
            frame[["cx", "cy"]].to_numpy()
        )
        groups = blocks
        folder = GroupKFold(n_splits=5)
        pairs = folder.split(frame, frame["complaints_per_1k"], groups)
    elif scheme == "random_kfold":
        folder = KFold(n_splits=5, shuffle=True, random_state=42)
        pairs = folder.split(frame)
    elif scheme == "borough_holdout":
        groups = frame["borough"].to_numpy()
        folder = GroupKFold(n_splits=frame["borough"].nunique())
        pairs = folder.split(frame, frame["complaints_per_1k"], groups)
    else:
        raise KeyError(scheme)
    for fold, (train, test) in enumerate(pairs):
        if scheme == "borough_holdout":
            label = str(frame.iloc[test]["borough"].iloc[0])
        else:
            label = str(fold)
        yield fold, label, train, test


def run() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    base = load_frame()
    rows = []
    oof_rows = []
    models = ["dummy", "poisson", "forest", "hgb", "lightgbm"]
    schemes = ["spatial_block", "random_kfold", "borough_holdout"]
    for drop_outlier in (False, True):
        frame = base if not drop_outlier else base.loc[base["GEOID"] != OUTLIER].reset_index(drop=True)
        for scheme in schemes:
            use_borough = scheme != "borough_holdout"
            features = design(frame, use_borough=use_borough)
            y = frame["complaints_per_1k"].to_numpy(dtype=float)
            weight = frame["total_pop"].to_numpy(dtype=float)
            for name in models:
                for fold, label, train, test in splits(frame, scheme):
                    pred = fit_predict(
                        name,
                        features.iloc[train],
                        y[train],
                        weight[train],
                        features.iloc[test],
                    )
                    metrics = fold_metrics(y[test], pred, weight[test], y[train], weight[train])
                    rows.append(
                        {
                            "model": name,
                            "scheme": scheme,
                            "drop_outlier": drop_outlier,
                            "fold": fold,
                            "test_label": label,
                            "n_test": int(len(test)),
                            **metrics,
                        }
                    )
                    if name == "lightgbm" and scheme == "spatial_block" and not drop_outlier:
                        part = frame.iloc[test][["GEOID", "borough", "complaints_per_1k"]].copy()
                        part["pred"] = pred
                        part["fold"] = fold
                        oof_rows.append(part)
                print(f"{scheme} outlier={drop_outlier} {name}")
    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby(["model", "scheme", "drop_outlier"], as_index=False)
        .agg(
            folds=("fold", "nunique"),
            n_test=("n_test", "sum"),
            deviance_mean=("deviance", "mean"),
            deviance_std=("deviance", "std"),
            d2_mean=("d2", "mean"),
            d2_std=("d2", "std"),
            mae_mean=("mae", "mean"),
            mae_std=("mae", "std"),
            spearman_mean=("spearman", "mean"),
            spearman_std=("spearman", "std"),
            top20_mean=("top20_hit", "mean"),
            top20_std=("top20_hit", "std"),
        )
    )
    detail.to_csv(TABLES / "plan05a_cv.csv", index=False)
    summary.to_csv(TABLES / "plan05a_cv_summary.csv", index=False)
    oof = pd.concat(oof_rows, ignore_index=True)
    oof.to_csv(TABLES / "plan05a_oof.csv", index=False)
    write_report(summary, detail)
    print(summary.to_string(index=False))
    print(REPORT)


def cell(summary: pd.DataFrame, model: str, scheme: str, drop: bool) -> pd.Series:
    hit = summary.loc[
        (summary["model"] == model)
        & (summary["scheme"] == scheme)
        & (summary["drop_outlier"] == drop)
    ]
    return hit.iloc[0]


def write_report(summary: pd.DataFrame, detail: pd.DataFrame) -> None:
    spatial = "spatial_block"
    kept = False
    hgb = cell(summary, "hgb", spatial, kept)
    lgb = cell(summary, "lightgbm", spatial, kept)
    boost = lgb if lgb.d2_mean >= hgb.d2_mean else hgb
    boost_name = "LightGBM" if boost.model == "lightgbm" else "HistGradientBoosting"
    other = hgb if boost.model == "lightgbm" else lgb
    other_name = "HistGradientBoosting" if other.model == "hgb" else "LightGBM"
    dummy = cell(summary, "dummy", spatial, kept)
    poisson = cell(summary, "poisson", spatial, kept)
    forest = cell(summary, "forest", spatial, kept)
    random_boost = cell(summary, boost.model, "random_kfold", kept)
    borough_boost = cell(summary, boost.model, "borough_holdout", kept)
    dropped = cell(summary, boost.model, spatial, True)
    poisson_dropped = cell(summary, "poisson", spatial, True)

    def within_spread(a: pd.Series, b: pd.Series) -> bool:
        gap = abs(float(a.d2_mean - b.d2_mean))
        return gap <= float(max(a.d2_std, b.d2_std))

    if within_spread(boost, poisson):
        model_gap = f"{boost_name}과 Poisson 회귀의 D² 차이는 폴드 표준편차 안에 있다."
    elif float(boost.d2_mean) > float(poisson.d2_mean):
        model_gap = (
            f"{boost_name}의 D²가 Poisson 회귀보다 {float(boost.d2_mean - poisson.d2_mean):.3f} 높다."
        )
    else:
        model_gap = (
            f"Poisson 회귀의 D²가 {boost_name}보다 {float(poisson.d2_mean - boost.d2_mean):.3f} 높다."
        )
    if within_spread(random_boost, boost):
        split_gap = "두 평균의 차이는 공간 블록 폴드 표준편차 안에 있다."
    elif float(random_boost.d2_mean) > float(boost.d2_mean):
        split_gap = (
            f"무작위 분할의 D²가 공간 블록보다 {float(random_boost.d2_mean - boost.d2_mean):.3f} 높다."
        )
    else:
        split_gap = (
            f"공간 블록의 D²가 무작위 분할보다 {float(boost.d2_mean - random_boost.d2_mean):.3f} 높다."
        )

    holdout = detail.loc[
        (detail["model"] == boost.model)
        & (detail["scheme"] == "borough_holdout")
        & (detail["drop_outlier"] == False)
    ].sort_values("d2")
    hardest = holdout.iloc[0]
    easiest = holdout.iloc[-1]
    lines = [
        "# Tract 민원율 예측",
        "",
        "타깃은 인구 1,000명당 민원율이다. 학습 가중치는 인구다. 설명변수는 중위소득, 임차율, 인구밀도, 빈곤율, 주택 연령, 1950년 이전 주택 비율, 자치구다. 실업률, 공실률, 제한적 영어, 학력, 중위연령은 이번 ACS 추출에 없다. 민원 건수와 유형 비율, 이웃 민원율, 좌표는 넣지 않았다.",
        "",
        "공간 블록은 투영 좌표로 나눈 25개 묶음이고, 평가는 5겹 GroupKFold다. 무작위 5겹과 자치구를 하나씩 빼는 검증을 같이 본다. 자치구를 빼는 검증에는 자치구 표시를 넣지 않았다. 지표는 인구 가중 Poisson deviance와 D², MAE, Spearman, 검증 폴드 상위 20% 적중률이다.",
        "",
        f"극단 Tract를 포함한 공간 블록에서 인구 가중 평균의 D²는 {dummy.d2_mean:.3f}, MAE는 {dummy.mae_mean:.0f}이다. 상수 예측이라 순위 상관은 없다.",
        f"Poisson 회귀의 D²는 {poisson.d2_mean:.3f} (폴드 표준편차 {poisson.d2_std:.3f}), MAE는 {poisson.mae_mean:.0f}, Spearman ρ는 {poisson.spearman_mean:.2f}, 상위 20% 적중률은 {poisson.top20_mean:.0%}다.",
        f"랜덤포레스트의 D²는 {forest.d2_mean:.3f} (표준편차 {forest.d2_std:.3f}), Spearman ρ는 {forest.spearman_mean:.2f}, 상위 20% 적중률은 {forest.top20_mean:.0%}다.",
        (
            f"{boost_name}의 D²는 {boost.d2_mean:.3f} (표준편차 {boost.d2_std:.3f}), "
            f"MAE는 {boost.mae_mean:.0f}, Spearman ρ는 {boost.spearman_mean:.2f}, "
            f"상위 20% 적중률은 {boost.top20_mean:.0%}다. "
            f"{other_name}의 D²는 {other.d2_mean:.3f}이다. "
            + model_gap
        ),
        (
            f"같은 {boost_name}을 무작위 5겹으로 보면 D²는 {random_boost.d2_mean:.3f} "
            f"(표준편차 {random_boost.d2_std:.3f})이고, 공간 블록은 {boost.d2_mean:.3f} "
            f"(표준편차 {boost.d2_std:.3f})이다. {split_gap}"
        ),
        (
            f"자치구를 하나씩 빼고 학습하면 {boost_name} D²는 {borough_boost.d2_mean:.3f} "
            f"(표준편차 {borough_boost.d2_std:.3f})이다. "
            f"가장 낮은 자치구는 {hardest.test_label} (D² {hardest.d2:.3f})이고, "
            f"가장 높은 자치구는 {easiest.test_label} (D² {easiest.d2:.3f})이다."
        ),
        (
            f"극단 Tract {OUTLIER}을 빼면 공간 블록 {boost_name} D²는 {dropped.d2_mean:.3f}, "
            f"MAE는 {dropped.mae_mean:.0f}이다. 같은 조건의 Poisson D²는 {poisson_dropped.d2_mean:.3f}이다."
        ),
        "",
        "교차검증 예측값은 `outputs/tables/plan05a_oof.csv`에 있다. 표는 `plan05a_cv.csv`와 `plan05a_cv_summary.csv`다.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
