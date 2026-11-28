"""100가지 질문으로 보는 뉴욕인의 삶 — 문항별 통계와 배경 지식.
실행(저장소 루트에서): streamlit run questions/app.py
"""
import streamlit as st

import qlib
import state

st.set_page_config(page_title="100가지 질문 · 뉴욕 311", page_icon=":material/quiz:", layout="wide")

pages = [
    st.Page("app_pages/index.py", title="목차", icon=":material/list:", default=True),
    st.Page("app_pages/question.py", title="질문 보기", icon=":material/help:", url_path="q"),
    st.Page("app_pages/concepts.py", title="개념 사전", icon=":material/menu_book:", url_path="concepts"),
    st.Page("app_pages/labs.py", title="체험실", icon=":material/science:", url_path="labs"),
    st.Page("app_pages/talks.py", title="발표후보", icon=":material/co_present:", url_path="talks"),
]
pg = st.navigation(pages)
pg.run()
state.render_sidebar(len(qlib.questions()), qlib.concepts())
