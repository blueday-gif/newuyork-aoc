"""질문 1개: 한 줄 답 → 통계 → 배경 지식 → 개념 → 계산 방법 → 주의할 점 → 출처."""
import streamlit as st

import qlib
import state
from components import edu_blocks

QS, PARTS, CONCEPTS, PAPERS = qlib.questions(), qlib.parts(), qlib.concepts(), qlib.papers()
# URL은 ?q=7처럼 번호만 쓴다. bind="query-params"는 표시 문구 전체를 URL에 넣어서
# 목차·관련 문항 링크(?q=7)와 맞지 않는다. 그래서 URL과 선택 상자를 직접 맞춘다.
IDS = [str(i) for i in QS]
url_q = st.query_params.get("q")
if url_q in IDS and url_q != st.session_state.get("_q_synced"):
    st.session_state.q = url_q  # 링크로 들어온 경우 URL이 우선
    st.session_state._q_synced = url_q


def step(delta: int):
    i = IDS.index(st.session_state.q) + delta
    st.session_state.q = IDS[max(0, min(len(IDS) - 1, i))]


with st.container(horizontal=True, vertical_alignment="bottom"):
    picked = st.selectbox("질문", IDS, key="q", format_func=lambda i: f"{i}. {QS[int(i)]['title']}", width="stretch")
    st.button("이전", icon=":material/chevron_left:", on_click=step, args=(-1,), disabled=picked == IDS[0])
    st.button("다음", icon=":material/chevron_right:", icon_position="right", on_click=step, args=(1,),
              disabled=picked == IDS[-1])

if st.query_params.get("q") != picked:
    st.query_params["q"] = picked
    st.session_state._q_synced = picked

qid = int(picked)
q = QS[qid]
part = PARTS[q["part"]]
c = qlib.content(qid) or {}
s = qlib.stats(qid)

edu_blocks.render_header(qid, q, part, c)
edu_blocks.render_concept_chips(c.get("concepts", []), CONCEPTS)
state.mark_visited(qid, c.get("concepts", []))
if s:
    edu_blocks.render_stats(qid, q["part"], s)
if c.get("lab"):
    edu_blocks.render_lab(qid, c["lab"])
if not c:
    st.info("이 문항은 아직 해설과 통계를 만들지 않았다. 위의 답은 원문(story_01_100_questions.md)이다.",
            icon=":material/edit_note:")
    st.stop()

if c.get("background"):
    edu_blocks.render_markdown_section("배경 지식", c["background"])
if c.get("concepts"):
    edu_blocks.render_concepts(c["concepts"], CONCEPTS)
if c.get("method"):
    edu_blocks.render_markdown_section("계산 방법", c["method"])
if c.get("caveats"):
    edu_blocks.render_caveats(c["caveats"])
if c.get("sources"):
    edu_blocks.render_sources(c["sources"])
if c.get("papers"):
    edu_blocks.render_paper_bridge(c["papers"], PAPERS)
if c.get("related"):
    edu_blocks.render_next(qid, c["related"], c.get("related_why", {}), QS)
