"""계획서에 남아 있고 집계 표로 계산할 수 있는 항목을 닫는다.

원본 311 파일이 필요한 문장·일별 시계열·반복 신고·처리 시간은 만들지 않는다.
인접 권역은 발표한 민원 구성 4유형을 바꾸지 않는다.
난수 고정값: 42.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import sparse, stats
from scipy.sparse.csgraph import connected_components
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "analysis"))

import plan_02_core as core
import plan_05_rest as rest

TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
REPORT = ROOT / "reports" / "plan_06_close.md"
FINAL = ROOT / "reports" / "final_report.md"
MAP = ROOT / "data" / "processed" / "tract_dashboard.geojson"
SHARES = ["소음", "주거", "위생", "도로", "해충", "건축"]
SOURCE = {
    "소음": "소음",
    "주거": "주거환경",
    "위생": "위생",
    "도로": "도로·교통",
    "해충": "해충·동물",
    "건축": "건축·안전",
}
HEAT = {"2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-10"}
NIGHT = {22, 23, 0, 1, 2, 3, 4, 5}
WEEKEND = {6, 7}
SHORT = {
    "Bronx": "Bronx",
    "Brooklyn (Kings)": "Brooklyn",
    "Manhattan (New York)": "Manhattan",
    "Queens": "Queens",
    "Staten Island (Richmond)": "Staten Island",
}

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def save_fig(fig, path) -> None:
    for ax in fig.axes:
        if ax.get_ylabel():
            ax.set_ylabel(ax.get_ylabel(), rotation=0, ha="right", va="center", labelpad=18)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def stable_tracts() -> pd.DataFrame:
    tracts = pd.read_csv(TABLES / "plan02_tracts.csv", dtype={"GEOID": str})
    return tracts.loc[tracts["total_pop"] >= 1000].copy()


def describe(part: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "complaints_per_1k",
        "complaint_count",
        "total_pop",
        "median_income",
        "renter_rate",
        "pop_density",
        "poverty_rate",
    ]
    rows = []
    for column in columns:
        series = part[column].dropna().to_numpy(dtype=float)
        rows.append(
            {
                "subset": "pop_ge_1000",
                "column": column,
                "n": int(series.size),
                "mean": float(series.mean()),
                "std": float(series.std(ddof=1)),
                "min": float(series.min()),
                "p25": float(np.percentile(series, 25)),
                "p50": float(np.percentile(series, 50)),
                "p75": float(np.percentile(series, 75)),
                "p90": float(np.percentile(series, 90)),
                "p95": float(np.percentile(series, 95)),
                "p99": float(np.percentile(series, 99)),
                "max": float(series.max()),
                "skew": float(stats.skew(series)),
                "excess_kurtosis": float(stats.kurtosis(series)),
            }
        )
    kept = part.loc[part["GEOID"] != core.OUTLIER, "complaints_per_1k"].dropna().to_numpy(dtype=float)
    rows.append(
        {
            "subset": "drop_outlier",
            "column": "complaints_per_1k",
            "n": int(kept.size),
            "mean": float(kept.mean()),
            "std": float(kept.std(ddof=1)),
            "min": float(kept.min()),
            "p25": float(np.percentile(kept, 25)),
            "p50": float(np.percentile(kept, 50)),
            "p75": float(np.percentile(kept, 75)),
            "p90": float(np.percentile(kept, 90)),
            "p95": float(np.percentile(kept, 95)),
            "p99": float(np.percentile(kept, 99)),
            "max": float(kept.max()),
            "skew": float(stats.skew(kept)),
            "excess_kurtosis": float(stats.kurtosis(kept)),
        }
    )
    return pd.DataFrame(rows)


def draw_distribution(part: pd.DataFrame) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    rate = part["complaints_per_1k"].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.hist(np.log10(rate), bins=40, color="#3d5a80")
    ax.set_xlabel("log10(1,000명당 민원)")
    ax.set_ylabel("Tract 수")
    ax.set_title("인구 1,000명 이상 Tract")
    save_fig(fig, FIGURES / "plan06_log_hist.png")

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for borough, group in part.groupby("borough"):
        values = np.sort(group["complaints_per_1k"].to_numpy(dtype=float))
        y = np.arange(1, len(values) + 1) / len(values)
        ax.plot(values, y, label=SHORT.get(borough, borough))
    ax.set_xlim(0, 1500)
    ax.set_xlabel("1,000명당 민원")
    ax.set_ylabel("누적 비율")
    ax.set_title("자치구별 민원율 ECDF")
    ax.legend(frameon=False)
    save_fig(fig, FIGURES / "plan06_ecdf.png")


def time_notes(part: pd.DataFrame) -> dict[str, float]:
    month = pd.read_csv(TABLES / "plan02_monthly.csv")
    heat = month["label"].isin(HEAT)
    housing = float(month.loc[heat, "housing"].sum() / month["housing"].sum())
    noise_month = float(month.loc[heat, "noise"].sum() / month["noise"].sum())
    noise = pd.read_csv(TABLES / "plan02_noise_dow_hour.csv")
    total = float(noise["noise"].sum())
    night = float(noise.loc[noise["created_hour"].isin(NIGHT), "noise"].sum() / total)
    weekend = float(noise.loc[noise["created_dow"].isin(WEEKEND), "noise"].sum() / total)
    count_pop = stats.spearmanr(part["complaint_count"], part["total_pop"])
    rate_pop = stats.spearmanr(part["complaints_per_1k"], part["total_pop"])
    weighted = float(part["complaint_count"].sum() / part["total_pop"].sum() * 1000)
    plain = float(part["complaints_per_1k"].mean())
    return {
        "housing_heat_share": housing,
        "noise_heat_share": noise_month,
        "noise_night_share": night,
        "noise_weekend_share": weekend,
        "count_pop_rho": float(count_pop.statistic),
        "rate_pop_rho": float(rate_pop.statistic),
        "weighted_rate": weighted,
        "plain_mean_rate": plain,
    }


def ale_curve(model, features: pd.DataFrame, column: str, bins: int = 10) -> pd.DataFrame:
    values = features[column].to_numpy(dtype=float)
    valid = np.flatnonzero(np.isfinite(values))
    order = valid[np.argsort(values[valid])]
    buckets = np.array_split(order, bins)
    centers = []
    deltas = []
    for bucket in buckets:
        if len(bucket) < 20:
            continue
        left = features.iloc[bucket].copy()
        right = left.copy()
        lo = float(values[bucket[0]])
        hi = float(values[bucket[-1]])
        if hi <= lo:
            continue
        left[column] = lo
        right[column] = hi
        deltas.append(float(np.mean(model.predict(right) - model.predict(left))))
        centers.append((lo + hi) / 2)
    accumulated = np.cumsum(deltas)
    accumulated = accumulated - accumulated.mean()
    return pd.DataFrame({"term": column, "value": centers, "ale": accumulated})


def draw_ale(frame: pd.DataFrame) -> None:
    labels = {
        "renter_rate": "임차율",
        "median_income": "중위소득",
        "pop_density": "인구밀도",
        "poverty_rate": "빈곤율",
    }
    fig, axes = plt.subplots(2, 2, figsize=(9.2, 6.2))
    for ax, term in zip(axes.ravel(), labels):
        curve = frame.loc[frame["term"] == term]
        ax.plot(curve["value"], curve["ale"], color="#9b2226", marker="o", ms=3)
        ax.axhline(0, color="#222", lw=0.6)
        ax.set_title(labels[term])
        ax.set_ylabel("누적 국소효과")
    fig.suptitle("ALE: 이웃 구간의 예측 차이를 누적")
    save_fig(fig, FIGURES / "plan06_ale.png")


def draw_dependence(features: pd.DataFrame, contrib: np.ndarray) -> None:
    renter_at = list(features.columns).index("renter_rate")
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    points = ax.scatter(
        features["renter_rate"],
        contrib[:, renter_at],
        c=features["median_income"],
        s=10,
        cmap="viridis",
        alpha=0.7,
        linewidths=0,
    )
    fig.colorbar(points, ax=ax, label="중위소득")
    ax.set_xlabel("임차율")
    ax.set_ylabel("임차율 기여 (로그 민원율)")
    ax.set_title("임차율 기여와 소득")
    save_fig(fig, FIGURES / "plan06_shap_renter.png")


def queen_binary(geoids: pd.Series) -> sparse.csr_matrix:
    from scipy.spatial import cKDTree

    geo = gpd_read(geoids)
    pairs = __import__("geopandas").sjoin(geo, geo, predicate="touches", how="inner")
    pairs = pairs.loc[pairs["GEOID_left"] != pairs["GEOID_right"], ["GEOID_left", "GEOID_right"]]
    index = {geoid: i for i, geoid in enumerate(geo["GEOID"])}
    rows = pairs["GEOID_left"].map(index).to_numpy()
    cols = pairs["GEOID_right"].map(index).to_numpy()
    binary = sparse.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(geo), len(geo))).tocsr()
    binary.data[:] = 1
    binary = binary.tolil()
    degree = np.asarray(binary.sum(axis=1)).ravel()
    xy = np.column_stack([geo.geometry.to_crs(2263).centroid.x, geo.geometry.to_crs(2263).centroid.y])
    neighbors = cKDTree(xy).query(xy, k=5)[1]
    for i in np.flatnonzero(degree == 0):
        for j in neighbors[i, 1:]:
            binary[i, j] = 1
            binary[j, i] = 1
    return binary.tocsr(), geo["GEOID"].tolist()


def gpd_read(geoids: pd.Series):
    import geopandas as gpd

    geo = gpd.read_file(core.TRACT_GEO)[["GEOID", "geometry"]]
    geo["GEOID"] = geo["GEOID"].astype(str)
    order = geoids.astype(str).tolist()
    geo = geo.set_index("GEOID").loc[order].reset_index()
    return geo


def cluster_borough(part: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    shares = np.column_stack(
        [(part[SOURCE[name]] / part["complaint_count"]).to_numpy(dtype=float) for name in SHARES]
    )
    scaled = __import__("sklearn.preprocessing", fromlist=["StandardScaler"]).StandardScaler().fit_transform(
        np.column_stack([shares, np.log1p(part["complaints_per_1k"].to_numpy(dtype=float))])
    )
    binary, ordered = queen_binary(part["GEOID"])
    lookup = {geoid: i for i, geoid in enumerate(part["GEOID"].astype(str))}
    permutation = np.array([lookup[geoid] for geoid in ordered])
    part = part.iloc[permutation].reset_index(drop=True)
    scaled = scaled[permutation]
    _count, membership = connected_components(binary, directed=False)
    labels = np.full(len(part), -1, dtype=int)
    next_label = 0
    chosen = []
    for component in range(int(membership.max()) + 1):
        idx = np.flatnonzero(membership == component)
        local = binary[idx][:, idx]
        k = 1
        score = np.nan
        if len(idx) >= 80:
            best_k, best_s = 2, -1.0
            for candidate in range(2, 5):
                trial = AgglomerativeClustering(
                    n_clusters=candidate, linkage="ward", connectivity=local
                ).fit_predict(scaled[idx])
                value = float(silhouette_score(scaled[idx], trial))
                if value > best_s:
                    best_k, best_s = candidate, value
            k, score = best_k, best_s
            labels[idx] = next_label + AgglomerativeClustering(
                n_clusters=k, linkage="ward", connectivity=local
            ).fit_predict(scaled[idx])
        else:
            labels[idx] = next_label
        chosen.append(
            {
                "borough": part["borough"].iloc[0],
                "tracts": int(len(idx)),
                "k": k,
                "silhouette": score,
            }
        )
        next_label += k
    part = part.copy()
    part["region_id"] = labels
    return part, chosen


def regions(part: pd.DataFrame) -> tuple[pd.DataFrame, int, pd.DataFrame]:
    pieces = []
    chosen = []
    offset = 0
    for _borough, group in part.groupby("borough"):
        labeled, fit_rows = cluster_borough(group.copy())
        labeled["region_id"] = labeled["region_id"] + offset
        offset = int(labeled["region_id"].max()) + 1
        pieces.append(labeled)
        chosen.extend(fit_rows)
    part = pd.concat(pieces, ignore_index=True)
    for column, source in SOURCE.items():
        part[column] = part[source] / part["complaint_count"]
    assigned = pd.read_csv(TABLES / "plan05c_assign.csv", dtype={"GEOID": str})
    part = part.merge(assigned, on="GEOID", how="left")
    names = {}
    used = set()
    for region, group in part.groupby("region_id"):
        excess = group[SHARES].median() - part[SHARES].median()
        lead = excess.idxmax()
        name = f"{lead} 중심" if float(excess[lead]) >= 0.03 else "혼합"
        borough = SHORT.get(group["borough"].mode().iloc[0], group["borough"].mode().iloc[0])
        label = f"{borough} {name}"
        if label in used:
            label = f"{label} {int(region)}"
        used.add(label)
        names[region] = label
    part["region_name"] = part["region_id"].map(names)
    profile = (
        part.groupby("region_name", as_index=False)
        .agg(
            tracts=("GEOID", "size"),
            borough=("borough", lambda s: SHORT.get(s.mode().iloc[0], s.mode().iloc[0])),
            rate_median=("complaints_per_1k", "median"),
            **{column: (column, "median") for column in SHARES},
        )
        .sort_values(["borough", "tracts"], ascending=[True, False])
    )
    profile.to_csv(TABLES / "plan06_regions.csv", index=False)
    pd.DataFrame(chosen).to_csv(TABLES / "plan06_region_fit.csv", index=False)
    pd.crosstab(part["region_name"], part["complaint_type"]).to_csv(TABLES / "plan06_region_cross.csv")
    return part[["GEOID", "region_name"]], int(part["borough"].nunique()), profile


def attach_regions(assigned: pd.DataFrame) -> None:
    import geopandas as gpd

    geo = gpd.read_file(MAP)
    geo["GEOID"] = geo["GEOID"].astype(str)
    if "region_name" in geo.columns:
        geo = geo.drop(columns=["region_name"])
    geo = geo.merge(assigned, on="GEOID", how="left")
    geo.to_file(MAP, driver="GeoJSON")


def write_report(notes: dict[str, float], described: pd.DataFrame, ale: pd.DataFrame, n_components: int, profile: pd.DataFrame) -> None:
    rate = described.loc[
        (described["subset"] == "pop_ge_1000") & (described["column"] == "complaints_per_1k")
    ].iloc[0]
    dropped = described.loc[described["subset"] == "drop_outlier"].iloc[0]
    ale_bits = []
    for term, label in (
        ("renter_rate", "임차율"),
        ("median_income", "중위소득"),
        ("pop_density", "인구밀도"),
        ("poverty_rate", "빈곤율"),
    ):
        curve = ale.loc[ale["term"] == term, "ale"]
        values = curve.to_numpy(dtype=float)
        delta = float(values[-1] - values[0])
        if int(np.argmax(values)) not in (0, len(values) - 1) and float(values.max()) > float(values[-1]) + 30:
            ale_bits.append(f"{label}은 끝보다 중간이 높고 끝점 차이는 {delta:+.0f}")
        else:
            ale_bits.append(f"{label} 끝점 차이 {delta:+.0f}")
    lines = [
        "# 남은 집계 분석",
        "",
        f"인구 1,000명 이상 Tract의 민원율은 평균 {rate['mean']:.0f}, 중앙값 {rate['p50']:.0f}, "
        f"90·95·99백분위 {rate['p90']:.0f}·{rate['p95']:.0f}·{rate['p99']:.0f}, 최댓값 {rate['max']:.0f}이다. "
        f"왜도는 {rate['skew']:.1f}, 초과 첨도는 {rate['excess_kurtosis']:.0f}이다. "
        f"극단 Tract를 빼면 왜도는 {dropped['skew']:.1f}, 최댓값은 {dropped['max']:.0f}이다.",
        "",
        f"같은 표본에서 민원 건수와 인구의 Spearman ρ는 {notes['count_pop_rho']:.2f}이고, "
        f"민원율과 인구의 ρ는 {notes['rate_pop_rho']:.2f}이다. "
        f"인구 가중 민원율은 {notes['weighted_rate']:.0f}이고 Tract 민원율의 단순 평균은 {notes['plain_mean_rate']:.0f}이다.",
        "",
        f"주거 민원 가운데 난방 시즌(10월–5월)에 해당하는 달은 {notes['housing_heat_share']:.0%}다. "
        f"소음은 {notes['noise_heat_share']:.0%}다. 이 패턴은 한 해의 관측이다.",
        f"소음 민원 가운데 22시–5시는 {notes['noise_night_share']:.0%}이고, 토·일은 {notes['noise_weekend_share']:.0%}다. "
        "요일 번호는 1이 월요일이고 7이 일요일이다.",
        "",
        "누적 국소효과에서 " + ", ".join(ale_bits) + "이다. "
        "소득과 빈곤처럼 같이 움직이는 변수에서 부분의존이 비현실적 조합을 만들 수 있어, 구간 안에서만 값을 바꿨다. "
        "임차율 기여 산점도의 색은 중위소득이다.",
        "",
        f"인접 권역은 자치구 {n_components}곳 안에서만 만들었다. 자치구가 맞닿아 있어도 경계를 넘기지 않았다. "
        f"Tract가 80개 이상인 덩어리만 실루엣이 가장 높은 2–4개로 나눴다. 발표한 민원 구성 4유형은 바꾸지 않았다. "
        f"권역은 {len(profile)}개다.",
        "",
        "원본 311 파일이 없어 처리하지 않은 항목은 민원 문장 주제, 고유 조합 검수, 반복 신고 비율, "
        "처리 소요시간, 일별 급증, 좌표 밀집, 주택 위반·쥐 점검 대조다. "
        "ACS 오차한계 열이 없어 변동계수 30% 기준의 포함·제외도 하지 않았다. "
        "UMAP와 spopt 권역화는 설치하지 않았고, 인접 제약은 scikit-learn 계층 군집으로 대신했다.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    marker = "\n## 마감\n"
    body = FINAL.read_text(encoding="utf-8")
    if marker in body:
        body = body.split(marker)[0].rstrip() + "\n"
    FINAL.write_text(body + marker + "\n".join(lines[2:]), encoding="utf-8")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    part = stable_tracts()
    described = describe(part)
    described.to_csv(TABLES / "plan06_describe.csv", index=False)
    draw_distribution(part)
    notes = time_notes(part)
    pd.DataFrame([notes]).to_csv(TABLES / "plan06_highlights.csv", index=False)
    print("model, ALE, dependence...")
    frame = rest.ml.load_frame()
    features, _y, _w, model = rest.fit_model(frame)
    ale = pd.concat(
        [ale_curve(model, features, column) for column in ("renter_rate", "median_income", "pop_density", "poverty_rate")],
        ignore_index=True,
    )
    ale.to_csv(TABLES / "plan06_ale.csv", index=False)
    draw_ale(ale)
    draw_dependence(features, model.predict(features, pred_contrib=True))
    print("contiguous regions...")
    assigned, n_components, profile = regions(part.loc[part["complaint_count"] > 0].copy())
    attach_regions(assigned)
    write_report(notes, described, ale, n_components, profile)
    print(pd.DataFrame([notes]).T.to_string(header=False))
    print("components", n_components, "regions", len(profile))
    print(REPORT)


if __name__ == "__main__":
    main()
