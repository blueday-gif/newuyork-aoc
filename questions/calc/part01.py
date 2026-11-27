"""1부. 기사 한 편을 데이터로 다시 보기 — 통계 계산.
문항 1–12. 실행: python questions/calc/part01.py  (일부만: python questions/calc/part01.py 3 8)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BORO_KO, HPD_RULES, INC_Q, borough_pop, classify, load_311,  # noqa: E402
                    records, save, with_tract)

BOROS = list(BORO_KO)
SNOW_WEEK = ("2026-02-22 18:00", "2026-03-03")
HEAT_SEASON_END = "2026-06-01"
SNOW_RULES = [
    (r"cannot respond to individual requests", "개별 대응 불가(일괄 종결)"),
    (r"no violation|no condition", "가 보니 문제 없음"),
    (r"plowed|cleaned|salted|removed", "치움·청소함"),
]


def snow_week(df):
    s = df[(df.problem == "Snow or Ice") & (df.created >= SNOW_WEEK[0]) & (df.created < SNOW_WEEK[1])]
    return s[s.borough.isin(BOROS)]


def heat_season(df):
    return df[(df.problem == "HEAT/HOT WATER") & (df.created < HEAT_SEASON_END)]


def q002(df, bp):
    w = snow_week(df)
    cnt = w.borough.value_counts().reindex(BOROS).astype(int)
    pop = bp.reindex(BOROS)
    share = pd.DataFrame({"자치구": [BORO_KO[b] for b in BOROS],
                          "눈 민원 몫(%)": (cnt / cnt.sum() * 100).round(1).values,
                          "인구 몫(%)": (pop / pop.sum() * 100).round(1).values})
    long = share.melt(id_vars="자치구", var_name="구분", value_name="비율(%)")
    rate = pd.DataFrame({"자치구": [BORO_KO[b] for b in BOROS], "눈 민원": cnt.values,
                         "10만 명당": (cnt / pop * 1e5).round(0).values})
    si, mn = rate.set_index("자치구").loc["스태튼아일랜드"], rate.set_index("자치구").loc["맨해튼"]
    save(2,
         metrics=[
             {"label": "폭설 1주일 눈 민원", "value": f"{cnt.sum():,}건", "help": "2/22 18시 ~ 3/2, 자치구 미상 1건 제외"},
             {"label": "스태튼아일랜드 몫", "value": f"{cnt['STATEN ISLAND'] / cnt.sum() * 100:.0f}%",
              "help": f"{cnt['STATEN ISLAND']:,}건, 인구 몫은 {pop['STATEN ISLAND'] / pop.sum() * 100:.0f}%"},
             {"label": "10만 명당", "value": f"{si['10만 명당']:,.0f}건", "help": f"맨해튼 {mn['10만 명당']:,.0f}건"},
             {"label": "맨해튼 대비", "value": f"{si['10만 명당'] / mn['10만 명당']:.0f}배", "help": "10만 명당 기준"},
         ],
         charts=[
             {"title": "눈 민원 몫과 인구 몫", "kind": "group", "x": "자치구", "y": "비율(%)", "color": "구분",
              "colors": {"눈 민원 몫(%)": "#2457a7", "인구 몫(%)": "#b9c4d4"}, "rows": records(long),
              "caption": "두 막대가 비슷하면 '인구만큼 신고했다'는 뜻이다. 스태튼아일랜드만 크게 어긋난다."},
             {"title": "자치구별 눈 민원(폭설 1주일)", "kind": "bar", "x": "자치구", "y": "10만 명당", "alt_y": "눈 민원",
              "rows": records(rate), "sort": "-y"},
         ],
         tables=[{"title": "자치구별 눈 민원과 인구 몫", "rows": records(share.merge(rate, on="자치구"))}])


def q003(df):
    w = snow_week(df).copy()
    w["결과"] = classify(w.resolution, SNOW_RULES)
    med = w.groupby("borough").hours.median().reindex(BOROS).round(1)
    mix = (w.groupby(["borough", "결과"]).size() / w.groupby("borough").size() * 100).round(1)
    mix = mix.rename("비율(%)").reset_index()
    mix["자치구"] = mix.borough.map(BORO_KO)
    order = ["개별 대응 불가(일괄 종결)", "가 보니 문제 없음", "치움·청소함", "기타"]
    medf = pd.DataFrame({"자치구": [BORO_KO[b] for b in BOROS], "처리시간 중앙값(시간)": med.values})
    si_auto = mix[(mix.borough == "STATEN ISLAND") & (mix.결과 == order[0])]["비율(%)"].iat[0]
    bk_auto = mix[(mix.borough == "BROOKLYN") & (mix.결과 == order[0])]["비율(%)"].iat[0]
    plowed = (w.결과 == "치움·청소함").mean() * 100
    save(3,
         metrics=[
             {"label": "처리시간 중앙값: 스태튼아일랜드", "value": f"{med['STATEN ISLAND']}시간"},
             {"label": "처리시간 중앙값: 브루클린", "value": f"{med['BROOKLYN']}시간"},
             {"label": "'개별 대응 불가'로 닫힘", "value": f"{si_auto:.0f}% 대 {bk_auto:.0f}%",
              "help": "스태튼아일랜드 대 브루클린"},
             {"label": "결과문이 '치웠다'인 민원", "value": f"{plowed:.1f}%", "help": "시 전체, 폭설 1주일"},
         ],
         charts=[
             {"title": "자치구별 처리시간 중앙값", "kind": "bar", "x": "자치구", "y": "처리시간 중앙값(시간)",
              "rows": records(medf), "sort": "-y", "caption": "이 숫자만 보면 스태튼아일랜드가 가장 빨리 치운 것처럼 보인다."},
             {"title": "결과문으로 본 종결 방식", "kind": "stackh", "x": "비율(%)", "y": "자치구", "color": "결과",
              "colors": dict(zip(order, ["#e07b39", "#b9c4d4", "#2457a7", "#6b7a8f"])),
              "rows": records(mix[["자치구", "결과", "비율(%)"]]),
              "caption": "주황은 '폭설 작업 중이라 개별 요청에 답할 수 없다'는 일괄 종결 문구다. 현장에 가지 않고 닫은 것이다."},
         ],
         tables=[{"title": "자치구 × 종결 방식(%)",
                  "rows": records(mix.pivot(index="자치구", columns="결과", values="비율(%)").reindex(columns=order).reset_index())}])


def q004(df):
    heat = df[df.problem == "HEAT/HOT WATER"].copy()
    heat["dup"] = heat.resolution.fillna("").str.lower().str.contains("duplicate")
    cold = heat[(heat.date >= "2026-01-24") & (heat.date <= "2026-02-01")]
    s = heat[heat.created < HEAT_SEASON_END]
    wk = s.groupby(s.created.dt.to_period("W-SUN").dt.start_time).agg(n=("dup", "size"), dup=("dup", "mean"))
    wk = wk[wk.n >= 500].reset_index().rename(columns={"created": "주 시작일"})
    wk["중복 비율(%)"] = (wk.dup * 100).round(1)
    wk["난방 민원"] = wk.n
    heat["결과"] = classify(heat.resolution, HPD_RULES)
    res = heat.결과.value_counts().rename_axis("결과").reset_index(name="민원")
    res["비율(%)"] = (res.민원 / len(heat) * 100).round(1)
    top_text = heat.resolution.fillna("").value_counts()
    save(4,
         metrics=[
             {"label": "1년 난방 민원 중 '중복'", "value": f"{heat.dup.mean() * 100:.1f}%", "help": f"{len(heat):,}건 중"},
             {"label": "한파 주간(1/24–2/1)", "value": f"{cold.dup.mean() * 100:.1f}%", "help": f"{len(cold):,}건 중"},
             {"label": "결과문 1위 건수", "value": f"{top_text.iat[0]:,}건", "help": "건물 전체 상태로 이미 접수된 민원의 중복"},
         ],
         charts=[
             {"title": "주별 난방 민원과 중복 비율", "kind": "line", "x": "주 시작일", "y": "중복 비율(%)", "alt_y": "난방 민원",
              "rows": records(wk[["주 시작일", "중복 비율(%)", "난방 민원"]]), "point": True,
              "caption": "민원이 많은 주일수록 중복 비율도 오른다. 한 건물에서 여러 세대가 동시에 신고하기 때문이다(난방 시즌, 주 500건 이상)."},
             {"title": "난방 민원은 어떻게 닫혔나(1년)", "kind": "barh", "x": "비율(%)", "y": "결과", "rows": records(res),
              "caption": "결과문을 규칙으로 묶었다. '중복'은 그중 한 갈래다."},
         ],
         tables=[{"title": "결과문 원문 상위 5개", "rows": records(
             top_text.head(5).rename_axis("결과문").reset_index(name="민원").assign(결과문=lambda x: x.결과문.str[:160]))}])


def q005(df):
    hs = heat_season(df)
    hs = hs[hs.bbl.notna() & (hs.bbl.astype(str).str.strip() != "")]
    b = hs.groupby("bbl").size()
    curve = []
    for k in [1, 2, 3, 5, 10, 20, 50]:
        curve.append({"기준 k(회 초과)": k, "건물 비율(%)": round((b > k).mean() * 100, 1),
                      "그 건물들의 민원 몫(%)": round(b[b > k].sum() / b.sum() * 100, 1)})
    cdf = pd.DataFrame(curve).melt(id_vars="기준 k(회 초과)", var_name="구분", value_name="비율(%)")
    months = hs.groupby("bbl").created.apply(lambda s: s.dt.to_period("M").nunique())
    mdist = months.value_counts().sort_index().rename_axis("민원이 있었던 달 수(7개월 중)").reset_index(name="건물 수")
    mdist["민원이 있었던 달 수(7개월 중)"] = mdist["민원이 있었던 달 수(7개월 중)"].astype(str) + "개월"
    over5 = b > 5
    save(5,
         metrics=[
             {"label": "5회 초과 건물(한 시즌)", "value": f"{over5.mean() * 100:.1f}%", "help": f"{over5.sum():,}동 / {len(b):,}동"},
             {"label": "그 건물들의 민원 몫", "value": f"{b[over5].sum() / b.sum() * 100:.1f}%"},
             {"label": "감사관 보고서", "value": "1.5%", "help": "2017–2021 매 시즌 연속 5회 초과"},
             {"label": "7개월 내내 신고된 건물", "value": f"{(months == 7).mean() * 100:.1f}%", "help": f"{(months == 7).sum():,}동"},
         ],
         charts=[
             {"title": "기준을 바꾸면 '문제 건물' 비율이 바뀐다", "kind": "line", "x": "기준 k(회 초과)", "y": "비율(%)",
              "color": "구분", "rows": records(cdf), "point": True,
              "caption": "같은 자료라도 'k회 초과'의 k를 어디에 두느냐에 따라 숫자가 크게 달라진다."},
             {"title": "건물마다 몇 달 동안 신고됐나", "kind": "bar", "x": "민원이 있었던 달 수(7개월 중)", "y": "건물 수",
              "rows": records(mdist), "caption": "'연속'을 조건에 넣으면 숫자는 급격히 줄어든다. 감사관의 1.5%는 5년 연속 조건이다."},
         ],
         tables=[{"title": "기준별 건물 비율과 민원 몫", "rows": curve}])


def q006(df):
    heat = df[df.problem == "HEAT/HOT WATER"]
    month = heat.groupby(heat.created.dt.to_period("M").dt.start_time).size().rename_axis("월").reset_index(name="난방 민원")
    hs = heat_season(df).copy()
    hs["결과"] = classify(hs.resolution, HPD_RULES)
    viol = (hs.결과 == "위반 발부").sum()
    save(6,
         metrics=[
             {"label": "감사관: 난방 신고(2017–2021)", "value": "약 100만 건"},
             {"label": "감사관: 위반 처분", "value": "21,610건"},
             {"label": "신고 ÷ 처분", "value": "약 46배"},
             {"label": "이번 시즌 결과문 '위반 발부'", "value": f"{viol / len(hs) * 100:.1f}%",
              "help": f"{len(hs):,}건 중 {viol:,}건. 위반 기록 자체가 아니라 결과문 문구다."},
         ],
         charts=[
             {"title": "월별 난방 민원(2025-11 ~ 2026-10)", "kind": "bar", "x": "월", "y": "난방 민원", "rows": records(month),
              "caption": "난방 시즌(10/1–5/31)에 몰린다. 1월이 정점이다."},
         ],
         numbers={"season": len(hs), "viol_text": int(viol)})


def q008(dt):
    enc = dt[dt.problem == "Encampment"]
    g = enc.groupby("inc_q", observed=True).agg(n=("hours", "size"), med=("hours", "median"))
    pop = dt.drop_duplicates("GEOID").groupby("inc_q", observed=True).total_pop.sum()
    g = g.reindex(INC_Q)
    rows = pd.DataFrame({"소득 5분위": INC_Q, "민원 건수": g.n.values, "처리시간 중앙값(시간)": g.med.round(2).values,
                         "10만 명당": (g.n / pop.reindex(INC_Q) * 1e5).round(0).values})
    q1, q5 = rows.iloc[0], rows.iloc[-1]
    save(8,
         metrics=[
             {"label": "처리시간 중앙값: 최하위", "value": f"{q1['처리시간 중앙값(시간)']:.2f}시간"},
             {"label": "처리시간 중앙값: 최상위", "value": f"{q5['처리시간 중앙값(시간)']:.2f}시간",
              "help": f"{(1 - q5['처리시간 중앙값(시간)'] / q1['처리시간 중앙값(시간)']) * 100:.0f}% 빠름"},
             {"label": "신고 건수: 최상위 ÷ 최하위", "value": f"{q5['민원 건수'] / q1['민원 건수']:.1f}배",
              "help": f"{int(q5['민원 건수']):,}건 대 {int(q1['민원 건수']):,}건"},
         ],
         charts=[
             {"title": "소득 5분위별 야영지 민원", "kind": "bar", "x": "소득 5분위", "y": "민원 건수",
              "alt_y": "처리시간 중앙값(시간)", "rows": records(rows),
              "caption": "건수 차이(5.7배)가 처리시간 차이(약 19%)보다 훨씬 크다."},
         ],
         tables=[{"title": "소득 5분위별 야영지 민원", "rows": records(rows)}])


def q009(dt):
    types = {"Encampment": "노숙인 야영지", "HEAT/HOT WATER": "난방·온수", "Illegal Parking": "불법주차",
             "Noise - Residential": "주거 소음"}
    sub = dt[dt.problem.isin(list(types))]
    g = sub.groupby(["problem", "inc_q"], observed=True).hours.median().rename("med").reset_index()
    g["유형"] = g.problem.map(types)
    g["처리시간 중앙값(시간)"] = g.med.round(2)
    base = g[g.inc_q == INC_Q[0]].set_index("problem").med
    g["최하위 분위=100"] = (g.med / g.problem.map(base) * 100).round(0)
    g = g.rename(columns={"inc_q": "소득 5분위"})[["유형", "소득 5분위", "처리시간 중앙값(시간)", "최하위 분위=100"]]
    g["소득 5분위"] = g["소득 5분위"].astype(str)
    piv = g.pivot(index="유형", columns="소득 5분위", values="처리시간 중앙값(시간)").reindex(columns=INC_Q)
    h = piv.loc["난방·온수"]
    save(9,
         metrics=[
             {"label": "난방: 최하위 분위", "value": f"{h[INC_Q[0]]:.1f}시간"},
             {"label": "난방: 최상위 분위", "value": f"{h[INC_Q[-1]]:.1f}시간", "help": "부유한 동네가 더 느리다"},
             {"label": "야영지: 최상위 ÷ 최하위", "value": f"{piv.loc['노숙인 야영지', INC_Q[-1]] / piv.loc['노숙인 야영지', INC_Q[0]]:.2f}"},
         ],
         charts=[
             {"title": "유형별 처리시간과 소득 분위", "kind": "line", "x": "소득 5분위", "y": "최하위 분위=100",
              "alt_y": "처리시간 중앙값(시간)", "color": "유형", "rows": records(g), "point": True, "nominal_x": True,
              "caption": "최하위 분위를 100으로 맞췄다. 100보다 아래면 그 분위가 더 빠르다. 방향이 유형마다 다르다."},
         ],
         tables=[{"title": "처리시간 중앙값(시간)", "rows": records(piv.reset_index())}])


def q010(df):
    soc = {"Encampment": "노숙인 야영지", "Homeless Person Assistance": "노숙인 지원", "Graffiti": "낙서",
           "Panhandling": "구걸", "Drug Activity": "마약", "Drinking": "공공 음주",
           "Urinating in Public": "노상 방뇨", "Disorderly Youth": "청소년 소란"}
    x = df.problem.isin(list(soc))
    by = df[x].problem.astype(str).map(soc).value_counts().rename_axis("유형").reset_index(name="민원")
    m = df.groupby(df.created.dt.to_period("M").dt.start_time).agg(all=("key", "size"))
    m["soc"] = df[x].groupby(df[x].created.dt.to_period("M").dt.start_time).size()
    m["사회적 무질서 비중(%)"] = (m.soc / m["all"] * 100).round(2)
    m = m.rename_axis("월").reset_index()
    save(10,
         metrics=[
             {"label": "사회적 무질서 민원", "value": f"{x.sum():,}건"},
             {"label": "전체 중 비중", "value": f"{x.mean() * 100:.2f}%", "help": "DCJ(2019): 2% 미만"},
             {"label": "1위 유형", "value": by.유형.iat[0], "help": f"{by.민원.iat[0]:,}건"},
         ],
         charts=[
             {"title": "유형별 건수", "kind": "barh", "x": "민원", "y": "유형", "rows": records(by)},
             {"title": "월별 비중", "kind": "line", "x": "월", "y": "사회적 무질서 비중(%)", "rows": records(m[["월", "사회적 무질서 비중(%)"]]),
              "point": True, "caption": "2월이 낮은 것은 눈 민원이 분모(전체 민원)를 키운 영향이 크다. 비중은 분자와 분모가 함께 움직인다."},
         ],
         tables=[{"title": "포함한 유형", "rows": records(by)}])


def q012(df):
    leak = df[df.problem == "WATER LEAK"].copy()
    leak["결과"] = classify(leak.resolution, HPD_RULES)
    leak["월"] = leak.created.dt.to_period("M").dt.start_time
    m = leak.groupby("월").size().reset_index(name="누수 민원")
    res = leak.결과.value_counts().rename_axis("결과").reset_index(name="민원")
    res["비율(%)"] = (res.민원 / len(leak) * 100).round(1)
    no_access = (leak.결과 == "점검 못 함(문을 못 엶)").mean() * 100
    viol = (leak.결과 == "위반 발부").mean() * 100
    save(12,
         metrics=[
             {"label": "누수 민원(HPD, 12개월)", "value": f"{len(leak):,}건"},
             {"label": "점검 못 하고 닫힘", "value": f"{no_access:.0f}%", "help": "점검원이 집에 들어가지 못함"},
             {"label": "위반 발부", "value": f"{viol:.0f}%"},
         ],
         charts=[
             {"title": "월별 누수 민원", "kind": "bar", "x": "월", "y": "누수 민원", "rows": records(m),
              "caption": "12개월만으로는 추세를 말할 수 없다. 늘고 줄어든 것이 계절 때문인지, 신고 의욕 때문인지 가를 수 없다."},
             {"title": "누수 민원은 어떻게 닫혔나", "kind": "barh", "x": "비율(%)", "y": "결과", "rows": records(res),
              "caption": "'닫혔다'의 상당수는 고쳤다는 뜻이 아니다."},
         ],
         tables=[{"title": "결과 분류", "rows": records(res)}])


def q001(df, bp):
    snow = df[df.problem == "Snow or Ice"]
    day = snow[snow.date == "2026-02-23"]
    cnt = day.borough.value_counts().reindex(BOROS).fillna(0).astype(int)
    rate = (cnt / bp.reindex(BOROS) * 1e5).round(1)
    by_boro = pd.DataFrame({"자치구": [BORO_KO[b] for b in BOROS], "민원 건수": cnt.values,
                            "10만 명당": rate.values, "인구": bp.reindex(BOROS).astype(int).values})

    win = snow[(snow.date >= "2026-02-16") & (snow.date <= "2026-03-08")]
    daily = (win.groupby(["date", "borough"], observed=True).size().rename("n").reset_index())
    daily = daily[daily.borough.isin(BOROS)]
    daily["10만 명당"] = (daily.n / daily.borough.map(bp) * 1e5).round(1)
    daily["자치구"] = daily.borough.map(BORO_KO)
    daily = daily.rename(columns={"date": "날짜", "n": "민원 건수"})[["날짜", "자치구", "민원 건수", "10만 명당"]]

    week = snow[(snow.created >= "2026-02-22 18:00") & (snow.created < "2026-03-03")]
    wk = week.borough.value_counts().reindex(BOROS).fillna(0).astype(int)
    wk_rate = (wk / bp.reindex(BOROS) * 1e5).round(0)
    total_day = int((df.date == "2026-02-23").sum())
    si, mn = rate["STATEN ISLAND"], rate["MANHATTAN"]

    save(1,
         metrics=[
             {"label": "스태튼아일랜드 눈 민원", "value": f"{cnt['STATEN ISLAND']:,}건", "help": "2026-02-23 하루, Snow or Ice"},
             {"label": "맨해튼 눈 민원", "value": f"{cnt['MANHATTAN']:,}건", "help": "같은 날"},
             {"label": "10만 명당 격차", "value": f"{si / mn:.0f}배", "help": f"{si:,.0f}건 대 {mn:,.0f}건"},
             {"label": "그날 시 전체 접수", "value": f"{total_day:,}건", "help": "모든 유형, 기사 15,387건"},
         ],
         charts=[
             {"title": "2026-02-23 자치구별 눈·얼음 민원", "kind": "bar", "x": "자치구", "y": "민원 건수",
              "alt_y": "10만 명당", "rows": records(by_boro), "sort": "-y",
              "caption": "건수와 10만 명당을 바꿔 보면 순위가 그대로인지 확인할 수 있다."},
             {"title": "폭설 전후 3주, 하루 눈·얼음 민원", "kind": "line", "x": "날짜", "y": "10만 명당",
              "alt_y": "민원 건수", "color": "자치구", "rows": records(daily),
              "caption": "2/22 저녁부터 눈이 내렸다. 스태튼아일랜드는 다음 이틀 동안 다른 자치구와 크게 벌어진다."},
         ],
         tables=[{"title": "자치구 인구와 눈 민원(2/23)", "rows": records(by_boro)}],
         numbers={"week_total": int(wk.sum()), "week_si": int(wk["STATEN ISLAND"]),
                  "week_si_rate": float(wk_rate["STATEN ISLAND"]), "week_mn_rate": float(wk_rate["MANHATTAN"])})


def q007(df):
    heat = df[(df.problem == "HEAT/HOT WATER") & (df.created < "2026-06-01")]
    has_bbl = heat.bbl.notna() & (heat.bbl.astype(str).str.strip() != "")
    b = heat[has_bbl].groupby("bbl").size().sort_values(ascending=False)
    n_bld = len(b)
    cum = b.cumsum() / b.sum()
    # 건물 상위 x%가 민원 몇 %를 차지하나 (집중 곡선)
    pts = []
    for pct in [1, 2, 5, 10, 20, 30, 50, 75, 100]:
        k = max(1, round(n_bld * pct / 100))
        pts.append({"건물 상위 %": pct, "민원 누적 %": round(float(cum.iloc[k - 1]) * 100, 1)})
    bins = pd.cut(b, [0, 1, 2, 5, 10, 25, 50, 100, 10_000],
                  labels=["1건", "2건", "3–5건", "6–10건", "11–25건", "26–50건", "51–100건", "101건 이상"])
    dist = bins.value_counts().reindex(bins.cat.categories).rename_axis("건물당 민원").reset_index(name="건물 수")
    top = b.head(10).rename_axis("BBL").reset_index(name="난방 민원")
    top["BBL"] = top["BBL"].astype(str)
    top_addr = heat[has_bbl].groupby("bbl").addr_n.agg(lambda s: s.mode().iat[0] if len(s.mode()) else "")
    top["주소"] = top["BBL"].map(top_addr)

    save(7,
         metrics=[
             {"label": "난방 민원(2025-11 ~ 2026-05)", "value": f"{len(heat):,}건", "help": "HEAT/HOT WATER"},
             {"label": "BBL이 있는 난방 민원", "value": f"{has_bbl.mean() * 100:.1f}%", "help": "HPD 자료와 연결할 수 있는 몫(311 전체는 약 88%)"},
             {"label": "신고된 건물", "value": f"{n_bld:,}동", "help": "BBL 기준"},
             {"label": "상위 10% 건물의 몫", "value": f"{pts[3]['민원 누적 %']:.0f}%", "help": "민원 누적 비율"},
         ],
         charts=[
             {"title": "난방 민원 집중 곡선", "kind": "line", "x": "건물 상위 %", "y": "민원 누적 %", "rows": pts,
              "point": True, "caption": "건물을 민원이 많은 순으로 줄 세웠을 때, 위에서부터 몇 %가 민원 몇 %를 내는가."},
             {"title": "건물당 난방 민원 수 분포", "kind": "bar", "x": "건물당 민원", "y": "건물 수",
              "rows": records(dist), "caption": "대부분의 건물은 한두 번, 소수 건물이 수십·수백 번 신고된다."},
         ],
         tables=[{"title": "난방 민원이 가장 많은 건물 10곳", "rows": records(top)}],
         numbers={"bbl_share": round(float(has_bbl.mean()), 3), "n_bld": n_bld})


def q011(df):
    noise = df[df.problem.astype(str).str.startswith("Noise")]
    hot = "655 EAST 230 STREET"
    is_hot = noise.addr_n == hot
    month = noise.created.dt.to_period("M").dt.to_timestamp()
    m = pd.DataFrame({"월": month, "hot": is_hot}).groupby(["월", "hot"]).size().unstack(fill_value=0)
    m.columns = ["그 밖의 주소", "655 E 230th St"]
    mrows = m.reset_index().melt(id_vars="월", var_name="구분", value_name="소음 민원")
    top = noise[noise.addr_n != ""].addr_n.value_counts().head(10).rename_axis("주소").reset_index(name="소음 민원")
    top["전체 소음 중 %"] = (top["소음 민원"] / len(noise) * 100).round(2)
    base_2024 = 738_000
    total, hot_n = len(noise), int(is_hot.sum())

    save(11,
         metrics=[
             {"label": "소음 민원(12개월)", "value": f"{total:,}건", "help": "Noise로 시작하는 유형 전체"},
             {"label": "2024년 보도 대비", "value": f"+{(total / base_2024 - 1) * 100:.1f}%", "help": "73.8만 건 기준"},
             {"label": "655 E 230th St 한 곳", "value": f"{hot_n:,}건", "help": f"전체 소음의 {hot_n / total * 100:.1f}%"},
             {"label": "이 주소를 빼면", "value": f"{(total - hot_n) / base_2024 * 100 - 100:+.1f}%", "help": f"{total - hot_n:,}건"},
         ],
         charts=[
             {"title": "월별 소음 민원, 한 주소와 나머지", "kind": "stack", "x": "월", "y": "소음 민원", "color": "구분",
              "colors": {"그 밖의 주소": "#9fb3d1", "655 E 230th St": "#e07b39"},
              "rows": records(mrows),
              "caption": ("주황 부분이 한 주소에서 온 민원이다. 11–12월 두 달에 몰려 있고, "
                          "이것만 빼도 증가분이 거의 사라진다.")},
             {"title": "소음 민원 상위 주소 10곳", "kind": "barh", "x": "소음 민원", "y": "주소",
              "rows": records(top), "caption": "1위 주소는 2위의 몇 배인지 보자. 이상치는 표에서 먼저 드러난다."},
         ],
         tables=[{"title": "소음 민원 상위 주소", "rows": records(top)}],
         numbers={"total": total, "hot": hot_n, "base_2024": base_2024})


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} or set(range(1, 13))
    df = load_311()
    bp = borough_pop()
    dt = with_tract(df) if want & {8, 9} else None
    jobs = {1: lambda: q001(df, bp), 2: lambda: q002(df, bp), 3: lambda: q003(df), 4: lambda: q004(df),
            5: lambda: q005(df), 6: lambda: q006(df), 7: lambda: q007(df), 8: lambda: q008(dt),
            9: lambda: q009(dt), 10: lambda: q010(df), 11: lambda: q011(df), 12: lambda: q012(df)}
    for k in sorted(want):
        jobs[k]()
