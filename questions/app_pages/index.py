"""목차: 100문항을 부·유형·진행 상태로 거른다."""
import streamlit as st

import qlib

QS, PARTS = qlib.questions(), qlib.parts()

st.title("100가지 질문으로 보는 뉴욕인의 삶")
st.caption("311 민원 3,963,959건(2025-11 ~ 2026-10) · ACS 2024 5개년 · Census Tract 2,327개. "
           "311은 '일어난 문제'가 아니라 '신고된 문제'다.")

done = [q for q in QS if qlib.status(q) == "완성"]
with st.container(horizontal=True):
    st.metric("문항", f"{len(QS)}개", border=True)
    for tag in ["답", "결합", "함정"]:
        st.metric(f"[{tag}]", f"{sum(q['tag'] == tag for q in QS.values())}개", help=qlib.TAG_HELP[tag], border=True)
    st.metric("페이지 완성", f"{len(done)}개", border=True)

with st.container(horizontal=True, vertical_alignment="bottom"):
    tags = st.pills("유형", ["답", "결합", "함정"], selection_mode="multi", key="f_tag")
    only_done = st.toggle("완성된 페이지만", key="f_done")
    word = st.text_input("검색", placeholder="예: 난방, 소음, 스태튼", key="f_word")

for no, part in PARTS.items():
    items = [q for q in QS.values() if q["part"] == no
             and (not tags or q["tag"] in tags)
             and (not only_done or qlib.status(q["id"]) == "완성")
             and (not word or word in q["title"] or word in q["answer"])]
    if not items:
        continue
    st.subheader(f"{no}부. {part['title']}", divider="gray")
    for q in items:
        s = qlib.status(q["id"])
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.badge(q["tag"], color=qlib.TAG_COLOR[q["tag"]])
            st.page_link("app_pages/question.py", label=f"{q['id']}. {q['title']}", query_params={"q": str(q["id"])})
            if s != "원문만":
                st.badge(s, icon=":material/check:" if s == "완성" else None, color="green" if s == "완성" else "gray")
