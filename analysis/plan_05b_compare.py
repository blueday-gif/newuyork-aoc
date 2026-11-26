"""회귀 계수와 LightGBM 기여·부분의존을 같은 변수에서 비교한다."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def save_fig(fig, path) -> None:
    for ax in fig.axes:
        if ax.get_ylabel():
            ax.set_ylabel(ax.get_ylabel(), rotation=0, ha="right", va="center", labelpad=18)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)

FOCUS = [
    ("renter_rate", "임차율", "renter_rate", 0.1, "10%p"),
    ("median_income", "중위소득", "income_10k", 1.0, "1만 달러"),
    ("pop_density", "인구밀도", "density_10k", 0.1, "1,000명/km²"),
    ("poverty_rate", "빈곤율", "poverty_rate", 0.1, "10%p"),
    ("pre1950_share", "1950년 이전 주택", None, None, None),
    ("housing_age", "주택 연령", None, None, None),
]


def direction(value: float) -> str:
    if value > 0:
        return "양"
    if value < 0:
        return "음"
    return "0"


def pdp_shape(curve: pd.DataFrame) -> str:
    y = curve["mean_prediction"].to_numpy(dtype=float)
    start, end = float(y[0]), float(y[-1])
    span = float(y.max() - y.min())
    if span < 25:
        return "거의 평평"
    body = y[:-2]
    if end > start + 30 and float(body.max() - body.min()) < 40 and end > float(body.max()) + 30:
        return "중간은 거의 평평하고 상위 값에서 오른다"
    if end > start + 25 and int(np.argmax(y)) not in (0, len(y) - 1) and end < float(y.max()) - 20:
        return "낮은 쪽에서 오르고, 높은 쪽에서는 조금 내려간다"
    if end > start + 25:
        return "값이 커질수록 예측이 높다"
    if end < start - 25 and y[0] > float(y[1:].max()) + 20:
        if int(np.argmin(y)) not in (0, len(y) - 1) and float(y[-1] - y.min()) > 30:
            return "낮은 구간에서 높고, 중간에서 낮아진 뒤 조금 오른다"
        if float(np.ptp(y[2:])) < 50:
            return "가장 낮은 구간에서 예측이 높고 이후에는 완만하다"
    if (
        end < start - 25
        and int(np.argmax(y)) not in (0, len(y) - 1)
        and end < float(y.max()) - 20
    ):
        return "중간에 한 번 높아진 뒤 끝에서 낮아진다"
    if end < start - 25:
        return "값이 커질수록 예측이 낮다"
    return "끝점 차이는 작고 중간이 오르내린다"


def compare() -> pd.DataFrame:
    shap = pd.read_csv(TABLES / "plan05b_shap.csv").set_index("term")
    pdp = pd.read_csv(TABLES / "plan05b_pdp.csv")
    ols = pd.read_csv(TABLES / "plan02_ols.csv")
    ols = ols.loc[ols["model"] == "full_borough"].set_index("term")
    rows = []
    for key, label, ols_term, scale, unit in FOCUS:
        curve = pdp.loc[pdp["term"] == key].sort_values("value")
        shap_gap = float(shap.loc[key, "high_minus_low"])
        start = float(curve["mean_prediction"].iloc[0])
        end = float(curve["mean_prediction"].iloc[-1])
        shape = pdp_shape(curve)
        if ols_term is None:
            if direction(shap_gap) != direction(end - start) and abs(end - start) > 20:
                verdict = "기여와 부분의존 끝점의 부호가 다르다"
            else:
                verdict = "선형 주 모형에 없는 변수"
            rows.append(
                {
                    "변수": label,
                    "회귀": "주 모형에 없음",
                    "SHAP": direction(shap_gap),
                    "SHAP_높은쪽차이": shap_gap,
                    "PDP_시작": start,
                    "PDP_끝": end,
                    "PDP_형태": shape,
                    "방향": verdict,
                }
            )
            continue
        coef = float(ols.loc[ols_term, "coef"]) * scale
        low = float(ols.loc[ols_term, "ci_low"]) * scale
        high = float(ols.loc[ols_term, "ci_high"]) * scale
        crosses = low < 0 < high
        same = direction(coef) == direction(shap_gap) == direction(end - start)
        if crosses:
            verdict = "회귀 신뢰구간이 0을 포함한다"
        elif same:
            verdict = "같다"
        elif direction(coef) == direction(shap_gap):
            verdict = "회귀와 기여의 부호는 같다"
        else:
            verdict = "부호가 다르다"
        rows.append(
            {
                "변수": label,
                "회귀": f"{coef:+.1f}건/{unit}",
                "SHAP": direction(shap_gap),
                "SHAP_높은쪽차이": shap_gap,
                "PDP_시작": start,
                "PDP_끝": end,
                "PDP_형태": shape,
                "방향": verdict,
            }
        )
    return pd.DataFrame(rows)


def draw(frame: pd.DataFrame) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    shap = pd.read_csv(TABLES / "plan05b_shap.csv")
    names = {key: label for key, label, *_ in FOCUS}
    shap["label"] = shap["term"].map(names).fillna(shap["term"])
    shap = shap.sort_values("mean_abs")
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(shap["label"], shap["mean_abs"], color="#3d5a80")
    ax.set_xlabel("평균 절대 기여 (로그 민원율)")
    ax.set_title("LightGBM 변수 기여")
    save_fig(fig, FIGURES / "plan05b_shap.png")

    pdp = pd.read_csv(TABLES / "plan05b_pdp.csv")
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 6.2))
    for ax, (key, label, *_) in zip(axes.ravel(), FOCUS):
        curve = pdp.loc[pdp["term"] == key].sort_values("value")
        ax.plot(curve["value"], curve["mean_prediction"], color="#9b2226", marker="o", ms=3)
        ax.set_title(label)
        ax.set_ylabel("예측 민원율")
    fig.suptitle("부분의존: 다른 변수는 관측값 그대로")
    save_fig(fig, FIGURES / "plan05b_pdp.png")

    outlier = pd.read_csv(TABLES / "plan05b_outlier_shap.csv")
    outlier["label"] = outlier["term"].map(names).fillna(outlier["term"])
    outlier = outlier.sort_values("shap")
    colors = np.where(outlier["shap"] >= 0, "#9b2226", "#1d3557")
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(outlier["label"], outlier["shap"], color=colors)
    ax.axvline(0, color="#222", lw=0.6)
    ax.set_xlabel("로그 민원율 기여")
    ax.set_title("36005042000 예측 분해")
    save_fig(fig, FIGURES / "plan05b_outlier_shap.png")


def main() -> None:
    frame = compare()
    frame.to_csv(TABLES / "plan05b_compare.csv", index=False)
    draw(frame)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
