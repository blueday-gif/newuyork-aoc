"""장기 재현(2010~2025) 그림: 소득 4분위별 7월 소음 민원(인구 10만 명당). ramphal_long.py의 결과 CSV를 읽는다."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "ramphal_long"
QL = ["Q1(저소득)", "Q2", "Q3", "Q4(고소득)"]
COLORS = {"Q1(저소득)": "#0d366b", "Q2": "#1c5cab", "Q3": "#3987e5", "Q4(고소득)": "#86b6ef"}
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"


def main():
    y = pd.read_csv(OUT / "03_july_by_year_main.csv", header=[0, 1], index_col=0)["7월 10만 명당"]
    plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 11,
                         "figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID,
                         "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED})
    fig, ax = plt.subplots(figsize=(11, 5.6))
    years = y.index.astype(int)
    ax.axvspan(2013.5, 2014.5, color="#f0efec", zorder=0)
    ax.text(2014, 20, "2014 자료 체계 변화", ha="center", va="bottom", color=MUTED, fontsize=9)
    ax.axvspan(2019.5, 2020.5, color="#fbe9e0", zorder=0)
    for q in QL:
        ax.plot(years, y[q].values, color=COLORS[q], lw=2.2, marker="o", ms=4, label=q, zorder=3)
        ax.annotate(f"{y[q].iloc[-1]:,.0f}", (years[-1], y[q].iloc[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK)
    ax.set_xticks(years, [str(v) for v in years], rotation=0, fontsize=9)
    ax.set_ylim(0, 1800)
    ax.set_ylabel("7월 소음 민원, 인구 10만 명당")
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=4, loc="upper left", fontsize=10, title="Tract 중위소득 4분위", title_fontsize=9)
    ax.set_title("7월 소음 민원, 소득 4분위별(2010~2026.10)", loc="left", color=INK, fontsize=15, fontweight="bold", pad=12)
    fig.text(0.01, 0.01, "2010~2019와 2020~2026은 다른 공개 자료다. 655·672 이상치 주소 제외. 인구는 2015~2019 ACS 고정.",
             color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "chart3_july_2010_2026.png", dpi=160)


if __name__ == "__main__":
    main()
