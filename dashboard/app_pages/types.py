import altair as alt
import streamlit as st

from dash_common import borough_short, table

st.title("민원 유형")
st.caption("Complaint Type을 생활환경 범주로 다시 묶었다. 매핑표는 data/processed/category_map.csv이다.")

summary = table("plan02_category_summary.csv").sort_values("n", ascending=False)
composition = table("plan02_borough_category.csv")
composition["자치구"] = borough_short(composition["borough_label"])
other = table("plan02_other_top.csv")
monthly = table("plan02_monthly.csv")
noise = table("plan02_noise_dow_hour.csv")

with st.container(border=True):
    st.subheader("범주별 건수")
    st.bar_chart(
        summary,
        x="category",
        y="n",
        x_label="범주",
        y_label="민원 건수",
        sort=False,
        alt="재분류 범주별 민원 건수",
    )
    other_share = float(summary.loc[summary["category"] == "기타", "share"].sum())
    st.caption(f"기타 비율은 {other_share * 100:.1f}%다. 상하수도, 노숙, 수목처럼 위 여섯 범주에 넣지 않은 유형이 여기 남는다.")

with st.container(border=True):
    st.subheader("자치구별 구성")
    chart = (
        alt.Chart(composition)
        .mark_bar()
        .encode(
            x=alt.X("자치구:N", title="자치구"),
            y=alt.Y("n:Q", stack="normalize", title="구성비", axis=alt.Axis(format="%")),
            color=alt.Color("category:N", title="범주"),
            tooltip=["자치구", "category", "n"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, width="stretch", alt="자치구별 민원 범주 구성비")

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("기타에 남은 유형")
        st.dataframe(other, hide_index=True, width="stretch", alt="기타 범주 상위 유형")
with right:
    with st.container(border=True):
        st.subheader("주거 민원의 월별 건수")
        st.line_chart(
            monthly,
            x="label",
            y="housing",
            x_label="연월",
            y_label="주거환경 민원 건수",
            alt="월별 주거환경 민원",
        )
        st.caption("난방 시즌(10월–5월)과 겹치는지 보는 한 해의 패턴이다.")

with st.container(border=True):
    st.subheader("소음 민원의 요일·시간")
    heat = (
        alt.Chart(noise)
        .mark_rect()
        .encode(
            x=alt.X("created_hour:O", title="시각"),
            y=alt.Y("created_dow:O", title="요일 (1=월 … 7=일)"),
            color=alt.Color("noise:Q", title="소음 민원 수", scale=alt.Scale(scheme="blues")),
            tooltip=["created_dow", "created_hour", "noise"],
        )
        .properties(height=240)
    )
    st.altair_chart(heat, width="stretch", alt="요일과 시간대별 소음 민원 수")
    st.caption("소음 가운데 22시–5시는 45%, 토·일은 40%다. 시간을 고르게 보면 각각 33%, 29%다. 주거 민원의 79%는 난방 시즌에 해당하는 달에 있다. 한 해의 관측이다.")
