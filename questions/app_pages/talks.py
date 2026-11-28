"""발표후보: 영향력 있는 311 논문의 실험을 최신 자료로 재현한 결과(수업 발표용).

해설은 replicate/talks.toml, 수치·그림은 replicate/out/<키>/ 의 CSV·PNG에서 읽는다.
계산(replicate/*.py)은 311 원본이 필요해 로컬에서만 돌린다.
"""
import tomllib
from pathlib import Path

import pandas as pd
import streamlit as st

import qlib

RDIR = Path(__file__).resolve().parents[1] / "replicate"
TALKS = tomllib.loads((RDIR / "talks.toml").read_text(encoding="utf-8"))
QS = qlib.questions()
QL = ["Q1(저소득)", "Q2", "Q3", "Q4(고소득)"]


@st.cache_data
def table(key: str, name: str) -> pd.DataFrame:
    return pd.read_csv(RDIR / "out" / key / name, encoding="utf-8-sig")


st.title("발표후보")
st.caption("뉴욕 311 분야 논문의 실험을 이 앱의 최신 자료(2025-11 ~ 2026-10)로 재현했다. 10분 수업 발표용 후보다.")

key = st.segmented_control("후보", list(TALKS), default=list(TALKS)[0],
                           format_func=lambda k: TALKS[k]["label"], key="talk") or list(TALKS)[0]
t = TALKS[key]
out = RDIR / "out" / key

st.subheader(f"{t['label']}: {t['paper']}", divider="gray")
st.markdown(t["headline"])
st.caption(t["data"])

boot = table(key, "06_bootstrap_ratio.csv").set_index(["유형", "분위"])
model = table(key, "07_poisson_model.csv")
gap_boro = model[(model["자료"] == "본 분석") & (model["모형"] == "자치구별 계절 허용")
                 & (model["항"] == "Q1 7월 배수 ÷ Q4 7월 배수")].iloc[0]
with st.container(horizontal=True):
    st.metric("7월 ÷ 겨울: 저소득(Q1)", f"{boot.loc[('전체', QL[0]), '7월÷겨울']:.2f}배", border=True,
              help="7월 소음 민원 ÷ 12~2월 월평균. 655 E 230th St 제외")
    st.metric("7월 ÷ 겨울: 고소득(Q4)", f"{boot.loc[('전체', QL[-1]), '7월÷겨울']:.2f}배", border=True)
    r = boot.loc[("전체", "Q1÷Q4")]
    st.metric("격차(Q1 ÷ Q4)", f"{r['7월÷겨울']:.2f}배", border=True,
              help=f"부트스트랩 95% 구간 {r['하한']:.2f}~{r['상한']:.2f}")
    st.metric("자치구별 계절 허용 시 격차", f"{gap_boro['IRR']:.2f}배", border=True,
              help=f"포아송 회귀, 95% 구간 {gap_boro['하한']:.2f}~{gap_boro['상한']:.2f}, p = {gap_boro['p']:.2f}")

st.subheader("원 논문과 비교", divider="gray")
st.markdown(t["compare"])
st.caption(t["compare_note"])

st.subheader("그림", divider="gray")
st.image(str(out / "chart1_monthly_by_quartile.png"), caption=t["chart1"])
st.image(str(out / "chart2_july_winter_ratio.png"), caption=t["chart2"])

st.subheader("소득 분위별 요약(인구 10만 명당)", divider="gray")
s = table(key, "04_summary_by_quartile.csv")
s = s[s["유형"].isin(["전체", "주거", "거리", "상업"])].rename(columns={"여름 월": "7월", "여름÷겨울": "7월÷겨울",
                                                                  "여름÷월평균": "7월÷월평균"})
st.dataframe(s, hide_index=True, column_config={
    "인구": st.column_config.NumberColumn(format="localized"),
    **{c: st.column_config.NumberColumn(format="%.0f") for c in ["연간 10만 명당", "월평균 10만 명당",
                                                                 "겨울(12~2월) 월평균", "7월"]},
    **{c: st.column_config.NumberColumn(format="%.2f") for c in ["7월÷겨울", "7월÷월평균"]},
})

st.subheader("해석", divider="gray")
tab1, tab2, tab3 = st.tabs(["관측한 것", "말할 수 있는 것", "한계"])
tab1.markdown(t["observed"])
tab2.markdown(t["can_say"])
tab3.markdown(t["limits"])

st.subheader("민감도: 어떻게 계산해도 같은가", divider="gray")
st.dataframe(table(key, "08_sensitivity.csv"), hide_index=True, column_config={
    "민원": st.column_config.NumberColumn(format="localized"),
    **{c: st.column_config.NumberColumn(format="%.2f") for c in ["Q1 여름÷겨울", "Q4 여름÷겨울", "Q1÷Q4"]},
})

if "long_title" in t:
    st.subheader(t["long_title"], divider="gray")
    st.caption(t["long_note"])
    lg = pd.read_csv(RDIR / "out" / "ramphal_long" / "05_growth_2019_2020_main.csv", encoding="utf-8-sig")
    st.dataframe(lg, hide_index=True, column_config={
        c: st.column_config.NumberColumn(format="%.1f") for c in lg.columns if lg[c].dtype.kind == "f"})
    with st.container(horizontal=True):
        st.metric("2019→2020 증가율: 저소득(Q1)", f"{lg.loc[0, '2019→2020 증가율(%)']:.0f}%", border=True,
                  help="논문 +103%")
        st.metric("2019→2020 증가율: 고소득(Q4)", f"{lg.loc[3, '2019→2020 증가율(%)']:.0f}%", border=True,
                  help="논문 +50%")
    st.image(str(RDIR / "out" / "ramphal_long" / "chart3_july_2010_2026.png"),
             caption="7월 소음 민원, 소득 4분위별(2010~2026.10). 2014년 자료 체계 변화, 2020 음영 표시.")
    tabA, tabB, tabC = st.tabs(["관측한 것", "말할 수 있는 것", "한계"])
    tabA.markdown(t["long_observed"])
    tabB.markdown(t["long_can_say"])
    tabC.markdown(t["long_limits"])

st.subheader("예상 질문", divider="gray")
for qa in t["qa"]:
    with st.expander(qa["q"]):
        st.markdown(qa["a"])

with st.expander("정제와 검증 기록"):
    st.markdown(t["cleaning"])
    st.dataframe(table(key, "01_exclusions.csv"), hide_index=True)
    st.dataframe(table(key, "03_duplicates.csv"), hide_index=True)
with st.expander("계산 방법"):
    st.markdown(t["method"])
    st.dataframe(model, hide_index=True)

if t.get("related"):
    with st.container(horizontal=True, gap="small", vertical_alignment="center"):
        st.caption("관련 문항", width="content")
        for qid in t["related"]:
            st.page_link("app_pages/question.py", label=f"{qid}번", query_params={"q": str(qid)},
                         help=QS[qid]["title"])
