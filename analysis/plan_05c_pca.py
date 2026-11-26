"""민원 구성의 가우시안 혼합 BIC와 주성분 산점도를 만든다.

군집 이름은 실루엣으로 정한 4개를 유지한다. BIC가 다른 개수를 가리켜도 이름을 바꾸지 않는다.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
SHARES = ["소음", "주거", "위생", "도로", "해충", "건축"]
SOURCE = {
    "소음": "소음",
    "주거": "주거환경",
    "위생": "위생",
    "도로": "도로·교통",
    "해충": "해충·동물",
    "건축": "건축·안전",
}
COLORS = {
    "도로 중심": "#bc6c25",
    "주거 중심": "#9b2226",
    "혼합": "#457b9d",
    "소음 중심": "#2a9d8f",
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


def matrix(frame: pd.DataFrame) -> np.ndarray:
    shares = np.column_stack(
        [(frame[SOURCE[name]] / frame["complaint_count"]).to_numpy(dtype=float) for name in SHARES]
    )
    rate = np.log1p(frame["complaints_per_1k"].to_numpy(dtype=float))
    return StandardScaler().fit_transform(np.column_stack([shares, rate]))


def align(pca: PCA) -> PCA:
    saved = pd.read_csv(TABLES / "plan05c_pca.csv").set_index("term")
    fitted = pd.DataFrame(pca.components_.T, index=SHARES + ["log_rate"], columns=["axis_1", "axis_2"])
    for axis, row in (("axis_1", 0), ("axis_2", 1)):
        if float(np.dot(fitted[axis], saved[axis])) < 0:
            pca.components_[row] *= -1
    return pca


def main() -> None:
    tracts = pd.read_csv(TABLES / "plan02_tracts.csv", dtype={"GEOID": str})
    part = tracts.loc[(tracts["total_pop"] >= 1000) & (tracts["complaint_count"] > 0)].copy()
    assigned = pd.read_csv(TABLES / "plan05c_assign.csv", dtype={"GEOID": str})
    part = part.merge(assigned, on="GEOID", how="inner")
    scaled = matrix(part)
    silhouette = pd.read_csv(TABLES / "plan05c_silhouette.csv")
    rows = []
    for k in range(3, 13):
        mixture = GaussianMixture(n_components=k, n_init=5, random_state=42).fit(scaled)
        rows.append({"k": k, "bic": float(mixture.bic(scaled))})
    bic = pd.DataFrame(rows).merge(silhouette, on="k", how="left")
    bic.to_csv(TABLES / "plan05c_bic.csv", index=False)

    pca = align(PCA(n_components=2, random_state=42).fit(scaled))
    scores = pca.transform(scaled)
    out = pd.DataFrame(
        {
            "GEOID": part["GEOID"].to_numpy(),
            "complaint_type": part["complaint_type"].to_numpy(),
            "axis_1": scores[:, 0],
            "axis_2": scores[:, 1],
        }
    )
    out.to_csv(TABLES / "plan05c_pca_scores.csv", index=False)
    draw(out, pca)
    best = bic.loc[bic["bic"].idxmin()]
    print(bic.to_string(index=False))
    print("bic_min_k", int(best.k), "explained", pca.explained_variance_ratio_.round(4))
    print(out.groupby("complaint_type")[["axis_1", "axis_2"]].median().round(2))


def draw(scores: pd.DataFrame, pca: PCA) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.8))
    for name, group in scores.groupby("complaint_type"):
        axes[0].scatter(
            group["axis_1"],
            group["axis_2"],
            s=8,
            alpha=0.55,
            c=COLORS.get(name, "#666"),
            label=name,
            linewidths=0,
        )
    axes[0].set_xlabel(f"축 1 ({pca.explained_variance_ratio_[0]:.0%})")
    axes[0].set_ylabel(f"축 2 ({pca.explained_variance_ratio_[1]:.0%})")
    axes[0].set_title("민원 구성 주성분")
    axes[0].legend(markerscale=2, frameon=False)

    loadings = pd.DataFrame(pca.components_.T, index=SHARES + ["민원율"], columns=["축 1", "축 2"])
    y = np.arange(len(loadings))
    axes[1].barh(y - 0.18, loadings["축 1"], height=0.36, color="#9b2226", label="축 1")
    axes[1].barh(y + 0.18, loadings["축 2"], height=0.36, color="#1d3557", label="축 2")
    axes[1].axvline(0, color="#222", lw=0.6)
    axes[1].set_yticks(y, loadings.index)
    axes[1].set_title("변수 적재값")
    axes[1].legend(frameon=False)
    save_fig(fig, FIGURES / "plan05c_pca.png")


if __name__ == "__main__":
    main()
