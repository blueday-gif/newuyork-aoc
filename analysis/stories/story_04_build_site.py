"""100가지 질문 사이트 만들기: 목차(index.html) + 심화 페이지 21개.
입력: reports/stories/story_03_deep.json, story_02_snow_sample.json, sample_q01_snow.html, story_01_100_questions.md
출력: reports/stories/site/
"""
import json, re, html, sys, os
sys.path.insert(0, os.path.dirname(__file__))
PROJ = r"G:/내 드라이브/newyork"
SITE = PROJ + "/reports/stories/site"
D = json.load(open(PROJ + "/reports/stories/story_03_deep.json", encoding="utf-8"))

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@500;700'
         '&family=Noto+Sans+KR:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">')

# ---------- 블록 도우미 ----------
def P(h): return ("p", h)
def H3(t): return ("h3", t)
def CALL(h): return ("call", h)
def FORM(h): return ("form", h)
def FLOW(steps): return ("flow", steps)          # [(k, t, d, n)]
def CARDS(cards): return ("cards", cards)        # [(title, value, sub, on)]
def CH(key, title, spec, sub="", legend=None):
    return ("chart", key, title, sub, legend or [], spec)

def render_block(b, charts):
    k = b[0]
    if k == "p": return f"<p>{b[1]}</p>"
    if k == "h3": return f"<h3>{b[1]}</h3>"
    if k == "call": return f'<div class="callout">{b[1]}</div>'
    if k == "form": return f'<div class="formula">{b[1]}</div>'
    if k == "flow":
        cols = min(4, len(b[1]))
        return (f'<div class="flow" style="grid-template-columns:repeat({cols},minmax(0,1fr))">' + "".join(
            f'<div class="step"><span class="k">{a}</span><span class="t">{t}</span><span class="d">{d}</span><span class="n num">{n}</span></div>'
            for a, t, d, n in b[1]) + "</div>")
    if k == "cards":
        return '<div class="cards">' + "".join(
            f'<div class="model{" on" if on else ""}"><span class="mt">{t}</span><span class="mv num">{v}</span><span class="mr">{s}</span></div>'
            for t, v, s, on in b[1]) + "</div>"
    if k == "chart":
        _, key, title, sub, legend, spec = b
        charts[key] = spec
        lg = ("<div class=\"legend\">" + "".join(f'<span><i style="background:var(--s-{c})"></i>{l}</span>' for l, c in legend) + "</div>") if legend else ""
        seg = '<div class="seg" role="group" aria-label="보기 선택"></div>' if spec.get("views") else ""
        body = '<div class="gridwrap"></div>' if spec["type"] == "grid" else f'<svg viewBox="0 0 700 300" role="img" aria-label="{html.escape(title)}"></svg>'
        return (f'<div class="chart" data-c="{key}"><span class="ct">{title}</span>' + (f'<span class="cs">{sub}</span>' if sub else "")
                + seg + lg + body + '<span class="vnote"></span>'
                + '<details class="table" hidden><summary>표로 보기</summary><div class="tscroll"><table class="tv"></table></div></details></div>')
    raise ValueError(k)

def page_html(pg, prev_, next_):
    charts = {}
    hero = "".join(
        (f'<span class="vs">vs</span>' if i else "") +
        f'<div class="ans-row"><span class="big num{" si" if hl else ""}">{v}</span><span class="lbl">{l}</span></div>'
        for i, (v, l, hl) in enumerate(pg["hero"]))
    cols = " ".join(["auto"] * (2 * len(pg["hero"]) - 1))
    out = [f'<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
           f'<title>{pg["short"]}</title>\n{FONTS}\n<link rel="stylesheet" href="story.css">\n</head>\n<body>\n<div class="wrap">\n',
           f'<nav class="topnav"><a href="index.html">← 100가지 질문 목차</a><span>'
           + (f'<a href="{prev_["id"]}.html">이전: 질문 {prev_["num"]}</a>' if prev_ else "")
           + (" · " if prev_ and next_ else "")
           + (f'<a href="{next_["id"]}.html">다음: 질문 {next_["num"]}</a>' if next_ else "") + "</span></nav>\n",
           f'<header><div class="qtag"><span class="chip">질문 {pg["num"]} / 100</span><span class="chip">{pg["part"]}</span>'
           f'<span class="chip">배우는 것: {pg["learn"]}</span></div><h1>{pg["title"]}</h1>'
           f'<div class="answer" style="grid-template-columns:{cols}">{hero}</div><p class="lede ans-text">{pg["lede"]}</p></header>\n']
    n = 1
    a = pg.get("article")
    if a:
        items = "".join(f"<li>{x}</li>" for x in a["items"])
        links = " · ".join(f'<a href="{u}" target="_blank" rel="noopener">{t}</a>' for t, u in a.get("links", []))
        out.append(f'<section><div class="sec-head"><span class="eyebrow">{n} · {a.get("kind", "기사 요약")}</span><h2>{a["h2"]}</h2></div>'
                   f'<div class="article"><span class="src">{a["src"]}</span><ul>{items}</ul>'
                   + (f'<p class="quote">{a["quote"]}</p>' if a.get("quote") else "")
                   + (f'<span class="src">{links}</span>' if links else "") + "</div></section>\n")
        n += 1
    for eyebrow, h2, blocks in pg["sections"]:
        out.append(f'<section><div class="sec-head"><span class="eyebrow">{n} · {eyebrow}</span><h2>{h2}</h2></div>'
                   + "".join(render_block(b, charts) for b in blocks) + "</section>\n")
        n += 1
    out.append(f'<section><div class="sec-head"><span class="eyebrow">{n} · 이렇게 하면 틀린다</span><h2>함정 {len(pg["traps"])}가지</h2></div><div class="traps">'
               + "".join(f'<div class="trap"><span class="x">{i + 1}</span><p><b>{t}</b> {d}</p></div>' for i, (t, d) in enumerate(pg["traps"]))
               + "</div></section>\n"); n += 1
    code = html.escape(pg["code"].strip("\n"))
    code = re.sub(r"(?m)^(\s*#.*)$", r'<span class="c">\1</span>', code)
    out.append(f'<section><div class="sec-head"><span class="eyebrow">{n} · 직접 해보기</span><h2>파이썬으로 따라 하기</h2></div>'
               f'<pre class="code">{code}</pre><p class="cs" style="color:var(--muted);font-size:13px">전체 계산: analysis/stories/story_03_deep_calc.py</p></section>\n'); n += 1
    out.append(f'<section><div class="sec-head"><span class="eyebrow">{n} · 오늘 배운 말</span><h2>용어 {len(pg["terms"])}개</h2></div><div class="terms">'
               + "".join(f"<div class=\"term\"><b>{t}</b><span>{d}</span></div>" for t, d in pg["terms"]) + "</div></section>\n")
    nxt = (f'<a href="{next_["id"]}.html">다음 심화: 질문 {next_["num"]} · {next_["short"]} →</a>' if next_ else '<a href="index.html">목차로 돌아가기</a>')
    out.append(f'<footer><div class="next"><a href="index.html">← 목차</a>{nxt}</div>'
               f'<span>데이터: NYC 311 서비스 요청 2025-11-01 21시 ~ 2026-10-31 21시 (3,963,959건), ACS 2024 5개년, Census Tract(인구 1,000명 이상 2,195곳). {pg.get("foot", "")}</span></footer>\n</div>\n')
    out.append('<script id="charts" type="application/json">' + json.dumps(charts, ensure_ascii=False).replace("</", "<\\/") + "</script>\n<script src=\"story.js\"></script>\n</body>\n</html>\n")
    return "".join(out)

# ---------- 질문 1: 기존 샘플을 사이트 페이지로 ----------
def q01_page(next_):
    s = open(PROJ + "/reports/stories/sample_q01_snow.html", encoding="utf-8").read()
    head_end = s.index("<div class=\"wrap\">")
    head = s[:head_end]
    title = re.search(r"<title>.*?</title>", head).group(0)
    head = head.replace(title, "")
    nav = (f'<nav class="topnav"><a href="index.html">← 100가지 질문 목차</a><span><a href="{next_["id"]}.html">다음: 질문 {next_["num"]}</a></span></nav>\n')
    body = s[head_end:].replace('<div class="wrap">', '<div class="wrap">\n' + nav, 1)
    body = body.replace('<div class="next"><span>다음 질문 2 · 폭설 1주일을 다 합치면?</span><span>질문 3 · 처리시간 0.4시간의 비밀</span></div>',
                        f'<div class="next"><a href="index.html">← 목차</a><a href="{next_["id"]}.html">다음 심화: 질문 {next_["num"]} · {next_["short"]} →</a></div>')
    body = body.replace(".next { display: flex;", ".next a { color: var(--ink-2); } .next { display: flex;")
    return (f'<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'{title}\n{head}<style>.topnav{{display:flex;justify-content:space-between;gap:12px;font-size:13px;flex-wrap:wrap}}.topnav a{{color:var(--ink-2);text-decoration:none}}.next a{{color:var(--ink-2)}}</style>\n</head>\n<body>\n{body}</body>\n</html>\n')

# ---------- 목차 ----------
def parse_questions():
    md = open(PROJ + "/reports/stories/story_01_100_questions.md", encoding="utf-8").read()
    parts, qs, cur = [], [], None
    for line in md.splitlines():
        m = re.match(r"## (\d+)부\. (.+)", line)
        if m: cur = (int(m.group(1)), m.group(2)); parts.append(cur); continue
        m = re.match(r"\*\*(\d+)\. \[(답|결합|함정)\] (.+?)\*\*(.*)", line)
        if m and cur:
            qs.append({"num": int(m.group(1)), "tag": m.group(2), "q": m.group(3).strip(), "rest": m.group(4).strip(), "part": cur[0], "ans": ""})
        elif qs and line.strip() and not line.startswith(("#", "---", "배경")) and not qs[-1]["ans"]:
            qs[-1]["ans"] = line.strip()
        if line.startswith("## 참고한 자료"): break
    for q in qs:
        if q["rest"] and not q["ans"]: q["ans"] = q["rest"]
        elif q["rest"]: q["ans"] = q["rest"] + " " + q["ans"]
    return parts, qs

def md_inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s

def index_html(pages):
    parts, qs = parse_questions()
    deep = {p["num"]: p for p in pages}
    TAG = {"답": ("답", "t-ans"), "결합": ("결합", "t-join"), "함정": ("함정", "t-trap")}
    cards = []
    for num, name in parts:
        items = [q for q in qs if q["part"] == num]
        lo, hi = items[0]["num"], items[-1]["num"]
        cards.append(f'<section class="part" id="p{num}"><div class="phead"><span class="eyebrow">{num}부 · 질문 {lo}–{hi}</span><h2>{html.escape(name)}</h2></div><div class="qgrid">')
        for q in items:
            t, cls = TAG[q["tag"]]
            dp = deep.get(q["num"])
            ans = md_inline(q["ans"])
            if len(re.sub("<.*?>", "", ans)) > 190:
                cut = ans[:190]; ans = cut[:cut.rfind(" ")] + " …"
                ans = re.sub(r"<b>([^<]*)$", r"\1", ans)
            link = (f'<a class="deep" href="{dp["id"]}.html">심화 페이지 · {dp["learn"]} →</a>' if dp else "")
            cards.append(f'<article class="q{" has-deep" if dp else ""}" data-tag="{q["tag"]}"><div class="qh"><span class="qn num">{q["num"]}</span>'
                         f'<span class="tag {cls}">{t}</span></div><h3>{md_inline(q["q"])}</h3><p>{ans}</p>{link}</article>')
        cards.append("</div></section>")
    lessons = "".join(f'<a class="lesson" href="{p["id"]}.html"><span class="num">{p["num"]:>3}</span><span>{p["learn"]}</span></a>' for p in pages)
    return f'''<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>100가지 질문으로 보는 뉴욕</title>
{FONTS}
<link rel="stylesheet" href="story.css">
<style>
.wrap {{ max-width: 1040px; gap: 40px; }}
.hero {{ display: flex; flex-direction: column; gap: 16px; }}
.hero .lede {{ max-width: 720px; }}
.stats {{ display: flex; gap: 28px; flex-wrap: wrap; }}
.stats div {{ display: flex; flex-direction: column; }}
.stats b {{ font-family: var(--font-mono); font-size: 30px; font-weight: 500; line-height: 1.1; }}
.stats span {{ font-size: 13px; color: var(--ink-2); }}
.filters {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; position: sticky; top: 0; background: var(--bg); padding: 10px 0; z-index: 3; border-bottom: 1px solid var(--rule); }}
.filters input {{ font: inherit; font-size: 14px; padding: 6px 10px; border: 1px solid var(--rule); border-radius: 8px; background: var(--surface); color: var(--ink); min-width: 0; flex: 1 1 180px; }}
.part {{ gap: 14px; }}
.phead {{ display: flex; flex-direction: column; gap: 4px; padding-top: 16px; border-top: 1px solid var(--rule); }}
.qgrid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 12px; }}
.q {{ background: var(--surface); border: 1px solid var(--rule); border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; min-width: 0; }}
.q.has-deep {{ border-color: var(--accent); box-shadow: inset 3px 0 0 var(--accent); }}
.q h3 {{ font-size: 15px; line-height: 1.45; }}
.q p {{ font-size: 13.5px; color: var(--ink-2); line-height: 1.6; }}
.qh {{ display: flex; gap: 8px; align-items: center; }}
.qn {{ font-size: 13px; color: var(--muted); }}
.tag {{ font-size: 11px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--rule); color: var(--ink-2); }}
.tag.t-ans {{ border-color: var(--s-b); color: var(--s-b); }}
.tag.t-trap {{ border-color: var(--accent); color: var(--accent); }}
.tag.t-join {{ border-color: var(--s-c); color: var(--ink-2); border-style: dashed; }}
.deep {{ font-size: 13px; font-weight: 500; margin-top: auto; }}
.lessons {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 6px 16px; }}
.lesson {{ display: grid; grid-template-columns: 34px 1fr; gap: 8px; font-size: 14px; color: var(--ink); text-decoration: none; padding: 6px 0; border-bottom: 1px solid var(--rule); }}
.lesson .num {{ color: var(--accent); }}
.lesson:hover span:last-child {{ color: var(--accent); }}
.q[hidden], .part[hidden] {{ display: none; }}
</style>
<div class="wrap">
<header class="hero">
  <span class="eyebrow">NYC 311 · 2025년 11월 ~ 2026년 10월</span>
  <h1>100가지 질문으로 보는 뉴요커의 삶</h1>
  <p class="lede">뉴욕 시민이 1년 동안 311에 신고한 396만 건과 인구조사(ACS)를 합쳐 100가지를 물었다. 뉴스 기사를 데이터로 다시 확인하고, 맘다니 시장의 임대료 동결과 집주인들의 반발, 가난·인종과 민원의 관계를 살폈다. 데이터로 답할 수 없는 질문은 왜 안 되는지도 적었다.</p>
  <div class="stats"><div><b>3,963,959</b><span>민원 건수</span></div><div><b>2,195</b><span>분석한 동네(Census Tract)</span></div><div><b>{len(pages)}</b><span>심화 페이지</span></div><div><b>100</b><span>질문</span></div></div>
  <p class="callout">311은 "일어난 문제"가 아니라 "신고된 문제"다. 아래 모든 답은 이 전제 위에 있다. 인종 관련 수치도 동네 단위 비교이고, 개인이 어떻게 행동한다는 뜻이 아니다.</p>
</header>
<section>
  <div class="sec-head"><span class="eyebrow">통계 입문 순서</span><h2>심화 페이지 {len(pages)}개로 배우는 통계</h2></div>
  <p>주황 테두리 카드에는 심화 페이지가 있다. 한 페이지는 기사 요약 → 데이터 확인 → 통계 기초 → 함정 → 파이썬 → 용어 순서다. 위에서부터 읽으면 초보자용 통계 과정이 된다.</p>
  <div class="lessons">{lessons}</div>
</section>
<div class="filters" role="group" aria-label="질문 거르기">
  <div class="seg" id="tagseg"><button type="button" aria-pressed="true" data-t="">전체</button><button type="button" aria-pressed="false" data-t="답">답</button><button type="button" aria-pressed="false" data-t="결합">결합</button><button type="button" aria-pressed="false" data-t="함정">함정</button><button type="button" aria-pressed="false" data-t="deep">심화만</button></div>
  <input type="search" id="qs" placeholder="단어로 찾기: 난방, 맘다니, 쥐…" aria-label="질문 검색">
</div>
{"".join(cards)}
<footer><span><b>표시</b> · 답: 지금 데이터로 답했다 · 결합: 다른 데이터를 붙여야 답이 나온다 · 함정: 이렇게 다루면 틀린다</span>
<span>데이터: NYC Open Data 311 서비스 요청, ACS 2024 5개년, TIGER/Line 2024. 계산: analysis/stories/. 논문·기사 출처는 질문 목록 원문(reports/stories/story_01_100_questions.md)에 있다.</span></footer>
</div>
<script>
(function () {{
  let tag = "", q = "";
  const cards = [...document.querySelectorAll(".q")], parts = [...document.querySelectorAll(".part")];
  function apply() {{
    cards.forEach(c => {{
      const okT = !tag || (tag === "deep" ? c.classList.contains("has-deep") : c.dataset.tag === tag);
      const okQ = !q || c.textContent.toLowerCase().includes(q);
      c.hidden = !(okT && okQ);
    }});
    parts.forEach(p => p.hidden = !p.querySelector(".q:not([hidden])"));
  }}
  document.querySelectorAll("#tagseg button").forEach(b => b.addEventListener("click", () => {{
    document.querySelectorAll("#tagseg button").forEach(x => x.setAttribute("aria-pressed", x === b)); tag = b.dataset.t; apply();
  }}));
  document.getElementById("qs").addEventListener("input", e => {{ q = e.target.value.trim().toLowerCase(); apply(); }});
}})();
</script>
'''

if __name__ == "__main__":
    from story_04_pages_a import PAGES as A
    from story_04_pages_b import PAGES as B
    pages = sorted([f(D) for f in A + B], key=lambda p: p["num"])
    q1 = {"id": "q01", "num": 1, "short": "폭설과 스태튼아일랜드", "learn": "데이터 합치기 · 회귀분석"}
    allp = [q1] + pages
    os.makedirs(SITE, exist_ok=True)
    open(SITE + "/q01.html", "w", encoding="utf-8").write(q01_page(pages[0]))
    for i, pg in enumerate(pages):
        prev_ = allp[i]; next_ = pages[i + 1] if i + 1 < len(pages) else None
        open(f"{SITE}/{pg['id']}.html", "w", encoding="utf-8").write(page_html(pg, prev_, next_))
    open(SITE + "/index.html", "w", encoding="utf-8").write(index_html(allp))
    print("pages:", [p["id"] for p in allp])
