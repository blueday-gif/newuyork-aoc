import altair as alt
import geopandas as gpd
import numpy as np
import pandas as pd
import streamlit as st
from altair.utils.data import to_values

from dash_common import BOROUGH_SHORT, MAP_PATH

st.title("공간 분포")
st.caption(
    "인구 1,000명 이상 Tract에서 군집(LISA)과 핫스팟(Gi*)을 계산했다. "
    "순열은 999회이고, 색이 있는 군집·핫스팟은 FDR 5%다. "
    "맞닿은 이웃이 없는 Tract는 가까운 4개를 이웃으로 넣었다. "
    "인구 1,000명 미만은 회색이다."
)


@st.cache_resource
def _load_map(_mtime_ns: int):
    geo = gpd.read_file(MAP_PATH)
    geo["GEOID"] = geo["GEOID"].astype(str)
    geo["자치구"] = geo["borough"].map(BOROUGH_SHORT).fillna(geo["borough"])
    return geo


def load_map():
    return _load_map(MAP_PATH.stat().st_mtime_ns)


geo = load_map()
stable = geo.loc[geo["total_pop"] >= 1000]

with st.sidebar:
    boroughs = ["전체"] + sorted(geo["자치구"].dropna().unique())
    picked = st.selectbox("자치구", boroughs)
    layer = st.selectbox(
        "지도에 올릴 값",
        ["민원율", "소음", "주거", "위생", "임차 비율", "중위소득", "임차 계수", "예측 잔차", "민원 구성", "인접 권역", "군집", "군집(보정 전)", "핫스팟"],
    )

view = geo if picked == "전체" else geo.loc[geo["자치구"] == picked]
low_pop = alt.datum.total_pop < 1000


def rate_color(field: str, title: str, domain: list[float], scheme: str) -> alt.Color:
    return alt.condition(
        low_pop,
        alt.value("#e6e6e6"),
        alt.Color(
            f"{field}:Q",
            title=title,
            scale=alt.Scale(scheme=scheme, domain=domain, clamp=True),
        ),
    )


if layer == "민원율":
    color = rate_color("complaints_per_1k", "1,000명당 민원", [0, 1200], "blues")
elif layer == "소음":
    cap = float(stable["noise_rate"].quantile(0.95))
    color = rate_color("noise_rate", "1,000명당 소음", [0, cap], "purples")
elif layer == "주거":
    cap = float(stable["housing_rate"].quantile(0.95))
    color = rate_color("housing_rate", "1,000명당 주거", [0, cap], "oranges")
elif layer == "위생":
    cap = float(stable["sanitation_rate"].quantile(0.95))
    color = rate_color("sanitation_rate", "1,000명당 위생", [0, cap], "greens")
elif layer == "임차 비율":
    color = rate_color("renter_rate", "임차 가구 비율", [0, 1], "oranges")
elif layer == "중위소득":
    cap = float(stable["median_income"].quantile(0.95))
    color = rate_color("median_income", "중위 가구소득", [0, cap], "tealblues")
elif layer == "임차 계수":
    vals = geo["gwr_renter_10pp"].dropna()
    span = float(np.nanmax(np.abs(vals.quantile([0.05, 0.95]))))
    span = max(span, 1.0)
    color = alt.condition(
        "datum.gwr_renter_10pp == null || datum.total_pop < 1000",
        alt.value("#e6e6e6"),
        alt.Color(
            "gwr_renter_10pp:Q",
            title="임차 10%p 지역 계수",
            scale=alt.Scale(scheme="redblue", domain=[-span, span], reverse=True, clamp=True),
        ),
    )
elif layer == "예측 잔차":
    vals = geo["oof_residual"].dropna()
    span = float(np.nanmax(np.abs(vals.quantile([0.05, 0.95]))))
    span = max(span, 1.0)
    color = alt.condition(
        "datum.oof_residual == null || datum.total_pop < 1000",
        alt.value("#e6e6e6"),
        alt.Color(
            "oof_residual:Q",
            title="실제−예측",
            scale=alt.Scale(scheme="redblue", domain=[-span, span], reverse=True, clamp=True),
        ),
    )
elif layer == "민원 구성":
    color = alt.condition(
        "datum.complaint_type == null || datum.total_pop < 1000",
        alt.value("#e6e6e6"),
        alt.Color("complaint_type:N", title="민원 구성", scale=alt.Scale(scheme="category10")),
    )
elif layer == "인접 권역":
    color = alt.condition(
        "datum.region_name == null || datum.total_pop < 1000",
        alt.value("#e6e6e6"),
        alt.Color("region_name:N", title="인접 권역", scale=alt.Scale(scheme="category20")),
    )
elif layer == "군집":
    color = alt.Color(
        "lisa:N",
        title="LISA, FDR",
        scale=alt.Scale(
            domain=["HH", "LL", "HL", "LH", "ns", "제외"],
            range=["#b3403a", "#3d5a80", "#e0a106", "#6a9a7a", "#d5dbe3", "#f4f6fa"],
        ),
    )
elif layer == "군집(보정 전)":
    color = alt.Color(
        "lisa_p05:N",
        title="LISA, 보정 전",
        scale=alt.Scale(
            domain=["HH", "LL", "HL", "LH", "ns", "제외"],
            range=["#b3403a", "#3d5a80", "#e0a106", "#6a9a7a", "#d5dbe3", "#f4f6fa"],
        ),
    )
else:
    color = alt.Color(
        "gi:N",
        title="Gi*",
        scale=alt.Scale(
            domain=["hot", "cold", "ns", "제외"],
            range=["#b3403a", "#3d5a80", "#d5dbe3", "#f4f6fa"],
        ),
    )

# GeoDataFrame을 그대로 넘기면 Streamlit이 geometry를 WKT 문자열로 바꿔 폴리곤이 안 그려진다.
chart = (
    alt.Chart(to_values(view))
    .mark_geoshape(stroke="white", strokeWidth=0.15)
    .encode(
        color=color,
        tooltip=[
            "GEOID:N",
            "자치구:N",
            alt.Tooltip("complaints_per_1k:Q", title="1,000명당", format=".0f"),
            alt.Tooltip("noise_rate:Q", title="소음", format=".0f"),
            alt.Tooltip("housing_rate:Q", title="주거", format=".0f"),
            alt.Tooltip("sanitation_rate:Q", title="위생", format=".0f"),
            alt.Tooltip("renter_rate:Q", title="임차 비율", format=".0%"),
            alt.Tooltip("median_income:Q", title="중위소득", format="$,.0f"),
            alt.Tooltip("total_pop:Q", title="인구", format=",.0f"),
            *([alt.Tooltip("gwr_renter_10pp:Q", title="임차 10%p 지역 계수", format=".0f")] if "gwr_renter_10pp" in geo.columns else []),
            *([alt.Tooltip("oof_residual:Q", title="실제−예측", format=".0f")] if "oof_residual" in geo.columns else []),
            *(["complaint_type:N"] if "complaint_type" in geo.columns else []),
            *(["region_name:N"] if "region_name" in geo.columns else []),
            "lisa:N",
            "lisa_p05:N",
            "gi:N",
        ],
    )
    .project(type="mercator")
    .properties(height=640)
)
st.altair_chart(chart, width="stretch", alt="Census Tract 민원율, 유형, 군집 지도")
if layer == "민원율":
    st.caption("색은 1,000명당 1,200건에서 고정된다. 그 이상인 Tract는 가장 진한 색이고, 마우스를 올리면 실제 값이 나온다.")
elif layer in {"소음", "주거", "위생", "중위소득"}:
    st.caption("색의 상한은 인구 1,000명 이상 Tract의 95백분위다. 그 이상은 가장 진한 색이다.")
elif layer == "임차 계수":
    st.caption("색은 그 Tract 주변에서 추정한 임차율 10%p 계수다. 네 설명변수가 같은 이웃 수를 쓴다.")
elif layer == "예측 잔차":
    st.caption("색은 공간 교차검증에서 실제 민원율에서 LightGBM 예측을 뺀 값이다. 붉은색은 사회경제 변수로 설명한 것보다 신고가 많은 Tract다.")
elif layer == "민원 구성":
    st.caption("색은 민원 유형 비율로 나눈 묶음이다. 소득과 임차율은 묶음을 만드는 데 쓰지 않았다.")
elif layer == "인접 권역":
    st.caption("색은 자치구 안에서 맞닿은 Tract만 묶은 권역이다. 민원 구성 유형과는 별개다.")
elif layer == "군집":
    n_sig = int(geo["lisa"].isin(["HH", "LL", "HL", "LH"]).sum())
    if n_sig == 0:
        st.caption("이 색은 FDR 5%다. 순열 p의 하한이 0.001이고 Tract가 2천 개가 넘어, 개별 Tract는 이 기준을 통과하지 못한다.")
    else:
        st.caption(f"이 색은 FDR 5%다. 유의한 Tract는 {n_sig:,}개다.")
elif layer == "군집(보정 전)":
    st.caption("이 색은 순열 p 5%이고 다중검정 보정이 없다. 전역 군집의 위치를 보는 용도다.")

if layer == "군집":
    rows = view.loc[view["lisa"] == "HH"]
    title = "이 화면의 High-High Tract"
elif layer == "군집(보정 전)":
    rows = view.loc[view["lisa_p05"] == "HH"]
    title = "이 화면의 보정 전 High-High Tract"
elif layer == "핫스팟":
    rows = view.loc[view["gi"] == "hot"]
    title = "이 화면의 Gi* 핫스팟"
else:
    rows = view.iloc[0:0]
    title = ""

if title:
    table = pd.DataFrame(
        rows[["GEOID", "자치구", "complaints_per_1k", "renter_rate", "total_pop"]]
    ).drop(columns=["geometry"], errors="ignore")
    with st.container(border=True):
        st.subheader(title)
        st.dataframe(
            table.sort_values("complaints_per_1k", ascending=False),
            hide_index=True,
            width="stretch",
            alt=title,
            column_config={
                "complaints_per_1k": st.column_config.NumberColumn("1,000명당", format="%.0f"),
                "renter_rate": st.column_config.NumberColumn("임차 비율", format="%.0%"),
                "total_pop": st.column_config.NumberColumn("인구", format="%d"),
            },
        )
