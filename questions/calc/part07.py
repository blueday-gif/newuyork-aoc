"""7부. 건물과 주소: 쏠림의 도시 — 통계 계산.
문항 69–76. 실행: python questions/calc/part07.py  (일부만: python questions/calc/part07.py 69 74)
71·75·76번은 외부 자료(최악의 집주인 목록, PLUTO, 세금 체납 목록)가 필요해 311 쪽만 계산한다.
"""
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BORO_KO, HPD_RULES, acs, borough_pop, classify, load_311, records, save  # noqa: E402

BOROS = list(BORO_KO)
HOT = "655 EAST 230 STREET"
HPD_KO = {"HEAT/HOT WATER": "난방·온수", "UNSANITARY CONDITION": "비위생", "PLUMBING": "배관", "PAINT/PLASTER": "페인트·회벽",
          "DOOR/WINDOW": "문·창문", "WATER LEAK": "누수", "GENERAL": "일반", "ELECTRIC": "전기", "FLOORING/STAIRS": "바닥·계단",
          "APPLIANCE": "가전", "SAFETY": "안전", "ELEVATOR": "승강기"}


def has_bbl(df):
    s = df.bbl.astype(str).str.strip()
    return df[df.bbl.notna() & (s != "") & (s != "nan")]


def gini(v) -> float:
    a = np.sort(np.asarray(v, dtype=float))
    n = len(a)
    return float((2 * np.sum(np.arange(1, n + 1) * a) / (n * a.sum())) - (n + 1) / n)


def q069(df):
    c = df[df.addr_n != ""].addr_n.value_counts()
    v = c.values
    cum = np.cumsum(v) / v.sum()
    pts = [{"주소 상위 %": 0.0, "민원 누적 %": 0.0}]
    for x in [0.1, 0.5, 1, 2, 5, 10, 20, 30, 50, 57, 70, 85, 100]:
        k = max(1, int(np.ceil(x / 100 * len(v))))
        pts.append({"주소 상위 %": x, "민원 누적 %": round(float(cum[k - 1]) * 100, 1)})
    top = c.head(10).rename_axis("주소").reset_index(name="민원")
    top1 = c.head(int(len(c) * 0.01)).sum() / c.sum() * 100
    save(69,
         metrics=[
             {"label": "민원이 들어온 주소", "value": f"{len(c):,}곳"},
             {"label": "1년에 딱 1번", "value": f"{(c == 1).mean() * 100:.0f}%", "help": f"{(c == 1).sum():,}곳"},
             {"label": "상위 1% 주소의 몫", "value": f"{top1:.1f}%", "help": f"{int(len(c) * 0.01):,}곳"},
             {"label": "지니 계수", "value": f"{gini(v):.2f}", "help": "0 = 모든 주소가 같음, 1 = 한 주소가 전부"},
         ],
         charts=[
             {"title": "주소 집중 곡선", "kind": "line", "x": "주소 상위 %", "y": "민원 누적 %", "rows": pts, "point": True,
              "caption": "민원이 많은 주소부터 줄 세웠다. 상위 1%가 30%, 상위 10%가 절반 넘게를 차지한다."},
         ],
         tables=[{"title": "민원이 가장 많은 주소 10곳", "rows": records(top)}])


def q070(df):
    heat = has_bbl(df[df.problem == "HEAT/HOT WATER"])
    b = heat.groupby("bbl").size().sort_values(ascending=False)
    top_bbl = b.index[0]
    h = heat[heat.bbl == top_bbl].copy()
    addr = h.addr_n.mode().iat[0]
    d = h.groupby("date").size().rename_axis("날짜").reset_index(name="난방 민원")
    h["결과"] = classify(h.resolution, HPD_RULES)
    res = h.결과.value_counts(normalize=True).mul(100).round(1).rename_axis("결과").reset_index(name="비율(%)")
    top = b.head(10).rename_axis("BBL").reset_index(name="난방 민원")
    top["BBL"] = top.BBL.astype(str)
    top["주소"] = top.BBL.map(heat.groupby(heat.bbl.astype(str)).addr_n.agg(lambda s: s.mode().iat[0]))
    save(70,
         metrics=[
             {"label": "난방 민원 1위 건물", "value": f"{len(h):,}건", "help": f"BBL {top_bbl} · {addr}"},
             {"label": "민원이 들어온 날", "value": f"{h.date.nunique()}일", "help": f"하루 최다 {d['난방 민원'].max()}건"},
             {"label": "중복으로 닫힌 비율", "value": f"{(h.결과 == '중복으로 묶음').mean() * 100:.0f}%"},
         ],
         charts=[
             {"title": "1위 건물의 하루 난방 민원", "kind": "line", "x": "날짜", "y": "난방 민원", "rows": records(d),
              "caption": "겨울 내내 거의 매일 들어온다. 세대가 많은 큰 건물에서 난방이 자주 끊기면 이렇게 된다."},
             {"title": "그 민원들은 어떻게 닫혔나", "kind": "barh", "x": "비율(%)", "y": "결과", "rows": records(res)},
         ],
         tables=[{"title": "난방 민원 상위 10개 건물(BBL)", "rows": records(top)}])


def q071(df):
    hpd = has_bbl(df[df.agency == "HPD"]).copy()
    hpd["결과"] = classify(hpd.resolution, HPD_RULES)
    g = hpd.groupby(hpd.bbl.astype(str)).agg(민원=("key", "size"), 유형수=("problem", "nunique"),
                                            위반발부=("결과", lambda s: (s == "위반 발부").sum()),
                                            주소=("addr_n", lambda s: s.mode().iat[0]))
    top = g.sort_values("민원", ascending=False).head(15).reset_index().rename(columns={"bbl": "BBL", "유형수": "민원 유형 수",
                                                                                      "위반발부": "결과문 '위반 발부'"})
    top["자치구"] = top.BBL.str[0].map({"1": "맨해튼", "2": "브롱크스", "3": "브루클린", "4": "퀸스", "5": "스태튼아일랜드"})
    save(71,
         metrics=[
             {"label": "최악의 집주인 목록", "value": "아직 없음", "help": "공익옹호관(Public Advocate) Worst Landlords Watchlist"},
             {"label": "HPD 민원이 있는 건물", "value": f"{len(g):,}동", "help": "BBL 기준, 12개월"},
             {"label": "상위 15개 건물 중 브롱크스", "value": f"{(top.자치구 == '브롱크스').sum()}곳"},
         ],
         charts=[
             {"title": "HPD 주거 민원 상위 15개 건물", "kind": "barh", "x": "민원", "y": "주소", "rows": records(top[["주소", "민원", "자치구"]]),
              "caption": "목록과 BBL로 맞추면 이 건물들의 집주인이 '최악의 집주인'인지 바로 확인할 수 있다."},
         ],
         tables=[{"title": "상위 15개 건물", "rows": records(top[["BBL", "주소", "자치구", "민원", "민원 유형 수", "결과문 '위반 발부'"]])}])


def q072(df):
    hpd = has_bbl(df[df.agency == "HPD"])
    hpd = hpd[hpd.problem.astype(str).isin(list(HPD_KO))]
    m = pd.crosstab(hpd.bbl.astype(str), hpd.problem.astype(str)).gt(0)
    ntype = m.sum(axis=1)
    dist = ntype.value_counts().sort_index().rename_axis("민원 유형 수").reset_index(name="건물 수")
    dist["민원 유형 수"] = dist["민원 유형 수"].astype(str) + "가지"
    cols = [c for c in m.columns if m[c].mean() >= 0.03]
    p = m[cols].mean()
    pairs = []
    for a, b in combinations(cols, 2):
        both = (m[a] & m[b]).mean()
        pairs.append({"짝": f"{HPD_KO[a]} + {HPD_KO[b]}", "함께 나온 건물": int((m[a] & m[b]).sum()),
                      "향상도(lift)": round(float(both / (p[a] * p[b])), 2)})
    pairs = pd.DataFrame(pairs).sort_values("향상도(lift)", ascending=False)
    pairs = pairs[pairs["함께 나온 건물"] >= 500].head(10)
    six = (ntype >= 6)
    save(72,
         metrics=[
             {"label": "HPD 민원이 있는 건물", "value": f"{len(m):,}동"},
             {"label": "한 가지 유형만", "value": f"{(ntype == 1).mean() * 100:.0f}%"},
             {"label": "6가지 이상 유형", "value": f"{six.sum():,}동", "help": f"{six.mean() * 100:.1f}%. '건물 증후군' 후보"},
             {"label": "위반 기록", "value": "아직 없음", "help": "신고 이전의 위반율 비교에는 HPD 위반 자료가 필요"},
         ],
         charts=[
             {"title": "건물마다 몇 가지 유형의 민원이 나왔나", "kind": "bar", "x": "민원 유형 수", "y": "건물 수", "rows": records(dist),
              "caption": "대부분은 한두 가지지만, 여러 문제가 한꺼번에 나오는 건물이 꼬리를 이룬다."},
             {"title": "함께 나오는 민원 짝(향상도 상위)", "kind": "barh", "x": "향상도(lift)", "y": "짝", "rows": records(pairs),
              "caption": "향상도 1 = 우연히 함께 나오는 수준. 2면 우연의 두 배로 함께 나온다. 500동 이상에서 함께 나온 짝만."},
         ],
         tables=[{"title": "함께 나오는 짝", "rows": records(pairs)}])


def q073(df):
    c = df[df.addr_n != ""].addr_n.value_counts().head(15)
    rows = []
    for a, n in c.items():
        s = df[df.addr_n == a]
        tp = s.problem.astype(str).value_counts()
        rows.append({"순위": len(rows) + 1, "주소": a, "민원": int(n), "자치구": BORO_KO.get(s.borough.astype(str).mode().iat[0], "?"),
                     "1위 유형": tp.index[0], "1위 몫(%)": round(tp.iat[0] / n * 100, 0)})
    rows = pd.DataFrame(rows)
    j = df[df.addr_n == "JOHN F KENNEDY AIRPORT"].problem.astype(str).value_counts()
    jr = j.head(5).rename_axis("유형").reset_index(name="민원")
    save(73,
         metrics=[
             {"label": "JFK 공항 순위", "value": f"{int(rows[rows.주소 == 'JOHN F KENNEDY AIRPORT'].순위.iat[0])}위",
              "help": f"{int(j.sum()):,}건"},
             {"label": "공항 민원 1위", "value": "택시 민원", "help": f"{int(j.iat[0]):,}건"},
             {"label": "분실물", "value": f"{int(j.get('Lost Property', 0)):,}건"},
         ],
         charts=[
             {"title": "JFK 공항 주소로 들어온 민원", "kind": "barh", "x": "민원", "y": "유형", "rows": records(jr),
              "caption": "택시·분실물처럼 '그곳을 지나간 사람'의 민원이다. 사는 사람이 없는 주소다."},
         ],
         tables=[{"title": "민원 상위 15개 주소와 1위 유형", "rows": records(rows)}])


def q074(df):
    from common import ROOT
    pg = pd.read_parquet(ROOT / "data" / "processed" / "nyc311_point_geoid.parquet").rename(columns={"unique_key": "key"})
    n = df[["key"]].merge(pg, on="key").groupby("GEOID").size()
    a = acs().set_index("GEOID")
    a = a[a.total_pop > 0].assign(n=lambda x: n.reindex(x.index).fillna(0))
    a["rate"] = a.n / a.total_pop * 1000
    pts = a.reset_index()[["GEOID", "total_pop", "rate", "borough"]].copy()
    pts = pts[pts.rate > 0]
    pts["인구"] = pts.total_pop.astype(int)
    pts["1,000명당 민원"] = pts.rate.round(0)
    pts["구분"] = np.where(pts.total_pop < 1000, "1,000명 미만(제외)", "분석 대상")
    top = a.sort_values("rate", ascending=False).head(5).reset_index()[["GEOID", "borough", "total_pop", "n", "rate"]]
    top.columns = ["GEOID", "자치구", "인구", "민원", "1,000명당"]
    top["1,000명당"] = top["1,000명당"].round(0)
    st = a[a.total_pop >= 1000]
    top_st = st.sort_values("rate", ascending=False).head(5).reset_index()[["GEOID", "borough", "total_pop", "n", "rate"]]
    top_st.columns = ["GEOID", "자치구", "인구", "민원", "1,000명당"]
    top_st["1,000명당"] = top_st["1,000명당"].round(0)
    save(74,
         metrics=[
             {"label": "민원율 1위 Tract", "value": f"{top['1,000명당'].iat[0]:,.0f}건", "help": f"인구 {int(top.인구.iat[0])}명, 민원 {int(top.민원.iat[0]):,}건"},
             {"label": "인구 1,000명 미만 Tract", "value": f"{(a.total_pop < 1000).sum()}개", "help": "분석에서 뺐다"},
             {"label": "분석 대상 중앙값", "value": f"{st.rate.median():,.0f}건", "help": "1,000명당"},
         ],
         charts=[
             {"title": "Tract 인구와 1,000명당 민원(두 축 모두 로그)", "kind": "scatter", "x": "인구", "y": "1,000명당 민원",
              "color": "구분", "colors": {"분석 대상": "#2457a7", "1,000명 미만(제외)": "#e07b39"},
              "log_x": True, "log_y": True, "rows": records(pts[["GEOID", "인구", "1,000명당 민원", "구분"]]),
              "caption": "왼쪽(인구가 적은 곳)으로 갈수록 점이 위로 치솟는다. 분모가 작으면 몇 건만으로도 비율이 폭주한다."},
         ],
         tables=[{"title": "민원율 상위 5(전체 Tract)", "rows": records(top)},
                 {"title": "민원율 상위 5(인구 1,000명 이상)", "rows": records(top_st)}])


def q075(df):
    lt = df.loc_type.astype(str).replace("nan", "(없음)").value_counts()
    top = lt.head(15).rename_axis("장소 유형(Location Type)").reset_index(name="민원")
    res = [k for k in lt.index if any(w in k.lower() for w in ["residential", "family", "apartment", "apt", "house", "dwelling"])
           and not any(w in k.lower() for w in ["worship", "non-residential", "warehouse", "firehouse"])]
    rr = lt[res].sort_values(ascending=False).head(10).rename_axis("주거 관련 장소 유형").reset_index(name="민원")
    save(75,
         metrics=[
             {"label": "PLUTO 자료", "value": "아직 없음", "help": "건물 용도·세대 수·건축연도(BBL)"},
             {"label": "장소 유형 종류", "value": f"{len(lt):,}가지", "help": "311 Location Type 열"},
             {"label": "주거 관련 표기", "value": f"{len(res)}가지", "help": "같은 뜻이 여러 이름으로 적혀 있다"},
         ],
         charts=[
             {"title": "주거 관련 장소 유형 표기 상위 10", "kind": "barh", "x": "민원", "y": "주거 관련 장소 유형", "rows": records(rr),
              "caption": "'3+ Family Apt. Building'과 '3+ Family Apartment Building'처럼 같은 뜻이 다른 이름으로 들어온다. 311 열만으로는 건물 종류를 깨끗하게 가르기 어렵다."},
         ],
         tables=[{"title": "장소 유형 상위 15", "rows": records(top)}])


def q076(df, bp):
    det = df.detail.astype(str)
    ic = df[det.str.contains("Illegal Conversion", case=False)]
    by = (ic.borough.value_counts().reindex(BOROS) / bp.reindex(BOROS) * 1e5).round(1)
    rows = pd.DataFrame({"자치구": [BORO_KO[b] for b in BOROS], "10만 명당 불법 개조 민원": by.values,
                         "민원": ic.borough.value_counts().reindex(BOROS).fillna(0).astype(int).values})
    dd = ic.detail.astype(str).value_counts().head(5).rename_axis("세부 유형").reset_index(name="민원")
    save(76,
         metrics=[
             {"label": "세금 체납 목록", "value": "아직 없음", "help": "DOF Tax Lien Sale 목록(BBL)"},
             {"label": "불법 개조 의심 민원", "value": f"{len(ic):,}건", "help": "세부 유형에 'Illegal Conversion'"},
             {"label": "가장 많은 자치구", "value": rows.sort_values("10만 명당 불법 개조 민원").자치구.iat[-1], "help": "10만 명당"},
         ],
         charts=[
             {"title": "자치구별 불법 개조 의심 민원", "kind": "bar", "x": "자치구", "y": "10만 명당 불법 개조 민원", "alt_y": "민원",
              "rows": records(rows), "sort": "-y",
              "caption": "지하실·차고를 몰래 주거로 바꾸거나 한 집을 여러 칸으로 쪼갠 경우다. 체납·저당 정보와 겹치면 위험 건물을 더 잘 고를 수 있다."},
         ],
         tables=[{"title": "불법 개조 세부 유형", "rows": records(dd)}])


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} or set(range(69, 77))
    df = load_311()
    jobs = {69: q069, 70: q070, 71: q071, 72: q072, 73: q073, 74: q074, 75: q075}
    for k in sorted(want):
        if k == 76:
            q076(df, borough_pop())
        else:
            jobs[k](df)
