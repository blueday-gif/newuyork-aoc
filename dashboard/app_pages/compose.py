import streamlit as st

from dash_common import ROOT, table

st.title("민원 구성")
st.caption(
    "인구 1,000명 이상이고 민원이 1건 이상인 Tract를 민원 유형 비율로 묶었다. "
    "소득과 임차율은 묶음을 만든 뒤에 비교한 값이다."
)

profile = table("plan05c_profile.csv")
tests = table("plan05c_kruskal.csv")
anomalies = table("plan05c_anomaly.csv")
share_cols = [column for column in ("소음", "주거", "위생", "도로", "해충", "건축") if column in profile.columns]
st.dataframe(
    profile[["complaint_type", "tracts", "rate_median", "income_median", "renter_median", *share_cols]],
    hide_index=True,
    width="stretch",
    alt="민원 구성 유형별 중앙값",
    column_config={
        "complaint_type": "유형",
        "tracts": st.column_config.NumberColumn("Tract", format="%d"),
        "rate_median": st.column_config.NumberColumn("민원율 중앙값", format="%.0f"),
        "income_median": st.column_config.NumberColumn("중위소득", format="$%.0f"),
        "renter_median": st.column_config.NumberColumn("임차율", format="%.0%"),
        **{column: st.column_config.NumberColumn(format="%.0%") for column in share_cols},
    },
)
income = tests.loc[tests["variable"] == "중위소득"].iloc[0]
renter = tests.loc[tests["variable"] == "임차율"].iloc[0]
st.caption(
    f"유형 간 중위소득 Kruskal-Wallis ε²는 {income.epsilon_squared:.3f}, "
    f"임차율 ε²는 {renter.epsilon_squared:.3f}이다."
)
st.image(
    str(ROOT / "outputs" / "figures" / "plan05c_pca.png"),
    caption="주성분 두 축은 구성 분산의 30.9%와 21.0%다. 가우시안 혼합 BIC는 8개에서 가장 낮고, 발표 유형은 실루엣이 가장 높은 4개다.",
)

st.subheader("구성이 특이한 Tract")
st.caption("Isolation Forest가 민원율과 유형 비율이 드문 조합으로 표시한 Tract다. 분석에서 빼지 않았다.")
st.dataframe(
    anomalies,
    hide_index=True,
    width="stretch",
    alt="이상 Tract",
    column_config={
        "complaints_per_1k": st.column_config.NumberColumn("1,000명당", format="%.0f"),
        **{column: st.column_config.NumberColumn(format="%.0%") for column in share_cols if column in anomalies.columns},
    },
)
