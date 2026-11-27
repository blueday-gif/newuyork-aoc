"""질문 페이지 교육 블록. 화면에 그리기만 하고 반환값은 없다."""
import pandas as pd
import streamlit as st

import qlib
from components.labs import render as render_lab_widget


def render_header(qid: int, q: dict, part: dict, c: dict) -> None:
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.badge(f"[{q['tag']}] {qlib.TAG_HELP[q['tag']]}", color=qlib.TAG_COLOR[q["tag"]])
        st.caption(f"{part['no']}부. {part['title']}")
    st.header(f"{qid}. {q['title']}")
    with st.container(border=True):
        st.markdown(q["answer"] or "_원문에 답이 없다._")
    if c.get("join_status"):
        st.info(c["join_status"], title="결합 진행 상태", icon=":material/merge:")


def render_concept_chips(keys: list[str], concepts: dict) -> None:
    cards = [(k, concepts[k]) for k in keys if k in concepts]
    if not cards:
        return
    with st.container(horizontal=True, gap="small"):
        for _, card in cards:
            with st.popover(card["title"], icon=":material/lightbulb:"):
                st.markdown(card["summary"])
                st.page_link("app_pages/concepts.py", label="개념 사전에서 보기", icon=":material/menu_book:")


def render_stats(qid: int, part_no: int, s: dict) -> None:
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
    st.caption(f"계산: `questions/calc/part{part_no:02d}.py` · {s['computed_at']} · 원본 {s['source']}")


def render_lab(qid: int, lab_key: str) -> None:
    st.subheader("직접 해 보기", divider="gray")
    render_lab_widget(lab_key, key=f"q{qid}")


def render_markdown_section(title: str, md: str) -> None:
    st.subheader(title, divider="gray")
    st.markdown(md)


def render_concepts(keys: list[str], concepts: dict) -> None:
    st.subheader("이 질문에 쓰인 개념", divider="gray")
    for k in keys:
        card = concepts.get(k)
        if not card:
            continue
        with st.expander(f"**{card['title']}** — {card['summary']}", icon=":material/lightbulb:"):
            st.markdown(card["body"])
            st.page_link("app_pages/concepts.py", label="개념 사전에서 보기", icon=":material/menu_book:")


def render_caveats(md: str) -> None:
    st.subheader("주의할 점", divider="gray")
    st.warning(md, icon=":material/warning:")


def render_sources(sources: list[dict]) -> None:
    st.subheader("출처", divider="gray")
    st.markdown("\n".join(f"- [{x['title']}]({x['url']})" if x.get("url") else f"- {x['title']}"
                          for x in sources))


def render_paper_bridge(keys: list[str], papers: dict) -> None:
    items = [(k, papers[k]) for k in keys if k in papers]
    if not items:
        return
    with st.expander("학술 논문·시정 사례와 연결하기", icon=":material/school:"):
        for i, (_, p) in enumerate(items):
            if i:
                st.divider()
            finding = " ".join(str(p["finding"]).split())
            st.markdown(f"**{p['title']}**")
            st.caption(p["who"])
            st.markdown(
                f"- **물은 것**: {p['question']}\n"
                f"- **합친 자료**: {p['data']}\n"
                f"- **방법**: {p['method']}\n"
                f"- **결과**: {finding}\n"
                f"- **이 프로젝트와 다른 점**: {p['differs']}"
            )
        st.caption("요약 출처: 뉴욕시_311_민원데이터_해외연구사례_종합.docx(2026-11-26). 원문 수치는 다시 확인하지 않았다.")


def render_next(qid: int, related: list[int], why: dict, qs: dict) -> None:
    st.subheader("같이 볼 질문", divider="gray")
    for r in related:
        rq = qs[r]
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.badge(rq["tag"], color=qlib.TAG_COLOR[rq["tag"]])
            st.button(f"{r}. {rq['title']}", key=f"rel_{r}", type="tertiary",
                      on_click=st.session_state.__setitem__, args=("q", str(r)))
        note = why.get(str(r))
        if note:
            st.caption(note)
