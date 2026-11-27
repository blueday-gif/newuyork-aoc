"""학습 진도: 본 문항·개념을 session_state에 기록하고 사이드바에 보여 준다."""
import streamlit as st

CORE = [
    "data_join",
    "boundary_overlay",
    "per_capita",
    "small_denominator",
    "did",
    "reported_vs_occurred",
]


def mark_visited(qid: int, concept_keys: list[str]) -> None:
    st.session_state.setdefault("visited", set()).add(qid)
    st.session_state.setdefault("seen_concepts", set()).update(concept_keys)


def visited() -> set[int]:
    return st.session_state.get("visited", set())


def seen_concepts() -> set[str]:
    return st.session_state.get("seen_concepts", set())


def render_sidebar(total: int, concepts: dict) -> None:
    with st.sidebar:
        st.subheader("나의 진도")
        n = len(visited())
        st.progress(n / total if total else 0.0, text=f"{n} / {total} 문항")
        seen = seen_concepts()
        for key in CORE:
            icon = ":material/check_circle:" if key in seen else ":material/radio_button_unchecked:"
            st.markdown(f"{icon} {concepts[key]['title']}")
        st.caption("진도는 이 브라우저 탭에서만 기억한다. 새로고침하면 처음부터다.")
