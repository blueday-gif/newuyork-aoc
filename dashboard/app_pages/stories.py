"""100가지 질문 사이트(reports/stories/site)를 대시보드 안에서 보여 준다.
각 HTML의 story.css·story.js를 인라인으로 넣어 한 장짜리 문서로 만든 뒤 components.html로 띄운다.
"""
import re
from pathlib import Path

import streamlit as st
try:
    import streamlit.components.v1 as components
except ImportError:  # 구성요소 API가 빠진 버전
    components = None

SITE = Path(__file__).resolve().parents[2] / "reports" / "stories" / "site"


@st.cache_data
def load_pages():
    pages = {}
    for f in sorted(SITE.glob("*.html")):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"<title>(.*?)</title>", text)
        pages[f.stem] = m.group(1) if m else f.stem
    return pages


@st.cache_data
def build(stem: str) -> str:
    html = (SITE / f"{stem}.html").read_text(encoding="utf-8")
    css = (SITE / "story.css").read_text(encoding="utf-8")
    js = (SITE / "story.js").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="story.css">', f"<style>{css}</style>")
    html = html.replace('<script src="story.js"></script>', f"<script>{js}</script>")
    # iframe 안에서는 다른 HTML로 이동할 수 없다. 페이지 사이 링크는 글자로 바꾸고 선택 상자로 이동한다.
    html = re.sub(r'<a ([^>]*?)href="(?:index|q\d\d)\.html(?:#[^"]*)?"([^>]*)>(.*?)</a>',
                  r'<span style="color:var(--accent)">\3</span>', html, flags=re.S)
    if not html.lstrip().lower().startswith("<!doctype"):
        html = '<!doctype html><html lang="ko"><head><meta charset="utf-8"></head><body>' + html + "</body></html>"
    return html


pages = load_pages()
order = ["index"] + sorted(k for k in pages if k != "index")
labels = {k: ("목차 · 질문 100개" if k == "index" else f"질문 {int(k[1:])} · {pages[k]}") for k in order}

qp = st.query_params.get("story", "index")
if qp not in order:
    qp = "index"
choice = st.sidebar.selectbox("페이지", order, index=order.index(qp), format_func=lambda k: labels[k])
st.query_params["story"] = choice
st.caption("페이지 안의 링크 대신 왼쪽 '페이지' 선택 상자로 이동한다.")
if hasattr(st, "iframe"):          # Streamlit 1.67+: components.v1.html 대체
    st.iframe(build(choice), height=1900)
else:
    components.html(build(choice), height=1900, scrolling=True)
