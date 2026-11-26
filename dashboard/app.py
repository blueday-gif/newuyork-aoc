import streamlit as st

st.set_page_config(
    page_title="뉴욕시 311 Tract 분석",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("app_pages/overview.py", title="개요", icon=":material/dashboard:", default=True),
    st.Page("app_pages/quality.py", title="데이터 품질", icon=":material/fact_check:"),
    st.Page("app_pages/types.py", title="민원 유형", icon=":material/category:"),
    st.Page("app_pages/relationship.py", title="사회경제 관계", icon=":material/query_stats:"),
    st.Page("app_pages/predict.py", title="민원율 예측", icon=":material/model_training:"),
    st.Page("app_pages/compose.py", title="민원 구성", icon=":material/donut_small:"),
    st.Page("app_pages/map_page.py", title="공간 분포", icon=":material/map:"),
    st.Page("app_pages/stories.py", title="100가지 질문", icon=":material/quiz:", url_path="stories"),
]
st.navigation(pages).run()
