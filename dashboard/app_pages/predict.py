import pandas as pd
import streamlit as st

from dash_common import ROOT, table

st.title("민원율 예측")
st.caption(
    "인구 1,000명 이상 Tract. 타깃은 1,000명당 민원율이고, 학습 가중치는 인구다. "
    "설명변수는 소득, 임차율, 밀도, 빈곤율, 주택 연령, 1950년 이전 비율, 자치구다. "
    "민원 건수와 유형 비율, 이웃 민원율, 좌표는 넣지 않았다. "
    "공간 블록은 가까운 Tract를 한 검증 묶음으로 둔다."
)

summary = table("plan05a_cv_summary.csv")
summary["drop_outlier"] = summary["drop_outlier"].astype(str).str.lower().isin(["true", "1"])
drop_outlier = st.toggle("극단 Tract를 빼고 보기", value=False)
view = summary.loc[summary["drop_outlier"] == drop_outlier].copy()
labels = {
    "dummy": "인구 가중 평균",
    "poisson": "Poisson 회귀",
    "forest": "랜덤포레스트",
    "hgb": "HistGradientBoosting",
    "lightgbm": "LightGBM",
    "spatial_block": "공간 블록",
    "random_kfold": "무작위 5겹",
    "borough_holdout": "자치구 제외",
}
view["모형"] = view["model"].map(labels)
view["검증"] = view["scheme"].map(labels)
order = ["인구 가중 평균", "Poisson 회귀", "랜덤포레스트", "HistGradientBoosting", "LightGBM"]
scheme_order = ["공간 블록", "무작위 5겹", "자치구 제외"]
view["모형"] = pd.Categorical(view["모형"], order, ordered=True)
view["검증"] = pd.Categorical(view["검증"], scheme_order, ordered=True)
view = view.sort_values(["검증", "모형"])

st.dataframe(
    view[
        [
            "검증",
            "모형",
            "d2_mean",
            "d2_std",
            "mae_mean",
            "spearman_mean",
            "top20_mean",
            "deviance_mean",
        ]
    ],
    hide_index=True,
    width="stretch",
    alt="모형과 검증 방식별 교차검증 성능",
    column_config={
        "d2_mean": st.column_config.NumberColumn("D²", format="%.3f"),
        "d2_std": st.column_config.NumberColumn("D² 표준편차", format="%.3f"),
        "mae_mean": st.column_config.NumberColumn("MAE", format="%.0f"),
        "spearman_mean": st.column_config.NumberColumn("Spearman", format="%.2f"),
        "top20_mean": st.column_config.NumberColumn("상위 20% 적중", format="%.0%"),
        "deviance_mean": st.column_config.NumberColumn("Poisson deviance", format="%.1f"),
    },
)

st.subheader("회귀 계수와 예측 기여")
st.caption(
    "회귀는 임차율, 소득, 밀도, 빈곤, 자치구를 넣은 선형 모형의 HC1 계수다. "
    "기여는 로그 민원율 척도이고, 중앙값 이상인 Tract의 평균에서 미만의 평균을 뺀 부호다. "
    "부분의존은 그 변수만 바꾸고 나머지 관측값은 그대로 둔 평균 예측이다. "
    "중위소득의 이변량 순위 상관은 음수다."
)
compared = table("plan05b_compare.csv")
st.dataframe(
    compared,
    hide_index=True,
    width="stretch",
    alt="회귀 계수와 LightGBM 기여, 부분의존 비교",
    column_config={
        "SHAP_높은쪽차이": st.column_config.NumberColumn("기여 차이", format="%.3f"),
        "PDP_시작": st.column_config.NumberColumn("부분의존 시작", format="%.0f"),
        "PDP_끝": st.column_config.NumberColumn("부분의존 끝", format="%.0f"),
        "PDP_형태": "부분의존 형태",
        "방향": "방향 비교",
    },
)
figures = ROOT / "outputs" / "figures"
left, right = st.columns(2)
left.image(str(figures / "plan05b_shap.png"), caption="변수별 평균 절대 기여")
right.image(str(figures / "plan05b_outlier_shap.png"), caption="36005042000의 로그 민원율 기여")
st.image(str(figures / "plan05b_pdp.png"), caption="변수별 부분의존")
ale = figures / "plan06_ale.png"
dependence = figures / "plan06_shap_renter.png"
if ale.exists():
    st.image(str(ale), caption="누적 국소효과. 이웃한 값 구간 안에서만 그 변수를 바꿨다.")
if dependence.exists():
    st.image(str(dependence), caption="임차율 기여. 색은 중위소득이고, 기여는 로그 민원율 척도다.")
