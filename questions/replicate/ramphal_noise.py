"""Ramphal 등(2022) 재현: 소득 4분위 × 계절(겨울 vs 7월)별 소음 민원.

실행(저장소 루트): py -3 questions/replicate/ramphal_noise.py
필요: 환경 변수 NY311_RAW(311 원본 parquet). 처음 한 번은 questions/.cache/slim.parquet을 만든다.
결과: questions/replicate/out/ramphal/ (CSV 표, PNG 그림 2개, results.json)

순서: 1) ACS 정제 → 2) 소음 민원 추출 → 3) Tract 결합 → 4) 중복 점검
      → 5) 분위·월·유형별 10만 명당 → 6) 부트스트랩 신뢰구간 → 7) 포아송 회귀 → 8) 민감도 → 9) 그림
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "calc"))
from common import ROOT, acs, load_311  # noqa: E402

OUT = HERE / "out" / "ramphal"
HOT = "655 EAST 230 STREET"  # 11번 이상치 주소(소음 4.7만 건, 11~12월 집중). 본 분석에서 뺀다.
MIN_POP = 1000               # 프로젝트 기준: 인구 1,000명 미만 Tract는 분모가 불안정해 뺀다(74·95번).
PER = 100_000                # 논문 관례에 맞춰 인구 10만 명당
JULY, WINTER = 7, (12, 1, 2)
SUMMER_ALT = (6, 7, 8)
MONTHS = pd.period_range("2025-11", "2026-10", freq="M")
QL = ["Q1(저소득)", "Q2", "Q3", "Q4(고소득)"]
TYPES = {"Noise - Residential": "주거", "Noise - Street/Sidewalk": "거리", "Noise - Commercial": "상업"}
TYPE_ORDER = ["전체", "주거", "거리", "상업", "기타"]
B = 2000
rng = np.random.default_rng(20261128)


# 1. ACS 정제 -------------------------------------------------------------------------
def clean_tracts() -> tuple[pd.DataFrame, list[dict]]:
    a = acs()
    log = [{"단계": "ACS Tract 전체", "남은 수": len(a), "제외": 0, "기준": "ACS 2024 5개년"}]
    num = a.select_dtypes("number").columns
    sentinel = int((a[num] <= -100_000_000).sum().sum())  # -666666666 등. CSV 작성 때 이미 결측 처리됐는지 확인
    a[num] = a[num].mask(a[num] <= -100_000_000)
    log.append({"단계": "센티널 값(-666666666 등) → 결측", "남은 수": len(a), "제외": 0,
                "기준": f"남아 있던 센티널 셀 {sentinel}개"})
    n = len(a)
    a = a[a.total_pop > 0]
    log.append({"단계": "인구 0명", "남은 수": len(a), "제외": n - len(a), "기준": "total_pop = 0"})
    n = len(a)
    a = a[a.total_pop >= MIN_POP]
    log.append({"단계": f"인구 {MIN_POP:,}명 미만", "남은 수": len(a), "제외": n - len(a),
                "기준": "분모 폭주 방지(프로젝트 기준, 74·95번)"})
    n = len(a)
    a = a[a.median_income.notna()]
    log.append({"단계": "중위 가구 소득 결측", "남은 수": len(a), "제외": n - len(a),
                "기준": "ACS가 추정치를 내지 않은 Tract"})
    a = a.copy()
    a["q"] = pd.qcut(a.median_income, 4, labels=QL)
    a["boro"] = a.borough
    return a[["GEOID", "boro", "total_pop", "median_income", "q"]], log


# 2~4. 소음 민원 추출·결합·중복 --------------------------------------------------------------
def noise_complaints(tr: pd.DataFrame, log: list[dict]) -> pd.DataFrame:
    df = load_311()
    n_all = len(df)
    d = df[df.problem.astype(str).str.startswith("Noise")].copy()
    log.append({"단계": "311 전체 → 소음 민원", "남은 수": len(d), "제외": n_all - len(d),
                "기준": "유형 이름이 'Noise'로 시작(8개 유형)"})
    d["type"] = d.problem.astype(str).map(TYPES).fillna("기타")
    d["month"] = d.created.dt.to_period("M")
    pg = pd.read_parquet(ROOT / "data" / "processed" / "nyc311_point_geoid.parquet").rename(
        columns={"unique_key": "key"})
    n = len(d)
    d = d.merge(pg, on="key", how="inner")
    log.append({"단계": "좌표 → Census Tract", "남은 수": len(d), "제외": n - len(d),
                "기준": "좌표가 없거나 Tract 밖"})
    n = len(d)
    d = d.merge(tr, on="GEOID", how="inner")
    log.append({"단계": "분석 대상 Tract 안", "남은 수": len(d), "제외": n - len(d),
                "기준": "위에서 뺀 Tract(인구 적음·소득 결측)에 있는 민원"})
    d["hot"] = d.addr_n == HOT
    # 중복: 같은 날짜·같은 주소·같은 유형. 주소가 비어 있으면 판단할 수 없어 중복으로 보지 않는다.
    has_addr = d.addr_n != ""
    d["dup"] = False
    d.loc[has_addr, "dup"] = d[has_addr].duplicated(["date", "addr_n", "problem"], keep="first")
    return d


# 5. 집계 ------------------------------------------------------------------------------
def tract_month(d: pd.DataFrame, tr: pd.DataFrame) -> pd.DataFrame:
    """Tract × 월 × 유형 건수(0건 포함). 유형 '전체'를 더한다."""
    g = d.groupby(["GEOID", "month", "type"], observed=True).size()
    full = pd.MultiIndex.from_product([tr.GEOID, MONTHS, ["주거", "거리", "상업", "기타"]],
                                      names=["GEOID", "month", "type"])
    g = g.reindex(full, fill_value=0).rename("n").reset_index()
    tot = g.groupby(["GEOID", "month"], as_index=False).n.sum().assign(type="전체")
    g = pd.concat([g, tot], ignore_index=True)
    return g.merge(tr, on="GEOID")


def summarize(tm: pd.DataFrame, summer=(JULY,)) -> pd.DataFrame:
    tm = tm.assign(m=tm.month.dt.month)
    pop = tm.drop_duplicates("GEOID").groupby("q", observed=True).total_pop.sum()
    rows = []
    for (q, t), g in tm.groupby(["q", "type"], observed=True):
        p = pop[q]
        year = g.n.sum()
        win = g[g.m.isin(WINTER)].n.sum() / len(WINTER)
        sm = g[g.m.isin(summer)].n.sum() / len(summer)
        rows.append({"분위": q, "유형": t, "Tract 수": g.GEOID.nunique(), "인구": int(p),
                     "연간 10만 명당": year / p * PER, "월평균 10만 명당": year / 12 / p * PER,
                     "겨울(12~2월) 월평균": win / p * PER, "여름 월": sm / p * PER,
                     "여름÷겨울": sm / win if win else np.nan, "여름÷월평균": sm / (year / 12) if year else np.nan})
    s = pd.DataFrame(rows)
    s["유형"] = pd.Categorical(s["유형"], TYPE_ORDER)
    return s.sort_values(["유형", "분위"]).reset_index(drop=True)


def monthly(tm: pd.DataFrame) -> pd.DataFrame:
    pop = tm.drop_duplicates("GEOID").groupby("q", observed=True).total_pop.sum()
    m = tm.groupby(["q", "type", "month"], observed=True).n.sum().reset_index()
    m["10만 명당"] = m.n / m.q.map(pop).astype(float) * PER
    m["월"] = m.month.astype(str)
    return m.rename(columns={"q": "분위", "type": "유형", "n": "건수"})[["분위", "유형", "월", "건수", "10만 명당"]]


# 6. 부트스트랩(Tract 재추출) -------------------------------------------------------------
def bootstrap(tm: pd.DataFrame) -> pd.DataFrame:
    """7월÷겨울 배수의 95% 구간. 분위 안의 Tract를 복원 추출한다. 같은 Tract 집합이면 인구가 약분된다."""
    tm = tm.assign(m=tm.month.dt.month)
    rows = []
    for t in TYPE_ORDER:
        g = tm[tm.type == t]
        jul = g[g.m == JULY].set_index("GEOID").n
        win = g[g.m.isin(WINTER)].groupby("GEOID").n.sum() / len(WINTER)
        q = g.drop_duplicates("GEOID").set_index("GEOID").q
        draws = {}
        for ql in QL:
            ids = q.index[q == ql]
            J, W = jul[ids].to_numpy(float), win[ids].to_numpy(float)
            idx = rng.integers(0, len(ids), (B, len(ids)))
            draws[ql] = J[idx].sum(1) / W[idx].sum(1)
            lo, hi = np.percentile(draws[ql], [2.5, 97.5])
            rows.append({"유형": t, "분위": ql, "7월÷겨울": J.sum() / W.sum(), "하한": lo, "상한": hi})
        rr = draws[QL[0]] / draws[QL[-1]]
        lo, hi = np.percentile(rr, [2.5, 97.5])
        rows.append({"유형": t, "분위": "Q1÷Q4", "7월÷겨울": np.nan, "하한": lo, "상한": hi,
                     "점추정": rows[-4]["7월÷겨울"] / rows[-1]["7월÷겨울"]})
    out = pd.DataFrame(rows)
    out.loc[out["분위"] == "Q1÷Q4", "7월÷겨울"] = out.pop("점추정")
    return out


# 7. 포아송 회귀(Tract × 월, 겨울 3개월 + 7월) ---------------------------------------------------
def model(tm: pd.DataFrame, label: str) -> list[dict]:
    import statsmodels.formula.api as smf
    import statsmodels.api as sm
    t = tm[(tm.type == "전체") & tm.month.dt.month.isin([*WINTER, JULY])].copy()
    t["july"] = (t.month.dt.month == JULY).astype(int)
    t["qc"] = t.q.cat.codes.map({0: "q1", 1: "q2", 2: "q3", 3: "q4"})
    t["boro"] = t.boro.astype(str)
    t["lpop"] = np.log(t.total_pop)
    out = []
    specs = {"자치구 고정효과": "n ~ C(qc, Treatment('q4')) * july + C(boro)",
             "자치구별 계절 허용": "n ~ C(qc, Treatment('q4')) * july + C(boro) * july"}
    for name, f in specs.items():
        r = smf.glm(f, t, offset=t.lpop, family=sm.families.Poisson()).fit(
            cov_type="cluster", cov_kwds={"groups": pd.factorize(t.GEOID)[0]})
        ci = r.conf_int()
        for term, lab in [("july", "Q4의 7월÷겨울(IRR)"),
                          ("C(qc, Treatment('q4'))[T.q1]:july", "Q1 7월 배수 ÷ Q4 7월 배수"),
                          ("C(qc, Treatment('q4'))[T.q2]:july", "Q2 7월 배수 ÷ Q4 7월 배수"),
                          ("C(qc, Treatment('q4'))[T.q3]:july", "Q3 7월 배수 ÷ Q4 7월 배수"),
                          ("C(qc, Treatment('q4'))[T.q1]", "겨울 수준: Q1 ÷ Q4")]:
            out.append({"자료": label, "모형": name, "항": lab, "IRR": np.exp(r.params[term]),
                        "하한": np.exp(ci.loc[term, 0]), "상한": np.exp(ci.loc[term, 1]), "p": r.pvalues[term],
                        "관측": int(r.nobs)})
    return out


# 9. 그림 --------------------------------------------------------------------------------
COLORS = {"Q1(저소득)": "#0d366b", "Q2": "#1c5cab", "Q3": "#3987e5", "Q4(고소득)": "#86b6ef"}
INK, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"


def _style(plt):
    plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 11,
                         "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED,
                         "ytick.color": MUTED, "figure.facecolor": SURF, "axes.facecolor": SURF})


def chart_monthly(m: pd.DataFrame, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _style(plt)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), sharey=False)
    labels = [p.strftime("%y.%m") for p in MONTHS]
    jul_i = list(MONTHS.month).index(JULY)
    for ax, t in zip(axes, ["주거", "거리", "상업"]):
        ax.axvspan(jul_i - 0.5, jul_i + 0.5, color="#f0efec", zorder=0)
        for q in QL:
            s = m[(m["유형"] == t) & (m["분위"] == q)].set_index("월")["10만 명당"].reindex([str(p) for p in MONTHS])
            ax.plot(range(12), s.values, color=COLORS[q], lw=2, marker="o", ms=4, label=q, zorder=3)
            if q in (QL[0], QL[-1]):
                ax.annotate(q.split("(")[0], (11, s.values[-1]), xytext=(6, 0), textcoords="offset points",
                            va="center", color=INK, fontsize=10)
        ax.set_title(f"{t} 소음", loc="left", color=INK, fontsize=13, fontweight="bold")
        ax.set_xticks(range(12), labels, fontsize=9)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylim(bottom=0)
        ax.text(jul_i, ax.get_ylim()[1] * 0.02, "7월", ha="center", va="bottom", color=MUTED, fontsize=9)
    axes[0].set_ylabel("인구 10만 명당 월 민원")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper left", bbox_to_anchor=(0.01, 0.925), ncol=4, frameon=False, fontsize=10,
               title="Tract 중위소득 4분위:", title_fontsize=10, alignment="left")
    fig.suptitle("소득 4분위별 월별 소음 민원(인구 10만 명당, 2025-11 ~ 2026-10)", x=0.01, ha="left",
                 color=INK, fontsize=15, fontweight="bold")
    fig.text(0.01, 0.005, "유형마다 세로축 범위가 다르다. 655 E 230th St 한 주소 제외. 자료: NYC 311, ACS 2024 5개년.",
             color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.03, 1, 0.84))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def chart_ratio(bs: pd.DataFrame, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _style(plt)
    types = ["전체", "주거", "거리", "상업"]
    fig, ax = plt.subplots(figsize=(11, 5.8))
    w = 0.17
    for i, q in enumerate(QL):
        r = bs[bs["분위"] == q].set_index("유형").loc[types]
        x = np.arange(len(types)) + (i - 1.5) * w
        ax.vlines(x, r["하한"], r["상한"], color=COLORS[q], lw=2, zorder=3)
        ax.scatter(x, r["7월÷겨울"], s=70, color=COLORS[q], edgecolor=SURF, linewidth=2, label=q, zorder=4)
        if q in (QL[0], QL[-1]):
            for xi, v in zip(x, r["7월÷겨울"]):
                ax.annotate(f"{v:.2f}", (xi, v), xytext=(-8 if q == QL[0] else 8, 0), textcoords="offset points",
                            ha="right" if q == QL[0] else "left", va="center", fontsize=9, color=INK)
    ax.set_yscale("log", base=2)
    ticks = [0.5, 1, 2, 4, 8]
    ax.set_yticks(ticks, ["0.5배", "1배", "2배", "4배", "8배"])
    ax.set_ylim(0.45, 14)
    ax.axhline(1, color=INK, lw=1, zorder=2)
    ax.text(-0.45, 1.04, "겨울과 같음", ha="left", va="bottom", color=MUTED, fontsize=9)
    ax.set_xticks(range(len(types)), [f"{t} 소음" for t in types], fontsize=11)
    ax.set_xlim(-0.5, len(types) - 0.5)
    ax.set_ylabel("7월 ÷ 겨울(12~2월) 월평균, 로그 눈금")
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=4, loc="upper left", fontsize=10, bbox_to_anchor=(0, 1.0))
    ax.set_title("여름(7월)에 소음 민원이 겨울의 몇 배가 되나: 소득 분위별", loc="left", color=INK,
                 fontsize=15, fontweight="bold", pad=14)
    fig.text(0.01, 0.01, "점: 배수, 세로선: Tract 재추출 부트스트랩 95% 구간(2,000회). 655 E 230th St 제외.",
             color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


# 실행 ----------------------------------------------------------------------------------
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tr, log = clean_tracts()
    d = noise_complaints(tr, log)
    n = len(d)
    main_d = d[~d.hot]
    log.append({"단계": "이상치 주소 제외(본 분석)", "남은 수": len(main_d), "제외": n - len(main_d), "기준": HOT})

    tm = tract_month(main_d, tr)
    summ = summarize(tm)
    mon = monthly(tm)
    bs = bootstrap(tm)

    # 4. 중복 점검 보고
    dup = (d.assign(분위=d.q).groupby("분위", observed=True)
           .agg(민원=("key", "size"), 중복=("dup", "sum")).reset_index())
    dup["중복 비율(%)"] = dup["중복"] / dup["민원"] * 100
    dup_hot = int(d[d.hot].dup.sum())

    # 8. 민감도
    def q14(s: pd.DataFrame, col="여름÷겨울") -> dict:
        x = s[s["유형"] == "전체"].set_index("분위")[col]
        return {"Q1": x[QL[0]], "Q4": x[QL[-1]], "Q1÷Q4": x[QL[0]] / x[QL[-1]]}

    per_addr = main_d[main_d.addr_n != ""].addr_n.value_counts()
    heavy = set(per_addr[per_addr >= 365].index)  # 하루 1건 꼴 이상 신고된 주소(반복 신고자 의심)
    sens = []
    for lab, data, summer in [("본 분석(이상치 주소 제외)", main_d, (JULY,)),
                              ("이상치 주소 포함", d, (JULY,)),
                              ("중복 제거(같은 날·주소·유형)", main_d[~main_d.dup], (JULY,)),
                              (f"연 365건 이상 주소 {len(heavy)}곳 제외", main_d[~main_d.addr_n.isin(heavy)], (JULY,)),
                              ("여름 = 6~8월 평균", main_d, SUMMER_ALT)]:
        s = summarize(tract_month(data, tr), summer=summer)
        r = q14(s)
        sens.append({"분석": lab, "민원": len(data), "Q1 여름÷겨울": r["Q1"], "Q4 여름÷겨울": r["Q4"],
                     "Q1÷Q4": r["Q1÷Q4"]})
    r = q14(summ, "여름÷월평균")
    sens.append({"분석": "참고: 7월÷12개월 월평균(67번 방식)", "민원": len(main_d), "Q1 여름÷겨울": r["Q1"],
                 "Q4 여름÷겨울": r["Q4"], "Q1÷Q4": r["Q1÷Q4"]})
    sens = pd.DataFrame(sens)

    mod = pd.DataFrame(model(tm, "본 분석") + model(tract_month(main_d[~main_d.dup], tr), "중복 제거"))

    cuts = tr.groupby("q", observed=True).median_income.agg(["min", "max", "size"]).reset_index()
    cuts.columns = ["분위", "최저 소득", "최고 소득", "Tract 수"]
    topcode = int((tr.median_income >= 250_000).sum())

    # 저장
    pd.DataFrame(log).to_csv(OUT / "01_exclusions.csv", index=False, encoding="utf-8-sig")
    cuts.to_csv(OUT / "02_income_quartiles.csv", index=False, encoding="utf-8-sig")
    dup.to_csv(OUT / "03_duplicates.csv", index=False, encoding="utf-8-sig")
    summ.to_csv(OUT / "04_summary_by_quartile.csv", index=False, encoding="utf-8-sig", float_format="%.3f")
    mon.to_csv(OUT / "05_monthly_rates.csv", index=False, encoding="utf-8-sig", float_format="%.2f")
    bs.to_csv(OUT / "06_bootstrap_ratio.csv", index=False, encoding="utf-8-sig", float_format="%.3f")
    mod.to_csv(OUT / "07_poisson_model.csv", index=False, encoding="utf-8-sig", float_format="%.4f")
    sens.to_csv(OUT / "08_sensitivity.csv", index=False, encoding="utf-8-sig", float_format="%.3f")
    chart_monthly(mon, OUT / "chart1_monthly_by_quartile.png")
    chart_ratio(bs, OUT / "chart2_july_winter_ratio.png")
    json.dump({"tracts": len(tr), "noise_all": int(log[5]["남은 수"]) if len(log) > 5 else None,
               "noise_main": len(main_d), "dup_total": int(d.dup.sum()), "dup_share": float(d.dup.mean()),
               "dup_at_hot": dup_hot, "topcoded_250k": topcode, "log": log},
              open(OUT / "results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)

    pd.set_option("display.width", 200, "display.max_columns", 20, "display.float_format", "{:,.3f}".format)
    for name, f in [("제외 기록", pd.DataFrame(log)), ("소득 분위", cuts), ("중복", dup),
                    ("요약(전체·주거·거리·상업)", summ[summ["유형"] != "기타"]), ("부트스트랩", bs),
                    ("민감도", sens), ("포아송", mod)]:
        print(f"\n== {name}\n{f.to_string(index=False)}")
    print(f"\n중복 전체 {int(d.dup.sum()):,}건({d.dup.mean() * 100:.1f}%), 이상치 주소 안 {dup_hot:,}건; 25만 달러 상한 Tract {topcode}개")


if __name__ == "__main__":
    main()
