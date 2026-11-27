"""체험실: 작은 분모·보고 편향 시뮬레이터를 한곳에서 움직인다."""
import streamlit as st

import qlib
from components import labs

st.title("체험실")
st.caption("통계 개념을 직접 움직여 본다. 슬라이더를 바꾸면 이 상자만 다시 그려진다.")

lab_users: dict[str, list[int]] = {}
for qid in qlib.questions():
    c = qlib.content(qid)
    if c and c.get("lab"):
        lab_users.setdefault(c["lab"], []).append(qid)

for lab_key, (title, _) in labs.LABS.items():
    st.subheader(title, divider="gray")
    labs.render(lab_key, key=f"page_{lab_key}")
    qids = lab_users.get(lab_key, [])
    if qids:
        with st.container(horizontal=True, gap="small"):
            for qid in qids:
                st.page_link(
                    "app_pages/question.py",
                    label=f"{qid}번",
                    query_params={"q": str(qid)},
                )
