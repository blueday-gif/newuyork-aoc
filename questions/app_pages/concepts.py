"""개념 사전: 여러 문항이 함께 쓰는 통계·311·뉴욕·데이터 개념."""
import streamlit as st

import qlib

QS, CONCEPTS, USERS = qlib.questions(), qlib.concepts(), qlib.concept_users()

st.title("개념 사전")
st.caption("문항 해설에서 반복해서 나오는 기초 지식을 한곳에 모았다.")

kinds = sorted({c["kind"] for c in CONCEPTS.values()})
pick = st.segmented_control("분류", ["전체"] + kinds, default="전체", key="c_kind")

for key, card in CONCEPTS.items():
    if pick not in (None, "전체") and card["kind"] != pick:
        continue
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.badge(card["kind"], color="gray")
            st.markdown(f"**{card['title']}**")
        st.markdown(card["summary"])
        with st.expander("자세히"):
            st.markdown(card["body"])
        if USERS.get(key):
            with st.container(horizontal=True, gap="small"):
                for qid in USERS[key]:
                    st.page_link("app_pages/question.py", label=f"{qid}번", query_params={"q": str(qid)},
                                 help=QS[qid]["title"])
