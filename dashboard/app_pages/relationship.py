import streamlit as st

from dash_common import BOROUGH_SHORT, TABLES, table

st.title("사회경제적 특성과 민원율")
st.caption(
    "인구 1,000명 이상 Tract. Spearman은 순위 상관이고, p값은 Benjamini–Hochberg로 보정했다. "
    "빈곤율은 B17001, 1950년 이전 주택 비율은 B25034, 주택 연령은 2024년에서 중위 건축연도(B25035)를 뺀 값이다."
)

corr = table("plan02_correlations.csv")
quint = table("plan02_quintiles.csv")
ols = table("plan02_ols.csv")
counts = table("plan02_count_model.csv")
kw = table("plan02_kruskal.csv").iloc[0]
moran = table("plan02_moran.csv").iloc[0]
tracts = table("plan02_tracts.csv")
stable = tracts.loc[tracts["stable"] == True].copy()  # noqa: E712

labels = {
    "median_income": "중위소득",
    "renter_rate": "임차 비율",
    "pop_density": "인구밀도",
    "poverty_rate": "빈곤율",
    "pre1950_share": "1950년 이전 주택 비율",
    "housing_age": "주택 연령",
}
corr["변수"] = corr["variable"].map(labels).fillna(corr["variable"])
corr["집단"] = corr["group"].replace(BOROUGH_SHORT)

with st.container(horizontal=True):
    city = corr.query("group == '시 전체' and variable == 'renter_rate' and outcome == '전체 민원율'").iloc[0]
    st.metric("임차율과 민원율 Spearman", f"{city.rho:.2f}", border=True)
    st.metric("Kruskal-Wallis ε²", f"{kw.epsilon_squared:.3f}", border=True)
    st.metric("Moran's I", f"{moran.moran_i:.3f}", border=True)
    st.metric("FDR High-High", f"{int(moran.hh)}", border=True)

h4 = corr.query("group == '시 전체' and variable == 'poverty_rate' and outcome == '위생 민원율'").iloc[0]
h5_old = corr.query("group == '시 전체' and variable == 'pre1950_share' and outcome == '주거 민원율'").iloc[0]
h5_age = corr.query("group == '시 전체' and variable == 'housing_age' and outcome == '주거 민원율'").iloc[0]
with st.container(horizontal=True):
    st.metric("H4 빈곤율–위생 ρ", f"{h4.rho:.2f}", border=True)
    st.metric("H5 1950년 이전–주거 ρ", f"{h5_old.rho:.2f}", border=True)
    st.metric("H5 주택 연령–주거 ρ", f"{h5_age.rho:.2f}", border=True)

st.info(
    f"인구 1,000명 이상 Tract {int(moran.n):,}개에서 Moran's I는 {moran.moran_i:.3f} "
    f"(순열 {int(moran.perms)}회, p={moran.p_value_perm:.3f})이다. "
    f"FDR 5%에서 High-High {int(moran.hh)}개, Low-Low {int(moran.ll)}개다. "
    f"보정 전 5%에서는 High-High {int(moran.hh_p05)}개, Low-Low {int(moran.ll_p05)}개다. "
    f"Gi* 핫스팟은 {int(moran.gi_hot)}개, 콜드스팟은 {int(moran.gi_cold)}개다.",
    title="민원율은 이웃 Tract와 함께 높다",
)

with st.container(border=True):
    st.subheader("순위 상관")
    st.dataframe(
        corr[["집단", "outcome", "변수", "n", "rho", "p_value", "p_fdr", "fdr_reject_0_05"]],
        hide_index=True,
        width="stretch",
        alt="민원율과 사회경제 변수의 Spearman 상관",
        column_config={
            "outcome": "결과",
            "n": st.column_config.NumberColumn("Tract", format="%d"),
            "rho": st.column_config.NumberColumn("ρ", format="%.2f"),
            "p_value": st.column_config.NumberColumn("p", format="%.3g"),
            "p_fdr": st.column_config.NumberColumn("FDR p", format="%.3g"),
            "fdr_reject_0_05": "FDR 5%에서 기각",
        },
    )

income_q = quint.loc[quint["variable"] == "median_income"]
renter_q = quint.loc[quint["variable"] == "renter_rate"]
left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("소득 5분위, 인구 가중 민원율")
        st.bar_chart(
            income_q,
            x="quintile",
            y="pop_weighted_per_1k",
            x_label="소득 분위 (Q1=낮음)",
            y_label="인구 1,000명당 민원",
            alt="소득 5분위별 인구 가중 민원율",
        )
with right:
    with st.container(border=True):
        st.subheader("임차 비율 5분위, 인구 가중 민원율")
        st.bar_chart(
            renter_q,
            x="quintile",
            y="pop_weighted_per_1k",
            x_label="임차 비율 분위 (Q1=낮음)",
            y_label="인구 1,000명당 민원",
            alt="임차 비율 5분위별 인구 가중 민원율",
        )

poverty_q = quint.loc[quint["variable"] == "poverty_rate"]
pre1950_q = quint.loc[quint["variable"] == "pre1950_share"]
left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("빈곤율 5분위, 인구 가중 위생 민원율")
        st.bar_chart(
            poverty_q,
            x="quintile",
            y="pop_weighted_per_1k",
            x_label="빈곤율 분위 (Q1=낮음)",
            y_label="인구 1,000명당 위생 민원",
            alt="빈곤율 5분위별 인구 가중 위생 민원율",
        )
        st.caption("가설 H4. 막대는 전체 민원율이 아니라 위생 민원율이다.")
with right:
    with st.container(border=True):
        st.subheader("1950년 이전 주택 5분위, 인구 가중 주거 민원율")
        st.bar_chart(
            pre1950_q,
            x="quintile",
            y="pop_weighted_per_1k",
            x_label="1950년 이전 비율 분위 (Q1=낮음)",
            y_label="인구 1,000명당 주거 민원",
            alt="1950년 이전 주택 비율 5분위별 인구 가중 주거 민원율",
        )
        st.caption(
            "가설 H5. 막대는 주거환경 민원율이다. "
            "중위 건축연도는 1939년 이전 구간이 1938로 바닥이 찍혀, 주택 연령 상관은 이 비율보다 약하다."
        )

sample = stable.dropna(subset=["renter_rate", "complaints_per_1k"])
with st.container(border=True):
    st.subheader("Tract 임차 비율과 민원율")
    st.scatter_chart(
        sample,
        x="renter_rate",
        y="complaints_per_1k",
        color="borough",
        x_label="임차 가구 비율",
        y_label="인구 1,000명당 민원",
        alt="인구 1,000명 이상 Tract의 임차 비율과 민원율",
    )

full_ols = ols.loc[ols["model"] == "full_borough"]
renter_cmp = ols.loc[ols["term"] == "renter_rate"].copy()
renter_cmp["모형"] = renter_cmp["model"].map(
    {
        "core_borough": "임차·소득·자치구",
        "full": "임차·소득·밀도·빈곤",
        "full_borough": "계획서 식",
    }
)
renter_cmp["임차 10%p"] = renter_cmp["coef"] * 0.1
with st.container(border=True):
    st.subheader("계획서 식 선형 모형")
    st.caption(
        f"종속변수는 1,000명당 민원. R² {full_ols['r_squared'].iloc[0]:.2f}, "
        f"n={int(full_ols['n'].iloc[0]):,}. 표준오차는 HC1이다. "
        "임차율·빈곤율 계수는 0에서 1로 갈 때의 변화라 10%p는 계수의 0.1배다. "
        "density_10k는 1만 명/km²이고, 1,000명/km²는 계수의 0.1배다."
    )
    st.dataframe(
        renter_cmp[["모형", "임차 10%p", "r_squared", "n", "vif"]],
        hide_index=True,
        width="stretch",
        alt="모형별 임차율 10%p 계수",
        column_config={
            "임차 10%p": st.column_config.NumberColumn(format="%.1f"),
            "r_squared": st.column_config.NumberColumn("R²", format="%.3f"),
            "n": st.column_config.NumberColumn("Tract", format="%d"),
            "vif": st.column_config.NumberColumn("임차율 VIF", format="%.2f"),
        },
    )
    st.dataframe(
        full_ols[["term", "coef", "se", "p_value", "ci_low", "ci_high", "vif"]],
        hide_index=True,
        width="stretch",
        alt="계획서 식 OLS 계수",
        column_config={
            "coef": st.column_config.NumberColumn(format="%.2f"),
            "se": st.column_config.NumberColumn(format="%.2f"),
            "p_value": st.column_config.NumberColumn(format="%.3g"),
            "ci_low": st.column_config.NumberColumn(format="%.2f"),
            "ci_high": st.column_config.NumberColumn(format="%.2f"),
            "vif": st.column_config.NumberColumn(format="%.2f"),
        },
    )

spatial = table("plan02_residual_spatial.csv")
residual = spatial.loc[
    (spatial["estimator"] == "residual_moran") & (spatial["term"] == "moran_i")
].iloc[0]
sar = spatial.loc[(spatial["estimator"] == "sar_2sls") & (spatial["term"] == "Wy")].iloc[0]
with st.container(border=True):
    st.subheader("잔차의 공간 상관")
    st.caption(
        f"계획서 식 잔차의 Moran's I는 {residual.estimate:.3f} "
        f"(n={int(residual.n):,}, 순열 p={residual.p_value:.3f})이다. "
        f"공간시차 ρ는 {sar.estimate:.3f}이다. "
        "이웃 민원율을 넣어도 임차율 계수는 양수로 남는다."
    )

if (TABLES / "plan02_gwr_summary.csv").exists():
    gwr = table("plan02_gwr_summary.csv")
    shown = gwr.loc[gwr["term"] != "Intercept"].copy()
    shown["변수"] = shown["term"].map(
        {
            "renter_rate": "임차 10%p",
            "income_10k": "소득 1만 달러",
            "density_10k": "밀도 1,000명/km²",
            "poverty_rate": "빈곤 10%p",
        }
    )
    for column in ("global_coef", "local_p10", "local_p50", "local_p90"):
        shown[column] = shown[column] * shown["effect_scale"]
    head = gwr.iloc[0]
    with st.container(border=True):
        st.subheader("지역마다 다른 계수")
        st.caption(
            f"가까운 {int(head.bandwidth_k)}개 Tract에 이중제곱 가중을 둔 지역 가중 회귀다. "
            f"이웃 수는 AICc가 가장 작은 후보다. "
            f"GWR AICc {head.aicc:.0f}, 전역 식 AICc {head.aicc_ols:.0f}. "
            "표의 값은 임차·빈곤 10%p, 소득 1만 달러, 밀도 1,000명/km² 기준이다."
        )
        st.dataframe(
            shown[["변수", "global_coef", "local_p10", "local_p50", "local_p90", "share_positive"]],
            hide_index=True,
            width="stretch",
            alt="지역 가중 회귀 계수 분포",
            column_config={
                "global_coef": st.column_config.NumberColumn("전역", format="%.1f"),
                "local_p10": st.column_config.NumberColumn("10백분위", format="%.1f"),
                "local_p50": st.column_config.NumberColumn("중앙값", format="%.1f"),
                "local_p90": st.column_config.NumberColumn("90백분위", format="%.1f"),
                "share_positive": st.column_config.NumberColumn("양수 비율", format="%.0%"),
            },
        )

with st.container(border=True):
    family = counts["family"].iloc[0]
    dispersion = counts["dispersion_pearson"].iloc[0]
    st.subheader(f"건수 모형 ({family})")
    st.caption(
        f"인구 1,000명을 offset으로 둔 계획서 식이다. Poisson Pearson 산포는 {dispersion:.1f}이다. "
        "irr_per_10pp_or_10k는 임차·빈곤 10%p, 소득 1천 달러, 인구밀도 1,000명/km²당 발생률비다."
    )
    st.dataframe(
        counts[["term", "coef", "irr", "irr_per_10pp_or_10k", "p_value", "ci_low", "ci_high"]],
        hide_index=True,
        width="stretch",
        alt="카운트 모형 계수와 발생률비",
        column_config={
            "coef": st.column_config.NumberColumn(format="%.3f"),
            "irr": st.column_config.NumberColumn(format="%.3f"),
            "irr_per_10pp_or_10k": st.column_config.NumberColumn(format="%.3f"),
            "p_value": st.column_config.NumberColumn(format="%.3g"),
            "ci_low": st.column_config.NumberColumn(format="%.3f"),
            "ci_high": st.column_config.NumberColumn(format="%.3f"),
        },
    )
