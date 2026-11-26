import pandas as pd
import streamlit as st

from dash_common import ROOT, borough_short, table

st.title("뉴욕시 311과 사회경제적 특성")
st.caption(
    "Census Tract 단위. 311은 2025-11-01–2026-10-31, ACS는 2024년 5개년 추정치. "
    "두 기간이 달라 아래 수치는 연관이지 같은 해의 인과가 아니다."
)

coverage = table("eda01_coverage.csv").iloc[0]
borough = table("eda01_borough.csv")
borough["자치구"] = borough_short(borough["borough"])
monthly = table("plan02_monthly.csv")

with st.container(horizontal=True):
    st.metric("전체 민원", f"{int(coverage['rows']):,}", border=True)
    st.metric("Tract에 배정", f"{int(coverage['in_tract']):,}", border=True)
    st.metric("인구 1,000명당", "457.4", border=True)
    st.metric("결합 Tract", "2,327", border=True)

st.warning(
    "좌표가 없는 민원 83,134건과 Tract 밖 221건은 민원율에서 빠진다. "
    "인구 1,000명 미만 132개 Tract는 상관·회귀·공간군집에서 제외한다.",
    title="집계에서 빠지는 민원",
)

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("자치구별 인구 1,000명당 민원")
        chart = borough.sort_values("complaints_per_1k", ascending=False)
        st.bar_chart(
            chart,
            x="자치구",
            y="complaints_per_1k",
            x_label="자치구",
            y_label="인구 1,000명당 민원 수",
            sort=False,
            alt="자치구별 인구 가중 민원율",
        )
with right:
    with st.container(border=True):
        st.subheader("월별 접수")
        st.line_chart(
            monthly,
            x="label",
            y=["complaints", "housing", "noise"],
            x_label="연월",
            y_label="민원 건수",
            alt="월별 전체·주거·소음 민원",
        )
        st.caption("complaints는 전체, housing은 주거환경, noise는 소음. 12개월만 있어 매년 반복된다고 보지 않는다.")

figures = ROOT / "outputs" / "figures"
log_hist = figures / "plan06_log_hist.png"
ecdf = figures / "plan06_ecdf.png"
if log_hist.exists() and ecdf.exists():
    left_fig, right_fig = st.columns(2)
    left_fig.image(str(log_hist), caption="인구 1,000명 이상 Tract의 로그 민원율. 오른쪽 꼬리는 극단 Tract다.")
    right_fig.image(str(ecdf), caption="자치구별 누적 분포. 가로축은 1,000명당 1,500건에서 자른다.")

with st.container(border=True):
    st.subheader("건수와 민원율")
    show = pd.DataFrame(
        {
            "자치구": borough["자치구"],
            "인구": borough["total_pop"].round().astype(int).map("{:,}".format),
            "민원 건수": borough["complaint_count"].round().astype(int).map("{:,}".format),
            "1,000명당": borough["complaints_per_1k"].map(lambda v: f"{v:.1f}"),
            "임차 비율": borough["renter_rate"].map(lambda v: f"{v * 100:.1f}%"),
        }
    )
    st.dataframe(
        show,
        hide_index=True,
        width="stretch",
        alt="자치구별 인구, 민원 건수, 민원율, 임차 비율",
    )
    st.caption("1,000명당 값은 민원 합을 인구 합으로 나눈 것이다. Tract 민원율의 단순 평균이 아니다.")
