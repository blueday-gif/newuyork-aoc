"""@st.fragment 통계 체험: 작은 분모, 보고 편향."""
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import streamlit as st

import qlib

_LAB_JSON = Path(__file__).resolve().parents[1] / "data" / "labs" / "small_denominator.json"


def render(lab_key: str, key: str) -> None:
    entry = LABS.get(lab_key)
    if not entry:
        return
    entry[1](key)


@st.cache_data(ttl="1h", max_entries=2)
def _small_denom_df(mtime: int) -> pd.DataFrame:
    return pd.DataFrame(qlib.lab("small_denominator")["rows"])


@st.fragment
def small_denominator(key: str) -> None:
    data = qlib.lab("small_denominator")
    df = _small_denom_df(_LAB_JSON.stat().st_mtime_ns if _LAB_JSON.exists() else 0)
    totals = data["totals"]
    default_min = data["default_min_pop"]

    st.markdown(
        "인구가 아주 적은 Tract는 민원 몇백 건만으로 '1,000명당 민원'이 수만 건으로 치솟는다. "
        "최소 인구 기준을 바꿔 가며 순위가 어떻게 흔들리는지 보자. "
        "기본값 1,000명은 이 프로젝트의 분석 기준이다."
    )
    min_pop = st.slider("최소 인구(명)", 0, 5000, value=default_min, step=50, key=f"{key}_min")

    work = df.copy()
    work["per_1k"] = float("nan")
    pos = work["pop"] > 0
    work.loc[pos, "per_1k"] = work.loc[pos, "n"] / work.loc[pos, "pop"] * 1000
    kept = work[(work["pop"] >= min_pop) & (work["pop"] > 0)]
    n_tracts = len(kept)
    n_complaints = int(kept["n"].sum()) if n_tracts else 0
    share = 100 * n_complaints / totals["complaints"] if totals["complaints"] else 0.0

    if n_tracts:
        top = kept.loc[kept["per_1k"].idxmax()]
        max_per = float(top["per_1k"])
        max_help = f"인구 {int(top['pop']):,}명, 민원 {int(top['n']):,}건"
    else:
        max_per, max_help = 0.0, "남은 Tract 없음"

    with st.container(horizontal=True):
        st.metric("남은 Tract", f"{n_tracts:,}개", help=f"전체 {totals['tracts']:,}개 중", border=True)
        st.metric("남은 민원", f"{n_complaints:,}건", help=f"전체의 {share:.1f}%", border=True)
        st.metric("1,000명당 최댓값", f"{max_per:,.0f}건", help=max_help, border=True)

    top10 = kept.nlargest(10, "per_1k").copy()
    if len(top10):
        top10["Tract"] = top10.apply(
            lambda r: f"{r['boro']} {str(r['GEOID'])[-6:]} · {int(r['pop']):,}명", axis=1)
        top10["1,000명당"] = top10["per_1k"].round(1)
        spec1 = {
            "kind": "barh",
            "title": "1,000명당 민원 상위 10개 Tract",
            "x": "1,000명당",
            "y": "Tract",
            "rows": top10[["Tract", "1,000명당"]].to_dict("records"),
        }
        with st.container(border=True):
            st.markdown(f"**{spec1['title']}**")
            st.altair_chart(qlib.chart(spec1), alt=spec1["title"])

    scatter = work[(work["pop"] > 0) & (work["n"] > 0)].copy()
    scatter["구분"] = ["포함" if p >= min_pop else "제외" for p in scatter["pop"]]
    scatter["인구"] = scatter["pop"]
    scatter["1,000명당"] = scatter["per_1k"]
    spec2 = {
        "kind": "scatter",
        "title": "인구와 1,000명당 민원(로그 축)",
        "x": "인구",
        "y": "1,000명당",
        "color": "구분",
        "colors": {"포함": "#2457a7", "제외": "#c94f6d"},
        "log_x": True,
        "log_y": True,
        "rows": scatter[["인구", "1,000명당", "구분"]].to_dict("records"),
    }
    with st.container(border=True):
        st.markdown(f"**{spec2['title']}**")
        st.altair_chart(qlib.chart(spec2), alt=spec2["title"])
        st.caption("제외된 점(빨강)이 왼쪽 위로 치솟는다. 분모가 작을수록 비율이 불안정하다.")

    if min_pop == default_min:
        st.caption(f"기본값 1,000명: 95번 분석과 같은 {n_tracts:,}개 Tract, {n_complaints:,}건이다.")
    if min_pop == 0:
        k = int((df["pop"] == 0).sum())
        st.caption(f"인구 0명인 Tract {k}개는 나눌 수 없어 늘 뺀다.")


@st.fragment
def reporting_bias(key: str) -> None:
    st.info(
        "가상 자료다. 실제 뉴욕 수치가 아니라, '신고가 적다 = 문제가 적다'는 착각이 예산을 어떻게 비트는지 따라가 보는 모형이다.",
        icon=":material/science:",
    )
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**동네 A**")
        a_true = st.slider("실제 문제(1,000가구당 건)", 0, 100, value=30, step=1, key=f"{key}_a_true")
        a_rate = st.slider("신고율(%)", 0, 100, value=20, step=5, key=f"{key}_a_rate")
    with col_b:
        st.markdown("**동네 B**")
        b_true = st.slider("실제 문제(1,000가구당 건)", 0, 100, value=20, step=1, key=f"{key}_b_true")
        b_rate = st.slider("신고율(%)", 0, 100, value=60, step=5, key=f"{key}_b_rate")

    a_rep = a_true * a_rate / 100
    b_rep = b_true * b_rate / 100
    if a_true + b_true == 0:
        st.warning("두 동네 모두 실제 문제가 0이라 예산을 나눌 수 없다.")
        return
    if a_rep + b_rep == 0:
        st.warning(
            "두 동네 모두 신고가 0건이라 '신고에 맞춤' 배분을 할 수 없다. "
            "신고만 보는 행정에는 두 동네 모두 문제가 없는 것처럼 보인다."
        )
        return

    budget_rep_a = a_rep / (a_rep + b_rep) * 100
    budget_true_a = a_true / (a_true + b_true) * 100
    budget_rep_b = b_rep / (a_rep + b_rep) * 100
    budget_true_b = b_true / (a_true + b_true) * 100
    gap = budget_true_a - budget_rep_a

    with st.container(horizontal=True):
        st.metric("동네 A 신고", f"{a_rep:.1f}건", border=True)
        st.metric("동네 B 신고", f"{b_rep:.1f}건", border=True)
        st.metric(
            "A가 덜 받는 예산",
            f"{gap:+.1f}",
            help="실제 문제에 맞춰 나눌 때와 비교한 차이. 음수면 A가 더 받는다.",
            border=True,
        )

    rows = [
        {"동네": "A", "기준": "실제 문제에 맞춤", "예산": round(budget_true_a, 1)},
        {"동네": "A", "기준": "신고에 맞춤", "예산": round(budget_rep_a, 1)},
        {"동네": "B", "기준": "실제 문제에 맞춤", "예산": round(budget_true_b, 1)},
        {"동네": "B", "기준": "신고에 맞춤", "예산": round(budget_rep_b, 1)},
    ]
    spec = {
        "kind": "group",
        "title": "예산 100을 나누는 두 방식",
        "x": "동네",
        "y": "예산",
        "color": "기준",
        "colors": {"실제 문제에 맞춤": "#3a9d6e", "신고에 맞춤": "#e07b39"},
        "rows": rows,
    }
    with st.container(border=True):
        st.markdown(f"**{spec['title']}**")
        st.altair_chart(qlib.chart(spec), alt=spec["title"])

    if a_true == 30 and b_true == 20 and a_rate == 20 and b_rate == 60:
        st.caption(
            "기본값에서 A는 문제가 더 많은데(30 > 20) 신고가 적어(6 < 12) 예산의 3분의 1만 받는다. "
            "39번(쥐 점검)과 37번(난방)이 이 문제를 실제 자료로 다룬다."
        )


LABS: dict[str, tuple[str, Callable[[str], None]]] = {
    "small_denominator": ("작은 분모의 함정", small_denominator),
    "reporting_bias": ("보고 편향 시뮬레이터", reporting_bias),
}
