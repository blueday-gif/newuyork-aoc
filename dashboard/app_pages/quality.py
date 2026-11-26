import streamlit as st

from dash_common import table

st.title("데이터 품질")
st.caption("극단값은 지우지 않고, 포함했을 때와 뺐을 때를 따로 본다.")

summary = table("plan02_outlier_summary.csv").iloc[0]
missing_borough = table("plan02_missing_by_borough.csv")
missing_type = table("plan02_missing_by_type.csv")
addresses = table("plan02_outlier_addresses.csv")
problems = table("plan02_outlier_problems.csv")
sens = table("plan02_sensitivity.csv")

with st.container(horizontal=True):
    st.metric("극단 Tract", summary["GEOID"], border=True)
    st.metric("해당 Tract 민원", f"{int(summary['complaints']):,}", border=True)
    st.metric("최다 주소 비중", f"{summary['top_address_share'] * 100:.1f}%", border=True)

st.info(
    f"최다 유형은 {summary['top_problem']} ({summary['top_problem_share'] * 100:.1f}%)이고, "
    f"최다 주소는 {summary['top_address']}이다. "
    f"시스템 중복 플래그는 이 Tract {summary['duplicate_flag_rate'] * 100:.2f}%, "
    f"시 전체 {summary['city_duplicate_flag_rate'] * 100:.2f}%다.",
    title="Bronx 36005042000",
)

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("이 Tract의 주소 집중")
        st.dataframe(addresses, hide_index=True, width="stretch", alt="극단 Tract 상위 주소")
with right:
    with st.container(border=True):
        st.subheader("이 Tract의 민원 유형")
        st.bar_chart(
            problems.head(8),
            x="problem",
            y="n",
            x_label="민원 유형",
            y_label="건수",
            alt="극단 Tract 상위 민원 유형",
        )

with st.container(border=True):
    st.subheader("좌표 결측")
    st.dataframe(
        missing_borough,
        hide_index=True,
        width="stretch",
        alt="자치구별 좌표 결측",
        column_config={"missing_pct": st.column_config.NumberColumn("결측 비율(%)", format="%.1f")},
    )
    st.caption("건수 5,000건 이상 유형 가운데 좌표 결측 비율이 높은 유형.")
    st.dataframe(
        missing_type.head(12),
        hide_index=True,
        width="stretch",
        alt="유형별 좌표 결측 상위",
        column_config={"missing_pct": st.column_config.NumberColumn("결측 비율(%)", format="%.1f")},
    )

with st.container(border=True):
    st.subheader("인구 기준과 극단 Tract를 바꿨을 때")
    view = sens.copy()
    view["규칙"] = view.apply(
        lambda row: f"인구 {int(row.pop_min):,}명 이상"
        + (" · 극단 Tract 제외" if row.drop_outlier else " · 극단 Tract 포함"),
        axis=1,
    )
    st.dataframe(
        view[
            [
                "규칙",
                "n_renter",
                "renter_rho",
                "renter_ols_per_10pp",
                "income_rho",
                "r_squared",
            ]
        ],
        hide_index=True,
        width="stretch",
        alt="인구 기준과 극단값 제외에 따른 임차율 연관",
        column_config={
            "n_renter": st.column_config.NumberColumn("Tract 수", format="%d"),
            "renter_rho": st.column_config.NumberColumn("임차 Spearman", format="%.2f"),
            "renter_ols_per_10pp": st.column_config.NumberColumn(
                "OLS, 임차 10%p당 민원", format="%.1f"
            ),
            "income_rho": st.column_config.NumberColumn("소득 Spearman", format="%.2f"),
            "r_squared": st.column_config.NumberColumn("OLS R²", format="%.2f"),
        },
    )
    st.caption("OLS는 자치구 고정효과와 HC1 표준오차를 쓴다. 임차 계수는 비율이 0.1 증가할 때의 1,000명당 민원 수다.")
