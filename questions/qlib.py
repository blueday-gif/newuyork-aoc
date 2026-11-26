"""100가지 질문 앱이 읽는 자료와 차트 도우미.

자료는 세 층으로 나뉜다.
- meta/questions.json: 질문·한 줄 답(원문에서 자동 생성, build_meta.py)
- content/q###.toml: 사람이 쓰는 해설(배경, 계산 방법, 주의, 출처, 개념, 관련 문항)
- data/q###.json: 계산 스크립트(calc/)가 만드는 통계(지표, 차트 자료, 표)
"""
import json
import tomllib
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

QDIR = Path(__file__).resolve().parent
TAG_COLOR = {"답": "blue", "결합": "violet", "함정": "orange"}
TAG_HELP = {"답": "지금 데이터로 답했다", "결합": "다른 데이터를 붙여야 답이 나온다", "함정": "이렇게 다루면 틀린다"}
CHART_COLORS = ["#2457a7", "#e07b39", "#3a9d6e", "#8e5cc4", "#c94f6d", "#6b7a8f"]


def _mtime(path: Path) -> int:
    """캐시 키. 인자 이름이 _로 시작하면 st.cache_data가 키에서 빼므로 mtime이라는 이름으로 넘긴다."""
    return path.stat().st_mtime_ns if path.exists() else 0


@st.cache_data(ttl="1h")
def _meta(mtime: int) -> dict:
    return json.loads((QDIR / "meta" / "questions.json").read_text(encoding="utf-8"))


def meta() -> dict:
    return _meta(_mtime(QDIR / "meta" / "questions.json"))


def questions() -> dict[int, dict]:
    return {q["id"]: q for q in meta()["questions"]}


def parts() -> dict[int, dict]:
    return {p["no"]: p for p in meta()["parts"]}


@st.cache_data(ttl="1h")
def _concepts(mtime: int) -> dict:
    return tomllib.loads((QDIR / "meta" / "concepts.toml").read_text(encoding="utf-8"))


def concepts() -> dict:
    return _concepts(_mtime(QDIR / "meta" / "concepts.toml"))


@st.cache_data(ttl="1h", max_entries=200)
def _content(qid: int, mtime: int) -> dict | None:
    path = QDIR / "content" / f"q{qid:03d}.toml"
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def content(qid: int) -> dict | None:
    return _content(qid, _mtime(QDIR / "content" / f"q{qid:03d}.toml"))


@st.cache_data(ttl="1h", max_entries=200)
def _stats(qid: int, mtime: int) -> dict | None:
    path = QDIR / "data" / f"q{qid:03d}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def stats(qid: int) -> dict | None:
    return _stats(qid, _mtime(QDIR / "data" / f"q{qid:03d}.json"))


def status(qid: int) -> str:
    """문항 페이지가 얼마나 채워졌나: 완성 / 해설만 / 통계만 / 원문만"""
    c, s = (QDIR / "content" / f"q{qid:03d}.toml").exists(), (QDIR / "data" / f"q{qid:03d}.json").exists()
    return {(True, True): "완성", (True, False): "해설만", (False, True): "통계만"}.get((c, s), "원문만")


def concept_users() -> dict[str, list[int]]:
    """개념 키 → 그 개념을 쓰는 문항 번호"""
    out: dict[str, list[int]] = {}
    for qid in questions():
        c = content(qid)
        for k in (c or {}).get("concepts", []):
            out.setdefault(k, []).append(qid)
    return out


def _safe_field(name: str) -> str:
    return (name.replace("'", "’").replace('"', "”").replace("[", "(").replace("]", ")")
            .replace(".", "·").replace(":", "∶").replace("\\", "/"))


def chart(spec: dict, y: str | None = None) -> alt.Chart:
    """data/q###.json의 차트 사양을 Altair 차트로 만든다. y를 주면 세로축 값을 바꾼다."""
    df = pd.DataFrame(spec["rows"])
    # Vega-Lite는 필드 이름의 따옴표·대괄호·점·콜론을 경로 문법으로 읽어 조용히 실패한다. 비슷한 글자로 바꾼다.
    safe = {c: _safe_field(c) for c in df.columns}
    df = df.rename(columns=safe)
    spec = {**spec, **{k: _safe_field(spec[k]) for k in ("x", "y", "color", "alt_y") if spec.get(k)}}
    kind, x = spec["kind"], spec["x"]
    y = _safe_field(y) if y else spec["y"]
    color = spec.get("color")
    is_date = df[x].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$").all() if kind != "barh" else False
    if is_date:
        df[x] = pd.to_datetime(df[x])
    # 사양에 colors({값: 색})가 있으면 그 순서와 색을 그대로 쓴다. 본문에서 색을 가리킬 때 필요하다.
    if spec.get("colors"):
        palette = alt.Scale(domain=list(spec["colors"]), range=list(spec["colors"].values()))
    else:
        palette = alt.Scale(range=CHART_COLORS)
    tip = [alt.Tooltip(c) for c in df.columns]
    if is_date:
        tip = [alt.Tooltip(x, format="%Y-%m-%d")] + [alt.Tooltip(c) for c in df.columns if c != x]

    if kind == "bar":
        sort = "-y" if spec.get("sort") == "-y" else None
        if is_date:  # 월 단위 막대
            xe = alt.X(x, timeUnit="yearmonth", type="ordinal", title=None, axis=alt.Axis(format="%y.%m", labelAngle=0))
        else:
            xe = alt.X(x, sort=sort, title=None, axis=alt.Axis(labelAngle=0))
        base = alt.Chart(df).mark_bar(color=CHART_COLORS[0], cornerRadiusEnd=2).encode(x=xe, y=alt.Y(y, title=y), tooltip=tip)
    elif kind == "barh":
        base = alt.Chart(df).mark_bar(color=CHART_COLORS[0], cornerRadiusEnd=2).encode(
            y=alt.Y(spec["y"], sort="-x", title=None, axis=alt.Axis(labelLimit=260)), x=alt.X(x, title=x), tooltip=tip)
    elif kind == "group":  # 묶은 막대: x 범주 안에 color 막대를 나란히
        order = list(spec["colors"]) if spec.get("colors") else None
        base = alt.Chart(df).mark_bar(cornerRadiusEnd=2).encode(
            x=alt.X(x, title=None, sort=None, axis=alt.Axis(labelAngle=0)), xOffset=alt.XOffset(color, sort=order),
            y=alt.Y(y, title=y), color=alt.Color(color, scale=palette, sort=order,
                                                 legend=alt.Legend(orient="top", title=None)), tooltip=tip)
    elif kind == "stackh":  # 가로 누적 막대(구성비): y 범주, x 값, color 구성
        order = list(spec["colors"]) if spec.get("colors") else None
        df["_o"] = df[color].map({v: i for i, v in enumerate(order)}) if order else 0
        base = alt.Chart(df).mark_bar().encode(
            y=alt.Y(spec["y"], title=None, sort=None), x=alt.X(x, stack=True, title=x, scale=alt.Scale(domain=[0, 100], nice=False)),
            color=alt.Color(color, scale=palette, sort=order, legend=alt.Legend(orient="top", title=None)),
            order=alt.Order("_o"), tooltip=[alt.Tooltip(c) for c in df.columns if c != "_o"])
    elif kind == "scatter":  # Tract 산점도. trend=True면 LOESS 추세선을 겹친다.
        enc = dict(x=alt.X(x, title=x, scale=alt.Scale(zero=False)), y=alt.Y(y, title=y), tooltip=tip)
        if color:
            enc["color"] = alt.Color(color, scale=palette, legend=alt.Legend(orient="top", title=None))
        pts = alt.Chart(df).mark_circle(size=14, opacity=0.35) if color \
            else alt.Chart(df).mark_circle(size=14, opacity=0.35, color=CHART_COLORS[0])
        base = pts.encode(**enc)
        if spec.get("trend"):
            line = alt.Chart(df).transform_loess(x, y).mark_line(color=CHART_COLORS[1], strokeWidth=3).encode(x=x, y=y)
            base = base + line
    elif kind == "stack":
        xt = alt.X(x, timeUnit="yearmonth", title=None) if is_date else alt.X(x, title=None)
        base = alt.Chart(df).mark_bar().encode(
            x=xt, y=alt.Y(y, stack=True, title=y),
            color=alt.Color(color, scale=palette, legend=alt.Legend(orient="top", title=None)), tooltip=tip)
    else:  # line
        # 글자 범주(D1…D10, Q1…Q5)는 가나다순이 아니라 자료에 나온 순서대로 놓는다(D10이 D1 옆에 오지 않게).
        is_text = not is_date and not pd.api.types.is_numeric_dtype(df[x])
        xe = alt.X(x, title=x, sort=None, axis=alt.Axis(labelAngle=0)) if is_text else alt.X(x, title=None if is_date else x)
        enc = dict(x=xe, y=alt.Y(y, title=y), tooltip=tip)
        if color:
            enc["color"] = alt.Color(color, scale=palette, legend=alt.Legend(orient="top", title=None))
        mark = dict(point=spec.get("point", False), strokeWidth=2)
        if not color:
            mark["color"] = CHART_COLORS[0]
        base = alt.Chart(df).mark_line(**mark).encode(**enc)
    return base.properties(height=spec.get("height", 300))
