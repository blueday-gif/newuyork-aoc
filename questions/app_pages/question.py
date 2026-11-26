"""질문 1개: 한 줄 답 → 통계 → 배경 지식 → 개념 → 계산 방법 → 주의할 점 → 출처."""
import pandas as pd
import streamlit as st

import qlib

QS, PARTS, CONCEPTS = qlib.questions(), qlib.parts(), qlib.concepts()
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

with st.container(horizontal=True, vertical_alignment="center", gap="small"):
    st.badge(f"[{q['tag']}] {qlib.TAG_HELP[q['tag']]}", color=qlib.TAG_COLOR[q["tag"]])
    st.caption(f"{part['no']}부. {part['title']}")
st.header(f"{qid}. {q['title']}")
with st.container(border=True):
    st.markdown(q["answer"] or "_원문에 답이 없다._")

if c.get("join_status"):
    st.info(c["join_status"], title="결합 진행 상태", icon=":material/merge:")

# ---------- 통계 ----------
if s:
    st.subheader("통계", divider="gray")
    with st.container(horizontal=True):
        for m in s["metrics"]:
            st.metric(m["label"], m["value"], help=m.get("help"), border=True)
    for i, spec in enumerate(s["charts"]):
        with st.container(border=True):
            st.markdown(f"**{spec['title']}**")
            y = spec["y"]
            if spec.get("alt_y"):
                y = st.segmented_control("세로축", [spec["y"], spec["alt_y"]], default=spec["y"],
                                         key=f"y_{qid}_{i}", label_visibility="collapsed") or spec["y"]
            st.altair_chart(qlib.chart(spec, y), alt=spec["title"])
            if spec.get("caption"):
                st.caption(spec["caption"])
    for t in s["tables"]:
        with st.expander(t["title"], icon=":material/table:"):
            st.dataframe(pd.DataFrame(t["rows"]), hide_index=True, alt=t["title"])
    st.caption(f"계산: `questions/calc/part{q['part']:02d}.py` · {s['computed_at']} · 원본 {s['source']}")

# ---------- 해설 ----------
if not c:
    st.info("이 문항은 아직 해설과 통계를 만들지 않았다. 위의 답은 원문(story_01_100_questions.md)이다.",
            icon=":material/edit_note:")
    st.stop()

if c.get("background"):
    st.subheader("배경 지식", divider="gray")
    st.markdown(c["background"])

if c.get("concepts"):
    st.subheader("이 질문에 쓰인 개념", divider="gray")
    for k in c["concepts"]:
        card = CONCEPTS.get(k)
        if not card:
            continue
        with st.expander(f"**{card['title']}** — {card['summary']}", icon=":material/lightbulb:"):
            st.markdown(card["body"])
            st.page_link("app_pages/concepts.py", label="개념 사전에서 보기", icon=":material/menu_book:")

if c.get("method"):
    st.subheader("계산 방법", divider="gray")
    st.markdown(c["method"])

if c.get("caveats"):
    st.subheader("주의할 점", divider="gray")
    st.markdown(c["caveats"])

if c.get("sources"):
    st.subheader("출처", divider="gray")
    st.markdown("\n".join(f"- [{x['title']}]({x['url']})" if x.get("url") else f"- {x['title']}"
                          for x in c["sources"]))

if c.get("related"):
    st.subheader("같이 볼 질문", divider="gray")
    for r in c["related"]:
        rq = QS[r]
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.badge(rq["tag"], color=qlib.TAG_COLOR[rq["tag"]])
            # 같은 페이지로 가는 page_link는 브라우저 주소를 바꾸지 않는다. 상태를 바꾸면 위에서 URL을 맞춘다.
            st.button(f"{r}. {rq['title']}", key=f"rel_{r}", type="tertiary",
                      on_click=st.session_state.__setitem__, args=("q", str(r)))
