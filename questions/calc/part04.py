"""4부. 세입자·소득·인종: 누가 무엇을 신고하나 — 통계 계산.
문항 33–48. 실행: python questions/calc/part04.py  (일부만: python questions/calc/part04.py 36 39)
48번은 HOLC 지도를 붙여야 해서 해설만 둔다.
인종 관련 수치는 모두 동네(Tract) 단위 비교다. 개인의 행동을 뜻하지 않는다.
"""
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BORO_KO, HPD_RULES, INC_Q, MAJOR_ORDER, Q5, RACE_KO, category,  # noqa: E402
                    classify, load_311, records, save, tract_rates, with_tract)

BOROS = list(BORO_KO)
CATS = ["주거환경", "소음", "도로·교통", "위생", "해충·동물"]
MAJOR_COLORS = dict(zip(MAJOR_ORDER, ["#e07b39", "#8e5cc4", "#2457a7", "#6b7a8f", "#3a9d6e"]))
Q5_COLORS = dict(zip(Q5, ["#c9d6ea", "#9fb3d1", "#6f8fbf", "#3f6aa9", "#1d3f7a"]))
INC_COLORS = dict(zip(INC_Q, Q5_COLORS.values()))


HOT = "655 EAST 230 STREET"  # 11번 이상치 주소. 흑인 다수·소득 최하위·임차율 최상위 Tract에 있다.


def rho(a, b) -> float:
    return round(float(spearmanr(a, b, nan_policy="omit")[0]), 2)


def per_k(sub, t, by, denom="total_pop", order=None) -> pd.Series:
    r = sub.groupby(by, observed=True).size() / t.groupby(by, observed=True)[denom].sum() * 1000
    return r.reindex(order) if order else r


def q033(dt, t):
    r = per_k(dt, t, "major", order=MAJOR_ORDER)
    r_ex = per_k(dt[dt.addr_n != HOT], t, "major", order=MAJOR_ORDER)
    n = t.major.value_counts().reindex(MAJOR_ORDER)
    rows = pd.DataFrame({"과반 집단": MAJOR_ORDER, "1,000명당 민원": r.round(1).values,
                         "이상치 주소 제외": r_ex.round(1).values, "Tract 수": n.values})
    save(33,
         metrics=[{"label": k, "value": f"{v:,.1f}건",
                   "help": f"Tract {n[k]:,}개" + (f". 655 E 230th St를 빼면 {r_ex[k]:,.1f}건" if abs(v - r_ex[k]) > 1 else "")}
                  for k, v in r.items()],
         charts=[
             {"title": "과반 집단별 1,000명당 민원", "kind": "bar", "x": "과반 집단", "y": "1,000명당 민원", "rows": records(rows),
              "caption": "Tract 인구의 50% 이상을 차지하는 집단으로 동네를 나눴다. 어느 집단도 50%가 안 되면 '과반 없음'."},
         ],
         tables=[{"title": "과반 집단별", "rows": records(rows)}])


def q034(dt, t):
    rows = []
    for c in CATS:
        r = per_k(dt[dt.cat == c], t, "major", order=MAJOR_ORDER)
        for k, v in r.items():
            rows.append({"분야": c, "과반 집단": k, "1,000명당": round(float(v), 1)})
    p = pd.DataFrame(rows).pivot(index="분야", columns="과반 집단", values="1,000명당").reindex(CATS)[MAJOR_ORDER]
    h = p.loc["주거환경"]
    bn_ex = per_k(dt[(dt.cat == "소음") & (dt.addr_n != HOT)], t, "major", order=MAJOR_ORDER)["흑인 다수"]
    save(34,
         metrics=[
             {"label": "주거: 히스패닉 다수", "value": f"{h['히스패닉 다수']:.1f}건", "help": "1,000명당"},
             {"label": "주거: 백인 다수", "value": f"{h['백인 다수']:.1f}건"},
             {"label": "격차", "value": f"{h['히스패닉 다수'] / h['백인 다수']:.1f}배"},
             {"label": "도로·교통 범위", "value": f"{int(p.loc['도로·교통'].min() + 0.5)}–{int(p.loc['도로·교통'].max() + 0.5)}건",
              "help": "집단 간 차이가 작다"},
             {"label": "소음: 흑인 다수", "value": f"{p.loc['소음', '흑인 다수']:.1f}건",
              "help": f"655 E 230th St 한 주소를 빼면 {bn_ex:.1f}건(→ 11번)"},
         ],
         charts=[
             {"title": "분야별·과반 집단별 1,000명당 민원", "kind": "group", "x": "분야", "y": "1,000명당", "color": "과반 집단",
              "colors": MAJOR_COLORS, "rows": rows,
              "caption": "주거환경과 소음에서 집단 차이가 크고, 도로·교통은 거의 같다."},
         ],
         tables=[{"title": "분야 × 과반 집단(1,000명당)", "rows": records(p.reset_index())}])


def q035(t):
    vars_ = {"임차율": "renter_rate", "빈곤율": "poverty_rate", "1950년 이전 주택 비율": "pre1950_share",
             "중위 가구소득": "median_income"}
    rows = [{"히스패닉 비율과 함께 본 변수": k, "Spearman 상관": rho(t.hispanic_rate, t[v])} for k, v in vars_.items()]
    pts = t.dropna(subset=["renter_rate"]).assign(**{"히스패닉 비율(%)": lambda x: (x.hispanic_rate * 100).round(1),
                                                    "임차율(%)": lambda x: (x.renter_rate * 100).round(1)})
    save(35,
         metrics=[{"label": f"히스패닉 비율 × {r['히스패닉 비율과 함께 본 변수']}", "value": f"{r['Spearman 상관']:.2f}"} for r in rows],
         charts=[
             {"title": "히스패닉 비율이 함께 움직이는 변수", "kind": "barh", "x": "Spearman 상관", "y": "히스패닉 비율과 함께 본 변수",
              "rows": rows, "caption": "히스패닉 비율이 높은 동네는 세입자와 빈곤 가구도 많다. 34번의 차이에는 이 변수들이 섞여 있다."},
             {"title": "Tract마다 본 히스패닉 비율과 임차율", "kind": "scatter", "x": "히스패닉 비율(%)", "y": "임차율(%)", "trend": True,
              "rows": records(pts[["GEOID", "히스패닉 비율(%)", "임차율(%)"]])},
         ])


def q036(dt, t):
    hh = dt[dt.problem == "HEAT/HOT WATER"]
    g = (hh.groupby(["inc_q", "his_q"], observed=True).size()
         / t.groupby(["inc_q", "his_q"], observed=True).renter_occupied.sum() * 1000)
    ntr = t.groupby(["inc_q", "his_q"], observed=True).size()
    rows = [{"소득 5분위": str(i), "히스패닉 비율 5분위": h, "임차가구 1,000가구당 난방 민원": round(float(g.get((i, h), float("nan"))), 0),
             "Tract 수": int(ntr.get((i, h), 0))} for i in INC_Q for h in Q5]
    grid = pd.DataFrame(rows).pivot(index="소득 5분위", columns="히스패닉 비율 5분위", values="임차가구 1,000가구당 난방 민원").reindex(INC_Q)[Q5]
    low = grid.loc[INC_Q[0]]
    save(36,
         metrics=[
             {"label": "소득 최하위: 히스패닉 최하위", "value": f"{low[Q5[0]]:.0f}건", "help": "임차가구 1,000가구당 난방 민원"},
             {"label": "소득 최하위: 히스패닉 최상위", "value": f"{low[Q5[-1]]:.0f}건"},
             {"label": "격차", "value": f"{low[Q5[-1]] / low[Q5[0]]:.1f}배"},
             {"label": "소득 최상위: 히스패닉 최상위", "value": f"{grid.loc[INC_Q[-1], Q5[-1]]:.0f}건", "help": "차이가 사라진다"},
         ],
         charts=[
             {"title": "소득을 맞춘 뒤 히스패닉 비율에 따른 난방 민원", "kind": "line", "x": "히스패닉 비율 5분위",
              "y": "임차가구 1,000가구당 난방 민원", "color": "소득 5분위", "colors": INC_COLORS, "point": True, "rows": rows,
              "caption": "선 하나가 소득 분위 하나. 가장 옅은 선(소득 최하위)만 오른쪽 끝에서 크게 튄다."},
         ],
         tables=[{"title": "소득 × 히스패닉 비율(임차가구 1,000가구당)", "rows": records(grid.reset_index())},
                 {"title": "칸마다 Tract 수",
                  "rows": records(pd.DataFrame(rows).pivot(
                      index="소득 5분위", columns="히스패닉 비율 5분위", values="Tract 수"
                  ).reindex(INC_Q)[Q5].reset_index())}])


def q037(dt, t):
    hs = dt[(dt.problem == "HEAT/HOT WATER") & (dt.created < "2026-06-01")].copy()
    hs["결과"] = classify(hs.resolution, HPD_RULES)
    share = (hs.groupby("his_q", observed=True).결과.apply(lambda s: (s == "위반 발부").mean() * 100)).reindex(Q5)
    rate = (hs.groupby("his_q", observed=True).size() / t.groupby("his_q", observed=True).renter_occupied.sum() * 1000).reindex(Q5)
    rows = pd.DataFrame({"히스패닉 비율 5분위": Q5, "임차가구 1,000가구당 난방 민원": rate.round(0).values,
                         "결과문 '위반 발부' 비율(%)": share.round(1).values})
    save(37,
         metrics=[
             {"label": "난방 민원: 히스패닉 최상위 ÷ 최하위",
              "value": f"{rate.iat[-1] / rate.iat[0]:.1f}배", "help": "임차가구당, 2025-11 ~ 2026-05"},
             {"label": "'위반 발부' 비율: 최하위", "value": f"{share.iat[0]:.1f}%"},
             {"label": "'위반 발부' 비율: 최상위", "value": f"{share.iat[-1]:.1f}%"},
         ],
         charts=[
             {"title": "신고 1건이 위반으로 이어지는 비율(대리 지표)", "kind": "bar", "x": "히스패닉 비율 5분위",
              "y": "결과문 '위반 발부' 비율(%)", "alt_y": "임차가구 1,000가구당 난방 민원", "rows": records(rows),
              "caption": ("신고 1건이 '위반 발부'로 닫히는 비율은 분위마다 거의 같다(약 5%). "
                          "신고가 2배 많은 곳은 확인된 위반도 대략 2배라는 뜻이고, 신고가 '과잉'이라는 흔적은 없다. "
                          "과소신고 판정에는 HPD 위반 기록 전체가 필요하다(→ 7번).")},
         ],
         tables=[{"title": "히스패닉 비율 5분위", "rows": records(rows)}])


ROD_RULES = [(r"found violations|minor violations", "위반 발견"), (r"did not find any violations", "위반 없음(통과)"),
             (r"earlier complaint", "중복(앞선 신고)"), (r"could not access", "점검 못 함")]


def q038(dt, t, df, bp):
    rod = dt[dt.problem == "Rodent"]
    r = per_k(rod, t, "inc_q", order=INC_Q)
    rows = pd.DataFrame({"소득 5분위": INC_Q, "1,000명당 쥐 민원": r.round(2).values})
    rb = (df[df.problem == "Rodent"].borough.value_counts().reindex(BOROS) / bp.reindex(BOROS) * 1e5).round(1)
    brows = pd.DataFrame({"자치구": [BORO_KO[b] for b in BOROS], "10만 명당 쥐 민원": rb.values})
    tt = t.assign(r=t.GEOID.map(rod.groupby("GEOID").size()).fillna(0) / t.total_pop)
    save(38,
         metrics=[
             {"label": "쥐 민원(12개월)", "value": f"{(df.problem == 'Rodent').sum():,}건", "help": "보건국(DOHMH)"},
             {"label": "소득 최하위 → 최상위", "value": f"{r.iat[0]:.1f} → {r.iat[-1]:.1f}건", "help": "1,000명당"},
             {"label": "1위 자치구", "value": brows.sort_values("10만 명당 쥐 민원").자치구.iat[-1],
              "help": f"10만 명당 {rb.max():.0f}건"},
             {"label": "빈곤율 × 해충·동물 분야", "value": f"{rho(t.poverty_rate, t['해충·동물']):.2f}",
              "help": f"Tract 단위. 쥐만 보면 {rho(tt.poverty_rate, tt.r):+.2f}"},
         ],
         charts=[
             {"title": "소득 5분위별 쥐 민원", "kind": "bar", "x": "소득 5분위", "y": "1,000명당 쥐 민원", "rows": records(rows),
              "caption": "부유할수록 조금씩 많다. 다른 민원과 반대 방향이다."},
             {"title": "자치구별 쥐 민원", "kind": "bar", "x": "자치구", "y": "10만 명당 쥐 민원", "rows": records(brows), "sort": "-y"},
         ],
         tables=[{"title": "소득 5분위", "rows": records(rows)}])


def q039(dt):
    rod = dt[dt.problem == "Rodent"].copy()
    rod["결과"] = classify(rod.resolution, ROD_RULES)
    insp = rod[rod.결과.isin(["위반 발견", "위반 없음(통과)"])]
    hit = (insp.groupby("inc_q", observed=True).결과.apply(lambda s: (s == "위반 발견").mean() * 100)).reindex(INC_Q)
    n = insp.groupby("inc_q", observed=True).size().reindex(INC_Q)
    rows = pd.DataFrame({"소득 5분위": INC_Q, "점검에서 위반 발견(%)": hit.round(1).values, "점검된 민원": n.values})
    mix = rod.결과.value_counts(normalize=True).mul(100).round(1).rename_axis("결과").reset_index(name="비율(%)")
    save(39,
         metrics=[
             {"label": "점검까지 간 쥐 민원", "value": f"{len(insp):,}건", "help": f"전체 {len(rod):,}건 중(Tract 연결분)"},
             {"label": "위반 발견: 소득 최하위", "value": f"{hit.iat[0]:.0f}%"},
             {"label": "위반 발견: 소득 최상위", "value": f"{hit.iat[-1]:.0f}%"},
         ],
         charts=[
             {"title": "신고가 점검으로 이어졌을 때 위반이 나온 비율", "kind": "bar", "x": "소득 5분위", "y": "점검에서 위반 발견(%)",
              "rows": records(rows),
              "caption": ("가난한 동네의 신고일수록 점검에서 실제 위반이 더 자주 나온다면, "
                          "신고는 적어도 문제는 크다는 뜻이다.")},
             {"title": "쥐 민원은 어떻게 닫혔나", "kind": "barh", "x": "비율(%)", "y": "결과", "rows": records(mix)},
         ],
         tables=[{"title": "소득 5분위", "rows": records(rows)}])


NOISE_KO = {"Noise - Residential": "주거(이웃)", "Noise - Street/Sidewalk": "길거리", "Noise - Vehicle": "차량",
            "Noise - Commercial": "상업 시설", "Noise": "공사·기타(DEP)"}


def q040(dt, t):
    nz = dt[dt.cat == "소음"]
    r = per_k(nz, t, "inc_q", order=INC_Q)
    r_ex = per_k(nz[nz.addr_n != "655 EAST 230 STREET"], t, "inc_q", order=INC_Q)  # 11번 이상치 주소 제외
    sub = nz[nz.problem.astype(str).isin(["Noise - Residential", "Noise - Street/Sidewalk", "Noise - Vehicle",
                                           "Noise - Commercial", "Noise"])]
    lines = []
    for p, g in sub.groupby(sub.problem.astype(str)):
        rr = per_k(g, t, "inc_q", order=INC_Q)
        for q, v in rr.items():
            lines.append({"소음 유형": NOISE_KO[p], "소득 5분위": q, "1,000명당": round(float(v), 1)})
    save(40,
         metrics=[
             {"label": "소득 최하위", "value": f"{r.iat[0]:.1f}건", "help": "1,000명당 소음 민원"},
             {"label": "소득 최상위", "value": f"{r.iat[-1]:.1f}건"},
             {"label": "격차", "value": f"{r.iat[0] / r.iat[-1]:.1f}배"},
             {"label": "이상치 주소를 빼면", "value": f"{r_ex.iat[0] / r_ex.iat[-1]:.1f}배",
              "help": f"655 E 230th St가 최하위 분위에 있다. 빼면 최하위 {r_ex.iat[0]:.1f}건"},
         ],
         charts=[
             {"title": "소득 5분위별 소음 민원(세부 유형)", "kind": "line", "x": "소득 5분위", "y": "1,000명당", "color": "소음 유형",
              "rows": lines, "point": True,
              "caption": "격차의 대부분은 주거 소음(이웃)과 길거리 소음에서 나온다. 주거 소음 최하위 분위 값에는 한 주소의 4.7만 건이 들어 있다."},
         ],
         tables=[{"title": "소득 5분위별 소음", "rows": [{"소득 5분위": q, "1,000명당 소음": round(float(v), 1),
                                                       "이상치 주소 제외": round(float(r_ex[q]), 1)} for q, v in r.items()]}])


def channel_mix(dt, by, order):
    ch = dt[dt.channel.notna() & (dt.channel.astype(str) != "UNKNOWN")]
    m = (ch.groupby([by, "channel"], observed=True).size() / ch.groupby(by, observed=True).size() * 100).rename("비율(%)").reset_index()
    m = m[m.channel.isin(["PHONE", "ONLINE", "MOBILE"])]
    m["경로"] = m.channel.map({"PHONE": "전화", "ONLINE": "온라인(웹)", "MOBILE": "모바일 앱"})
    m[by] = m[by].astype(str)
    m["비율(%)"] = m["비율(%)"].round(1)
    return m


def q041(dt):
    mj = channel_mix(dt, "major", MAJOR_ORDER).rename(columns={"major": "과반 집단"})
    inc = channel_mix(dt, "inc_q", INC_Q).rename(columns={"inc_q": "소득 5분위"})
    def ph(m, col, k):
        return m[(m.경로 == "전화") & (m[col] == k)]["비율(%)"].iat[0]
    colors = {"전화": "#e07b39", "온라인(웹)": "#2457a7", "모바일 앱": "#9fb3d1"}
    save(41,
         metrics=[
             {"label": "전화: 소득 최하위", "value": f"{ph(inc, '소득 5분위', INC_Q[0]):.1f}%"},
             {"label": "전화: 소득 최상위", "value": f"{ph(inc, '소득 5분위', INC_Q[-1]):.1f}%"},
             {"label": "전화: 흑인 다수", "value": f"{ph(mj, '과반 집단', '흑인 다수'):.1f}%"},
             {"label": "전화: 백인 다수", "value": f"{ph(mj, '과반 집단', '백인 다수'):.1f}%"},
         ],
         charts=[
             {"title": "과반 집단별 신고 경로", "kind": "stackh", "x": "비율(%)", "y": "과반 집단", "color": "경로", "colors": colors,
              "rows": records(mj[["과반 집단", "경로", "비율(%)"]])},
             {"title": "소득 5분위별 신고 경로", "kind": "stackh", "x": "비율(%)", "y": "소득 5분위", "color": "경로", "colors": colors,
              "rows": records(inc[["소득 5분위", "경로", "비율(%)"]]), "caption": "경로 미상(약 8%)과 기타(0.1%)는 뺐다."},
         ])


def q042(dt, t):
    ch = dt[dt.channel.notna() & (dt.channel.astype(str) != "UNKNOWN")]
    g = ch.groupby("GEOID").agg(n=("key", "size"), ph=("channel", lambda s: (s.astype(str) == "PHONE").mean() * 100))
    g = g[g.n >= 200].join(t.set_index("GEOID")[["median_income", "boro_acs"]]).dropna(subset=["median_income"])
    g["중위 가구소득(천 달러)"] = (g.median_income / 1000).round(0)
    g["전화 신고 비율(%)"] = g.ph.round(1)
    g["자치구"] = g.boro_acs.map(BORO_KO)
    save(42,
         metrics=[
             {"label": "인터넷·언어 자료", "value": "아직 없음", "help": "ACS B28002, C16002를 받아 붙여야 한다"},
             {"label": "Tract 전화 비율 × 소득", "value": f"{rho(g.median_income, g.ph):.2f}", "help": f"민원 200건 이상 Tract {len(g):,}개"},
         ],
         charts=[
             {"title": "Tract마다 본 소득과 전화 신고 비율", "kind": "scatter", "x": "중위 가구소득(천 달러)", "y": "전화 신고 비율(%)",
              "trend": True, "rows": records(g.reset_index()[["GEOID", "자치구", "중위 가구소득(천 달러)", "전화 신고 비율(%)"]]),
              "caption": "소득이 낮을수록 전화 비율이 높다. 인터넷 가입률과 영어 미숙 비율을 붙이면 이 기울기가 어디서 오는지 가를 수 있다."},
         ])


def q043(dt, t):
    prof = t.groupby("major").agg(Tract=("GEOID", "size"), 인구=("total_pop", "sum"),
                                  소득=("median_income", "median"), 임차율=("renter_rate", "median"))
    prof = prof.reindex(MAJOR_ORDER)
    rate = per_k(dt, t, "major", order=MAJOR_ORDER)
    out = pd.DataFrame({"과반 집단": MAJOR_ORDER, "1,000명당 민원": rate.round(1).values,
                        "중위 가구소득 중앙값($)": prof.소득.round(-2).astype(int).values,
                        "임차율 중앙값(%)": (prof.임차율 * 100).round(0).values, "Tract 수": prof.Tract.values})
    ph = channel_mix(dt, "major", MAJOR_ORDER)
    ph = ph[ph.경로 == "전화"].set_index("major")["비율(%)"].reindex(MAJOR_ORDER)
    out["전화 신고 비율(%)"] = ph.values
    a = out.set_index("과반 집단").loc["아시아계 다수"]
    save(43,
         metrics=[
             {"label": "아시아계 다수 Tract", "value": f"{a['1,000명당 민원']:.0f}건", "help": "1,000명당, 다섯 집단 중 가장 적다"},
             {"label": "그 동네의 임차율 중앙값", "value": f"{a['임차율 중앙값(%)']:.0f}%"},
             {"label": "그 동네의 전화 신고 비율", "value": f"{a['전화 신고 비율(%)']:.1f}%"},
         ],
         charts=[
             {"title": "과반 집단별 임차율과 민원율", "kind": "bar", "x": "과반 집단", "y": "1,000명당 민원", "alt_y": "임차율 중앙값(%)",
              "rows": records(out), "caption": "세로축을 바꿔 보자. 임차율이 낮은 것은 민원이 적은 이유 후보 중 하나다."},
         ],
         tables=[{"title": "과반 집단 프로필", "rows": records(out)}])


def q044(t):
    tt = t.dropna(subset=["median_income"])
    within = [{"자치구": BORO_KO[b], "Spearman 상관": rho(g.median_income, g.rate), "Tract 수": len(g)} for b, g in tt.groupby("boro_acs")]
    pts = tt.assign(**{"중위 가구소득(천 달러)": (tt.median_income / 1000).round(0), "1,000명당 민원": tt.rate.round(0),
                       "자치구": tt.boro_acs.map(BORO_KO)})
    pts = pts[pts["1,000명당 민원"] <= pts["1,000명당 민원"].quantile(0.99)]
    save(44,
         metrics=[{"label": "시 전체", "value": f"{rho(tt.median_income, tt.rate):.2f}", "help": f"Tract {len(tt):,}개"}]
         + [{"label": w["자치구"], "value": f"{w['Spearman 상관']:+.2f}", "help": f"Tract {w['Tract 수']}개"} for w in within],
         charts=[
             {"title": "자치구 안에서 본 소득과 민원율의 상관", "kind": "bar", "x": "자치구", "y": "Spearman 상관", "rows": within,
              "caption": "브루클린만 양수다."},
             {"title": "Tract마다 본 소득과 민원율", "kind": "scatter", "x": "중위 가구소득(천 달러)", "y": "1,000명당 민원", "color": "자치구",
              "rows": records(pts[["GEOID", "자치구", "중위 가구소득(천 달러)", "1,000명당 민원"]]), "caption": "위쪽 1%는 그림에서만 뺐다."},
         ],
         tables=[{"title": "자치구별 상관", "rows": within}])


def q045(dt, t):
    rows, raw = [], []
    clean = dt[dt.addr_n != HOT]  # 이상치 주소가 브롱크스 안 소득 최하위 분위에 있어 그 칸을 1,000명당 152건 부풀린다
    for b, g in t.dropna(subset=["median_income"]).groupby("boro_acs"):
        g = g.assign(bq=pd.qcut(g.median_income, 5, labels=Q5))
        pop = g.groupby("bq", observed=True).total_pop.sum()
        for src, out in [(clean, rows), (dt, raw)]:
            r = src[src.GEOID.isin(g.GEOID)].merge(g[["GEOID", "bq"]], on="GEOID").groupby("bq", observed=True).size() / pop * 1000
            for q, v in r.reindex(Q5).items():
                out.append({"자치구": BORO_KO[b], "자치구 안 소득 5분위": q, "1,000명당 민원": round(float(v), 0)})
    df = pd.DataFrame(rows)
    bx_raw = pd.DataFrame(raw).query("자치구 == '브롱크스'").set_index("자치구 안 소득 5분위")["1,000명당 민원"]
    bk = df[df.자치구 == "브루클린"].set_index("자치구 안 소득 5분위")["1,000명당 민원"]
    save(45,
         metrics=[
             {"label": "브루클린: 소득 최하위", "value": f"{bk.iat[0]:.0f}건", "help": "자치구 안에서 나눈 5분위, 1,000명당"},
             {"label": "브루클린: 소득 최상위", "value": f"{bk.iat[-1]:.0f}건"},
             {"label": "시 전체 상관", "value": "−0.13", "help": "44번"},
             {"label": "브롱크스 최하위 분위", "value": f"{bx_raw.iat[0]:.0f} → {df[df.자치구 == '브롱크스']['1,000명당 민원'].iat[0]:.0f}건",
              "help": "655 E 230th St 한 주소를 빼기 전 → 뺀 뒤"},
         ],
         charts=[
             {"title": "자치구마다 소득 5분위를 따로 나눈 민원율(이상치 주소 제외)", "kind": "line", "x": "자치구 안 소득 5분위",
              "y": "1,000명당 민원", "color": "자치구", "rows": rows, "point": True,
              "caption": ("다른 자치구는 오른쪽으로 내려가거나 평평한데, 브루클린만 오른쪽으로 올라간다. "
                          "655 E 230th St(4.7만 건)는 브롱크스 최하위 칸 하나를 크게 부풀려서 뺐다.")},
         ],
         tables=[{"title": "자치구 × 자치구 안 소득 5분위",
                  "rows": records(df.pivot(
                      index="자치구", columns="자치구 안 소득 5분위", values="1,000명당 민원"
                  )[Q5].reset_index())}])


def q046(t):
    low = t[t.inc_q.isin(INC_Q[:2])].dropna(subset=["소음"])
    rows = []
    for b, g in low.groupby("boro_acs"):
        for p, lab in [(0.25, "하위 25%"), (0.5, "중앙값"), (0.75, "상위 25%")]:
            rows.append({"자치구": BORO_KO[b], "분위점": lab, "1,000명당 소음 민원": round(float(g.소음.quantile(p)), 0)})
    save(46,
         metrics=[
             {"label": "ACS 두 시점", "value": "아직 없음", "help": "2015–2019 5개년을 더 받아야 '변화'를 잴 수 있다"},
             {"label": "저소득(Q1–Q2) Tract", "value": f"{len(low):,}개"},
             {"label": "그 안의 소음 민원 격차",
              "value": f"{low.소음.quantile(0.75) / low.소음.quantile(0.25):.1f}배", "help": "상위 25% ÷ 하위 25%"},
         ],
         charts=[
             {"title": "저소득 동네끼리도 소음 민원은 크게 다르다", "kind": "group", "x": "자치구", "y": "1,000명당 소음 민원",
              "color": "분위점", "colors": {"하위 25%": "#c9d6ea", "중앙값": "#6f8fbf", "상위 25%": "#1d3f7a"}, "rows": rows,
              "caption": "이 차이 가운데 '젠트리피케이션 중'이라는 변화가 얼마를 설명하는지가 46번의 질문이다."},
         ])


def q047(t):
    rows = []
    for c in ["주거환경", "소음", "도로·교통"]:
        for r, lab in RACE_KO.items():
            rows.append({"분야": c, "집단 비율": lab, "Spearman 상관": rho(t[r], t[c])})
    p = pd.DataFrame(rows).pivot(index="분야", columns="집단 비율", values="Spearman 상관")
    save(47,
         metrics=[
             {"label": "흑인 비율 × 주거", "value": f"{p.loc['주거환경', '흑인']:.2f}"},
             {"label": "히스패닉 비율 × 주거", "value": f"{p.loc['주거환경', '히스패닉']:.2f}"},
             {"label": "히스패닉 비율 × 소음", "value": f"{p.loc['소음', '히스패닉']:.2f}"},
             {"label": "흑인 비율 × 소음", "value": f"{p.loc['소음', '흑인']:.2f}"},
         ],
         charts=[
             {"title": "Tract 집단 비율과 분야별 민원율의 상관", "kind": "group", "x": "분야", "y": "Spearman 상관", "color": "집단 비율",
              "colors": {"히스패닉": "#e07b39", "흑인": "#2457a7", "백인": "#6b7a8f", "아시아계": "#3a9d6e"}, "rows": rows,
              "caption": "막대가 위로 가면 그 집단 비율이 높은 동네에서 그 분야 민원이 많다는 뜻이다."},
         ],
         tables=[{"title": "상관 행렬", "rows": records(p.reset_index())}])


if __name__ == "__main__":
    from common import borough_pop
    want = {int(a) for a in sys.argv[1:]} or set(range(33, 49))
    df = load_311()
    dt = with_tract(df)
    dt["cat"] = category(dt.problem)
    t = tract_rates(dt, CATS)
    jobs = {33: lambda: q033(dt, t), 34: lambda: q034(dt, t), 35: lambda: q035(t), 36: lambda: q036(dt, t),
            37: lambda: q037(dt, t), 38: lambda: q038(dt, t, df, borough_pop()), 39: lambda: q039(dt), 40: lambda: q040(dt, t),
            41: lambda: q041(dt), 42: lambda: q042(dt, t), 43: lambda: q043(dt, t), 44: lambda: q044(t),
            45: lambda: q045(dt, t), 46: lambda: q046(t), 47: lambda: q047(t)}
    for k in sorted(want & set(jobs)):
        jobs[k]()
