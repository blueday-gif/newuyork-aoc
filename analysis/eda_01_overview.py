"""Tract 결합 데이터의 개요와 기초 EDA.

분석 단위는 Census Tract다. 인구 1,000명 미만 Tract는 분포 설명에는 포함하고,
변수 간 순위 상관과 5분위 비교에서는 뺀다. 인구가 너무 적으면 1,000명당 민원 수가
몇 건의 민원만으로도 크게 흔들리기 때문이다.

실행 (프로젝트 루트):
    py -3 analysis/eda_01_overview.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
REPORT = ROOT / "reports" / "eda_01_overview.md"
REQUESTS = Path(r"D:\project-ny311\data\processed\311_requests_clean.parquet")

POP_MIN = 1000
ACS_VARS = [
    "total_pop",
    "median_income",
    "total_housing",
    "owner_occupied",
    "renter_occupied",
    "race_total",
    "white_nh",
    "black_nh",
    "asian_nh",
    "hispanic",
    "lang_total",
    "renter_rate",
    "hispanic_rate",
    "black_rate",
    "white_rate",
    "asian_rate",
    "owner_rate",
]
RATE_VARS = [
    ("median_income", "가구 중위소득 ($)"),
    ("renter_rate", "임차 가구 비율"),
    ("hispanic_rate", "히스패닉 비율"),
    ("black_rate", "비히스패닉 흑인 비율"),
    ("white_rate", "비히스패닉 백인 비율"),
    ("asian_rate", "비히스패닉 아시아인 비율"),
    ("total_pop", "Tract 인구"),
]


def fmt_int(value: float) -> str:
    return f"{int(round(value)):,}"


def fmt_num(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return ""
    return f"{value:,.{digits}f}"


def save_table(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(TABLES / name, index=False, encoding="utf-8-sig")


def request_coverage() -> dict[str, int]:
    requests = pq.ParquetFile(REQUESTS)
    lat = pq.read_table(REQUESTS, columns=["latitude"]).column("latitude")
    missing_xy = int(pc.sum(pc.is_null(lat)).as_py())
    joined = pq.ParquetFile(PROCESSED / "nyc311_point_geoid.parquet").metadata.num_rows
    total = requests.metadata.num_rows
    return {
        "rows": total,
        "missing_xy": missing_xy,
        "with_xy": total - missing_xy,
        "in_tract": joined,
        "outside_tract": total - missing_xy - joined,
    }


def load_tracts() -> pd.DataFrame:
    acs = pd.read_csv(
        PROCESSED / "nyc_acs_2024_5yr.csv",
        dtype={"GEOID": str, "state": str, "county": str, "tract": str},
    )
    complaints = pd.read_csv(
        PROCESSED / "nyc311_tract_complaints.csv",
        dtype={"GEOID": str},
    )
    keep = ["GEOID", "complaint_count", "complaints_per_1k"]
    merged = acs.merge(complaints[keep], on="GEOID", how="left", validate="one_to_one")
    if merged["complaint_count"].isna().any():
        raise RuntimeError("ACS Tract 중 민원 집계와 연결되지 않은 행이 있습니다.")
    merged["stable"] = merged["total_pop"] >= POP_MIN
    return merged


def missing_table(tracts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    n = len(tracts)
    for col in ACS_VARS:
        missing = int(tracts[col].isna().sum())
        rows.append(
            {
                "column": col,
                "missing": missing,
                "missing_pct": missing / n * 100,
                "nonmissing": n - missing,
            }
        )
    return pd.DataFrame(rows)


def borough_table(tracts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for borough, part in tracts.groupby("borough", sort=True):
        pop = part["total_pop"].sum(min_count=1)
        complaints = part["complaint_count"].sum()
        stable = part.loc[part["stable"]]
        rows.append(
            {
                "borough": borough,
                "tracts": len(part),
                "stable_tracts": int(part["stable"].sum()),
                "total_pop": pop,
                "complaint_count": complaints,
                "complaints_per_1k": complaints / pop * 1000 if pop and pop > 0 else pd.NA,
                "median_tract_rate_pop1k": stable["complaints_per_1k"].median(),
                "median_income": part["median_income"].median(),
                "renter_rate": part["renter_occupied"].sum(min_count=1)
                / part["total_housing"].sum(min_count=1),
            }
        )
    out = pd.DataFrame(rows).sort_values("complaints_per_1k", ascending=False)
    return out


def numeric_profile(tracts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, part in (("all_tracts", tracts), (f"pop_ge_{POP_MIN}", tracts.loc[tracts["stable"]])):
        for col in ["total_pop", "median_income", "renter_rate", "complaints_per_1k", "complaint_count"]:
            series = part[col].dropna()
            rows.append(
                {
                    "subset": label,
                    "column": col,
                    "n": int(series.shape[0]),
                    "min": series.min(),
                    "p25": series.quantile(0.25),
                    "median": series.median(),
                    "p75": series.quantile(0.75),
                    "max": series.max(),
                    "mean": series.mean(),
                }
            )
    return pd.DataFrame(rows)


def spearman_table(stable: pd.DataFrame) -> pd.DataFrame:
    rows = []
    y = stable["complaints_per_1k"]
    for col, label in RATE_VARS:
        pair = stable[[col]].copy()
        pair["complaints_per_1k"] = y
        pair = pair.dropna()
        rho, pvalue = stats.spearmanr(pair[col], pair["complaints_per_1k"])
        rows.append(
            {
                "variable": col,
                "label": label,
                "n": len(pair),
                "spearman_rho": rho,
                "p_value": pvalue,
            }
        )
    return pd.DataFrame(rows).sort_values("spearman_rho")


def quintile_table(stable: pd.DataFrame, column: str) -> pd.DataFrame:
    part = stable.dropna(subset=[column, "complaints_per_1k"]).copy()
    part["quintile"] = pd.qcut(part[column], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
    rows = []
    for quintile, group in part.groupby("quintile", observed=True):
        rows.append(
            {
                "variable": column,
                "quintile": str(quintile),
                "tracts": len(group),
                "variable_min": group[column].min(),
                "variable_max": group[column].max(),
                "median_complaints_per_1k": group["complaints_per_1k"].median(),
                "complaint_count": int(group["complaint_count"].sum()),
                "total_pop": group["total_pop"].sum(),
            }
        )
    out = pd.DataFrame(rows)
    out["pop_weighted_per_1k"] = out["complaint_count"] / out["total_pop"] * 1000
    return out


def style_plots() -> None:
    plt.rcParams.update(
        {
            "font.family": "Malgun Gothic",
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def save_fig(fig: plt.Figure, path) -> None:
    for ax in fig.axes:
        if ax.get_ylabel():
            ax.set_ylabel(ax.get_ylabel(), rotation=0, ha="right", va="center", labelpad=18)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def draw_figures(boroughs: pd.DataFrame, stable: pd.DataFrame) -> None:
    style_plots()
    order = boroughs.sort_values("complaints_per_1k")
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.barh(order["borough"], order["complaints_per_1k"], color="#3d5a80")
    ax.set_xlabel("인구 1,000명당 민원 수")
    ax.set_ylabel("자치구")
    ax.set_title("자치구별 311 접수율 (인구 가중, 2025-11 ~ 2026-10)")
    save_fig(fig, FIGURES / "eda01_borough_rate.png")

    fig, ax = plt.subplots(figsize=(8, 4.2))
    cap = stable["complaints_per_1k"].quantile(0.99)
    shown = stable.loc[stable["complaints_per_1k"] <= cap, "complaints_per_1k"]
    ax.hist(shown, bins=30, color="#3d5a80", edgecolor="white")
    ax.axvline(stable["complaints_per_1k"].median(), color="#c44536", linewidth=1.4, label="중앙값")
    ax.set_xlabel("Tract 인구 1,000명당 민원 수")
    ax.set_ylabel("Tract 수")
    ax.set_title(f"Tract 접수율 분포 (인구 {POP_MIN:,}명 이상, 상위 1% 구간은 그림에서 제외)")
    ax.legend()
    save_fig(fig, FIGURES / "eda01_rate_hist.png")

    income = stable.dropna(subset=["median_income"])
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.scatter(
        income["median_income"] / 1000,
        income["complaints_per_1k"],
        s=12,
        alpha=0.35,
        color="#3d5a80",
        linewidths=0,
    )
    ax.set_xlabel("가구 중위소득 (천 달러)")
    ax.set_ylabel("인구 1,000명당 민원 수")
    ax.set_title(f"중위소득과 Tract 접수율 (인구 {POP_MIN:,}명 이상)")
    save_fig(fig, FIGURES / "eda01_income_scatter.png")

    fig, ax = plt.subplots(figsize=(8, 4.4))
    labels = list(boroughs.sort_values("borough")["borough"])
    data = [stable.loc[stable["borough"] == name, "complaints_per_1k"].dropna() for name in labels]
    ax.boxplot(data, tick_labels=labels, showfliers=False, orientation="vertical")
    ax.set_ylabel("인구 1,000명당 민원 수")
    ax.set_xlabel("자치구")
    ax.set_title(f"자치구별 Tract 접수율 (인구 {POP_MIN:,}명 이상, 이상점 숨김)")
    save_fig(fig, FIGURES / "eda01_borough_box.png")


def extremes(stable: pd.DataFrame, n: int, highest: bool) -> pd.DataFrame:
    cols = [
        "GEOID",
        "borough",
        "tract_name",
        "total_pop",
        "median_income",
        "renter_rate",
        "complaint_count",
        "complaints_per_1k",
    ]
    ordered = stable.sort_values("complaints_per_1k", ascending=not highest)
    return ordered[cols].head(n)


def write_report(
    coverage: dict[str, int],
    tracts: pd.DataFrame,
    missing: pd.DataFrame,
    boroughs: pd.DataFrame,
    profile: pd.DataFrame,
    spearman: pd.DataFrame,
    income_q: pd.DataFrame,
    renter_q: pd.DataFrame,
    top: pd.DataFrame,
) -> None:
    stable = tracts.loc[tracts["stable"]]
    small = tracts.loc[~tracts["stable"]]
    income_missing = int(tracts["median_income"].isna().sum())
    city_rate = tracts["complaint_count"].sum() / tracts["total_pop"].sum() * 1000
    stable_rate = profile.query("subset == 'pop_ge_1000' and column == 'complaints_per_1k'").iloc[0]
    income_rho = spearman.loc[spearman["variable"] == "median_income"].iloc[0]
    renter_rho = spearman.loc[spearman["variable"] == "renter_rate"].iloc[0]

    def q_line(frame: pd.DataFrame) -> str:
        bits = [
            f"{row.quintile} {fmt_num(row.pop_weighted_per_1k, 0)}"
            for row in frame.itertuples()
        ]
        return " → ".join(bits)

    lines = [
        "# 데이터 개요와 기초 EDA",
        "",
        "분석 단위는 뉴욕시 Census Tract다. 311은 2025-11-01부터 2026-10-31까지이고, ACS는 2024년 5개년 추정치다. 두 자료의 기간이 같지 않으므로 아래 관계는 같은 해의 인과가 아니다.",
        "",
        "## 데이터 범위",
        "",
        f"- 311 민원 {fmt_int(coverage['rows'])}건 중 좌표가 있는 민원은 {fmt_int(coverage['with_xy'])}건이다. 좌표 결측은 {fmt_int(coverage['missing_xy'])}건이다.",
        f"- 좌표가 Tract 안에 들어온 민원은 {fmt_int(coverage['in_tract'])}건이고, Tract 밖은 {fmt_int(coverage['outside_tract'])}건이다.",
        f"- ACS와 결합된 Tract는 {fmt_int(len(tracts))}개다. 인구 합계는 {fmt_int(tracts['total_pop'].sum())}명이다.",
        f"- 시 전체 인구 1,000명당 민원 수는 {fmt_num(city_rate, 1)}건이다. 민원 합을 인구 합으로 나눈 값이다.",
        "",
        "## 결측",
        "",
        f"- 가구 중위소득이 비어 있는 Tract는 {income_missing}개 ({income_missing / len(tracts) * 100:.1f}%)다. 인구가 적거나 센서스가 소득을 공개하지 않은 구역이 여기에 들어간다.",
        "- 인구, 점유 가구, 인종 집계는 결측이 거의 없다. 상세 건수는 `outputs/tables/eda01_missing.csv`에 있다.",
        "",
        "## 접수율이 안정된 Tract",
        "",
        f"- 인구 {POP_MIN:,}명 미만 Tract는 {fmt_int(len(small))}개다. 이 구역의 민원은 {fmt_int(small['complaint_count'].sum())}건으로, 전체 집계 민원의 {small['complaint_count'].sum() / tracts['complaint_count'].sum() * 100:.1f}%다.",
        f"- 인구 {POP_MIN:,}명 이상 Tract {fmt_int(len(stable))}개의 접수율 중앙값은 {fmt_num(stable_rate['median'], 1)}건, 사분위 범위는 {fmt_num(stable_rate['p25'], 1)}–{fmt_num(stable_rate['p75'], 1)}건이다.",
        "- 인구가 아주 적은 Tract의 1,000명당 수치는 순위에서 빼는 편이 맞다. 상관과 5분위 비교는 이 기준을 쓴다.",
        (
            f"- 인구 {POP_MIN:,}명 이상에서도 {top.iloc[0]['borough']} {top.iloc[0]['GEOID']}는 "
            f"민원 {fmt_int(top.iloc[0]['complaint_count'])}건, 1,000명당 "
            f"{fmt_num(top.iloc[0]['complaints_per_1k'], 0)}건이다. "
            "한 지점에 좌표가 반복된 시설이나 주소일 수 있다."
        ),
        "",
        "## 자치구",
        "",
        "자치구 수치는 민원 합을 인구 합으로 나눈 것이다. Tract 중앙값과 다를 수 있다.",
        "",
    ]
    for row in boroughs.itertuples():
        lines.append(
            f"- {row.borough}: 인구 {fmt_int(row.total_pop)}명, 민원 {fmt_int(row.complaint_count)}건, "
            f"1,000명당 {fmt_num(row.complaints_per_1k, 1)}건, 임차 비율 {row.renter_rate * 100:.1f}%."
        )
    lines.extend(
        [
            "",
            "## 같이 움직이는 변수",
            "",
            f"인구 {POP_MIN:,}명 이상 Tract에서 인구 1,000명당 민원 수와의 스피어만 순위 상관이다. 순위만 보므로 직선 관계를 가정하지 않는다.",
            "",
            f"- 중위소득: rho {income_rho.spearman_rho:.2f} (n={fmt_int(income_rho.n)}). 소득이 높은 Tract일수록 접수율 순위가 {'낮다' if income_rho.spearman_rho < 0 else '높다'}.",
            f"- 임차 비율: rho {renter_rho.spearman_rho:.2f} (n={fmt_int(renter_rho.n)}).",
            f"- 중위소득 5분위의 인구 가중 1,000명당 민원 수: {q_line(income_q)}.",
            f"- 임차 비율 5분위: {q_line(renter_q)}.",
            "- 이 상관은 민원 유형을 나누지 않은 전체 건수다. 소음, 난방, 포트홀은 방향이 다를 수 있다.",
            "",
            "## 그림과 표",
            "",
            "- `outputs/figures/eda01_borough_rate.png`",
            "- `outputs/figures/eda01_rate_hist.png`",
            "- `outputs/figures/eda01_income_scatter.png`",
            "- `outputs/figures/eda01_borough_box.png`",
            "- `outputs/tables/eda01_*.csv`",
            "",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    coverage = request_coverage()
    tracts = load_tracts()
    missing = missing_table(tracts)
    boroughs = borough_table(tracts)
    profile = numeric_profile(tracts)
    stable = tracts.loc[tracts["stable"]].copy()
    spearman = spearman_table(stable)
    income_q = quintile_table(stable, "median_income")
    renter_q = quintile_table(stable, "renter_rate")
    top = extremes(stable, 10, highest=True)
    bottom = extremes(stable, 10, highest=False)

    small = tracts.loc[~tracts["stable"]]
    exclusion = pd.DataFrame(
        [
            {"step": "311 전체 행", "removed": 0, "remaining": coverage["rows"], "rule": "311_requests_clean.parquet"},
            {
                "step": "좌표 결측 제외",
                "removed": coverage["missing_xy"],
                "remaining": coverage["with_xy"],
                "rule": "latitude 결측",
            },
            {
                "step": "Tract 밖 좌표 제외",
                "removed": coverage["outside_tract"],
                "remaining": coverage["in_tract"],
                "rule": "ACS Tract polygon within",
            },
            {
                "step": f"인구 {POP_MIN}명 미만 Tract를 상관·5분위에서 제외",
                "removed": int(len(small)),
                "remaining": int(len(stable)),
                "rule": f"total_pop >= {POP_MIN}. 제외 Tract의 민원 {int(small['complaint_count'].sum())}건",
            },
        ]
    )

    save_table(pd.DataFrame([coverage]), "eda01_coverage.csv")
    save_table(missing, "eda01_missing.csv")
    save_table(boroughs, "eda01_borough.csv")
    save_table(profile, "eda01_numeric.csv")
    save_table(spearman, "eda01_spearman.csv")
    save_table(income_q, "eda01_income_quintile.csv")
    save_table(renter_q, "eda01_renter_quintile.csv")
    save_table(top, "eda01_top10.csv")
    save_table(bottom, "eda01_bottom10.csv")
    save_table(exclusion, "eda01_exclusion_log.csv")
    draw_figures(boroughs, stable)
    write_report(
        coverage, tracts, missing, boroughs, profile, spearman, income_q, renter_q, top
    )
    print(f"표: {TABLES}")
    print(f"그림: {FIGURES}")
    print(f"보고서: {REPORT}")


if __name__ == "__main__":
    main()
