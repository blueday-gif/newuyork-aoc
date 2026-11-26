"""5부. 뉴욕의 하루와 1년 — 통계 계산.
문항 49–60. 실행: python questions/calc/part05.py  (일부만: python questions/calc/part05.py 52 60)
57·58번은 NOAA 일별 기온을 아직 붙이지 않았다. 311 쪽 일별 흐름만 계산한다.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_311, records, save, tracts, with_tract  # noqa: E402

DOW_KO = ["월", "화", "수", "목", "금", "토", "일"]
HOT = "655 EAST 230 STREET"
PROB_KO = {"Noise - Residential": "주거 소음", "Illegal Parking": "불법주차", "HEAT/HOT WATER": "난방·온수",
           "Noise - Street/Sidewalk": "길거리 소음", "Blocked Driveway": "진입로 막힘", "Noise - Vehicle": "차량 소음",
           "Noise - Commercial": "상업 시설 소음", "Snow or Ice": "눈·얼음", "Illegal Fireworks": "불법 불꽃놀이",
           "Abandoned Vehicle": "버려진 차", "Encampment": "노숙인 야영지", "UNSANITARY CONDITION": "비위생 상태",
           "Non-Emergency Police Matter": "비긴급 경찰", "Water System": "상수도", "Noise": "공사·기타 소음(DEP)",
           "Traffic Signal Condition": "신호등 고장", "Street Light Condition": "가로등 고장", "Dirty Condition": "더러운 거리"}


def ko(p: str) -> str:
    return PROB_KO.get(p, p)


def noise(df):
    return df[df.problem.astype(str).str.startswith("Noise")]


def q049(df):
    nz = noise(df)
    h = nz.created.dt.hour.value_counts().sort_index()
    rows = pd.DataFrame({"시각": [f"{i:02d}시" for i in h.index], "소음 민원": h.values})
    night = h.loc[[22, 23, 0, 1, 2, 3, 4, 5]].sum() / h.sum() * 100
    save(49,
         metrics=[
             {"label": "1위 시각", "value": f"밤 10시", "help": f"{h[22]:,}건"},
             {"label": "2위·3위", "value": "11시·자정", "help": f"{h[23]:,}건, {h[0]:,}건"},
             {"label": "밤 10시 ~ 새벽 6시 몫", "value": f"{night:.0f}%", "help": "하루 24시간 중 8시간"},
             {"label": "가장 조용한 시각", "value": f"{h.idxmin()}시", "help": f"{h.min():,}건"},
         ],
         charts=[
             {"title": "시각별 소음 민원(1년 합계)", "kind": "bar", "x": "시각", "y": "소음 민원", "rows": records(rows),
              "caption": "접수 시각 기준이다. 소음이 난 시각과 신고한 시각은 조금 다를 수 있다."},
         ])


def q050(df):
    nz = noise(df)
    dw = nz.created.dt.dayofweek.value_counts().sort_index()
    rows = pd.DataFrame({"요일": DOW_KO, "소음 민원": dw.values})
    ndays = nz.groupby(nz.created.dt.dayofweek).date.nunique()
    hh = nz.assign(h=nz.created.dt.hour, 구분=np.where(nz.created.dt.dayofweek >= 5, "주말(토·일)", "평일(월–금)"))
    prof = hh.groupby(["구분", "h"]).size().rename("n").reset_index()
    days = {"주말(토·일)": ndays.loc[[5, 6]].sum(), "평일(월–금)": ndays.loc[[0, 1, 2, 3, 4]].sum()}
    prof["하루 평균"] = (prof.n / prof.구분.map(days)).round(0)
    prof["시각"] = prof.h.map(lambda i: f"{i:02d}시")
    save(50,
         metrics=[
             {"label": "토요일", "value": f"{dw[5]:,}건"},
             {"label": "일요일", "value": f"{dw[6]:,}건"},
             {"label": "월요일", "value": f"{dw[0]:,}건"},
             {"label": "주말 ÷ 월요일", "value": f"{dw[5:7].mean() / dw[0]:.2f}배"},
         ],
         charts=[
             {"title": "요일별 소음 민원(1년 합계)", "kind": "bar", "x": "요일", "y": "소음 민원", "rows": records(rows),
              "caption": "금요일부터 오른다. 요일마다 1년에 52번 안팎이라 합계를 그대로 비교할 수 있다."},
             {"title": "시각별 하루 평균: 평일 vs 주말", "kind": "line", "x": "시각", "y": "하루 평균", "color": "구분",
              "colors": {"평일(월–금)": "#2457a7", "주말(토·일)": "#e07b39"}, "rows": records(prof[["시각", "구분", "하루 평균"]]),
              "caption": "주말의 차이는 밤 10시 ~ 새벽 3시에 몰려 있다. 주말 '새벽'은 토·일 새벽, 곧 금·토 밤이다."},
         ])


def q051(df):
    h3 = df[df.created.dt.hour == 3]
    top = h3.problem.astype(str).value_counts().head(10)
    rows = pd.DataFrame({"유형": [ko(p) for p in top.index], "새벽 3시 민원": top.values})
    day = df[df.created.dt.hour == 15].problem.astype(str).value_counts()
    rows["오후 3시 민원"] = [int(day.get(p, 0)) for p in top.index]
    save(51,
         metrics=[{"label": f"{i + 1}위 {ko(p)}", "value": f"{n:,}건"} for i, (p, n) in enumerate(top.head(3).items())]
         + [{"label": "새벽 3시 접수 전체", "value": f"{len(h3):,}건", "help": f"하루 평균 {len(h3) / 365:,.0f}건"}],
         charts=[
             {"title": "새벽 3시에 들어오는 민원 상위 10", "kind": "barh", "x": "새벽 3시 민원", "y": "유형", "rows": records(rows),
              "caption": "표에서 같은 유형의 오후 3시 건수와 비교해 보자. 소음은 밤에, 주차는 낮에도 많다."},
         ],
         tables=[{"title": "새벽 3시 vs 오후 3시", "rows": records(rows)}])


def q052(df):
    nz = noise(df)
    d = nz.groupby("date").size().rename_axis("날짜").reset_index(name="소음 민원")
    avg = d["소음 민원"].mean()
    top = d.sort_values("소음 민원", ascending=False).head(10).copy()
    top["요일"] = top.날짜.dt.dayofweek.map(dict(enumerate(DOW_KO)))
    top["평균 대비"] = (top["소음 민원"] / avg).round(1)
    t1 = top.iloc[0]
    save(52,
         metrics=[
             {"label": "가장 시끄러운 날", "value": t1.날짜.strftime("%Y-%m-%d"), "help": f"{t1.요일}요일"},
             {"label": "그날 소음 민원", "value": f"{int(t1['소음 민원']):,}건"},
             {"label": "하루 평균", "value": f"{avg:,.0f}건", "help": f"그날은 {t1['소음 민원'] / avg:.1f}배"},
         ],
         charts=[
             {"title": "하루 소음 민원(12개월)", "kind": "line", "x": "날짜", "y": "소음 민원", "rows": records(d),
              "caption": "겨울에 낮고 여름에 높다. 뾰족한 날은 대부분 여름 주말이다. 11–12월의 높은 구간은 11번의 한 주소 영향이다."},
         ],
         tables=[{"title": "소음 민원 상위 10일", "rows": records(top[["날짜", "요일", "소음 민원", "평균 대비"]])}])


def q053(df):
    w = df[(df.created >= "2026-06-15") & (df.created < "2026-07-16")]
    fw = w[w.problem == "Illegal Fireworks"].groupby("date").size()
    nz = noise(w).groupby("date").size()
    idx = pd.date_range("2026-06-15", "2026-07-15")
    rows = pd.concat([pd.DataFrame({"날짜": idx, "구분": "불법 불꽃놀이", "민원": fw.reindex(idx, fill_value=0).values}),
                      pd.DataFrame({"날짜": idx, "구분": "소음", "민원": nz.reindex(idx, fill_value=0).values})])
    fall = df[df.problem == "Illegal Fireworks"]
    peak3 = fall[(fall.date >= "2026-07-03") & (fall.date <= "2026-07-05")]
    save(53,
         metrics=[
             {"label": "불법 불꽃놀이(12개월)", "value": f"{len(fall):,}건"},
             {"label": "7월 3–5일", "value": f"{len(peak3):,}건", "help": f"1년치의 {len(peak3) / len(fall) * 100:.0f}%"},
             {"label": "7월 4일 하루", "value": f"{int(fw.get(pd.Timestamp('2026-07-04'), 0)):,}건"},
             {"label": "7월 4일 소음", "value": f"{int(nz.get(pd.Timestamp('2026-07-04'), 0)):,}건"},
         ],
         charts=[
             {"title": "6/15–7/15 하루 민원: 불꽃놀이와 소음", "kind": "line", "x": "날짜", "y": "민원", "color": "구분",
              "colors": {"불법 불꽃놀이": "#e07b39", "소음": "#2457a7"}, "rows": records(rows),
              "caption": "불꽃놀이 민원은 7월 4일 전후 사흘에 솟는다. 독립기념일 불꽃놀이는 소음이 아니라 '불법 불꽃놀이' 유형으로 따로 들어간다."},
         ])


SPECIAL = [("2025-12-31", "12/31 새해 전야"), ("2026-01-01", "1/1 새해 첫날"), ("2026-02-08", "2/8 슈퍼볼 일요일"),
           ("2026-03-17", "3/17 성 패트릭의 날"), ("2026-06-21", "6/21 하지 무렵 일요일"), ("2026-07-04", "7/4 독립기념일"),
           ("2026-07-05", "7/5 독립기념일 다음 날")]


def q054(df):
    nz = noise(df)
    daily = nz.groupby("date").size()
    avg = daily.mean()
    rows = pd.DataFrame([{"날": lab, "소음 민원": int(daily.get(pd.Timestamp(d), 0))} for d, lab in SPECIAL])
    rows["평균 대비"] = (rows["소음 민원"] / avg).round(2)
    jan = daily[(daily.index >= "2026-01-02") & (daily.index < "2026-02-01")]
    save(54,
         metrics=[
             {"label": "1월 1일 소음", "value": f"{int(daily.get(pd.Timestamp('2026-01-01'))):,}건"},
             {"label": "1월 평일 하루 평균", "value": f"{jan[jan.index.dayofweek < 5].mean():,.0f}건", "help": "1/2–1/31"},
             {"label": "1년 하루 평균", "value": f"{avg:,.0f}건"},
             {"label": "1월 1일 ÷ 1월 평일", "value": f"{daily.get(pd.Timestamp('2026-01-01')) / jan[jan.index.dayofweek < 5].mean():.1f}배",
              "help": "같은 계절과 비교"},
         ],
         charts=[
             {"title": "특별한 날의 소음 민원", "kind": "barh", "x": "소음 민원", "y": "날", "rows": records(rows),
              "caption": "1년 평균과 비교하면 새해 첫날은 평범해 보인다. 하지만 같은 계절(1월 평일 약 1,300건)과 비교하면 1.6배다. 무엇과 비교하느냐에 따라 '평범'과 '많음'이 갈린다."},
         ],
         tables=[{"title": "특별한 날", "rows": records(rows)}])


def q055(df):
    d = df.groupby("date").size().rename_axis("날짜").reset_index(name="전체 민원")
    top = d.sort_values("전체 민원", ascending=False).head(10).copy()
    first = []
    for day in top.날짜:
        s = df[df.date == day].problem.astype(str).value_counts()
        first.append(f"{ko(s.index[0])} {s.iat[0] / s.sum() * 100:.0f}%")
    top["1위 유형과 몫"] = first
    low = d.sort_values("전체 민원").head(3)
    t1 = top.iloc[0]
    save(55,
         metrics=[
             {"label": "가장 많은 날", "value": t1.날짜.strftime("%Y-%m-%d"), "help": f"{int(t1['전체 민원']):,}건, {top['1위 유형과 몫'].iat[0]}"},
             {"label": "하루 평균", "value": f"{d['전체 민원'].mean():,.0f}건"},
             {"label": "가장 적은 날", "value": low.날짜.iat[0].strftime("%Y-%m-%d"), "help": f"{int(low['전체 민원'].iat[0]):,}건. 자료가 21시부터만 있다(→ 89번)"},
         ],
         charts=[
             {"title": "하루 전체 민원(12개월)", "kind": "line", "x": "날짜", "y": "전체 민원", "rows": records(d),
              "caption": "2월 23–24일 폭설이 가장 높은 봉우리다. 맨 왼쪽 첫날은 자료가 저녁 9시부터라 낮게 찍힌다."},
         ],
         tables=[{"title": "민원이 가장 많은 10일", "rows": records(top)}])


def q056(df):
    h = df[df.problem == "HEAT/HOT WATER"]
    m = h.groupby(h.created.dt.to_period("M").dt.start_time).size().rename_axis("월").reset_index(name="난방 민원")
    d = h.groupby("date").size().rename_axis("날짜").reset_index(name="난방 민원")
    mx, mn = m.loc[m["난방 민원"].idxmax()], m.loc[m["난방 민원"].idxmin()]
    save(56,
         metrics=[
             {"label": "가장 많은 달", "value": mx.월.strftime("%Y-%m"), "help": f"{int(mx['난방 민원']):,}건"},
             {"label": "가장 적은 달", "value": mn.월.strftime("%Y-%m"), "help": f"{int(mn['난방 민원']):,}건"},
             {"label": "계절 폭", "value": f"{mx['난방 민원'] / mn['난방 민원']:.0f}배"},
         ],
         charts=[
             {"title": "월별 난방 민원", "kind": "bar", "x": "월", "y": "난방 민원", "rows": records(m)},
             {"title": "하루 난방 민원", "kind": "line", "x": "날짜", "y": "난방 민원", "rows": records(d),
              "caption": "겨울 안에서도 날마다 크게 출렁인다. 뾰족한 날은 한파가 온 날로 보인다(→ 57번에서 기온으로 확인)."},
         ])


def q057(df):
    h = df[(df.problem == "HEAT/HOT WATER") & (df.created < "2026-04-01")]
    d = h.groupby("date").size().rename_axis("날짜").reset_index(name="난방 민원")
    d["7일 이동평균"] = d["난방 민원"].rolling(7, center=True).mean().round(0)
    top = d.sort_values("난방 민원", ascending=False).head(8).copy()
    top["요일"] = top.날짜.dt.dayofweek.map(dict(enumerate(DOW_KO)))
    long = d.melt(id_vars="날짜", value_vars=["난방 민원", "7일 이동평균"], var_name="구분", value_name="건수")
    save(57,
         metrics=[
             {"label": "기온 자료", "value": "아직 없음", "help": "NOAA 센트럴파크(USW00094728) 일별 최저기온"},
             {"label": "겨울 하루 최대", "value": f"{int(top['난방 민원'].iat[0]):,}건", "help": top.날짜.iat[0].strftime("%Y-%m-%d")},
             {"label": "겨울 하루 중앙값", "value": f"{d['난방 민원'].median():,.0f}건", "help": "2025-11 ~ 2026-03"},
         ],
         charts=[
             {"title": "겨울 하루 난방 민원과 7일 이동평균", "kind": "line", "x": "날짜", "y": "건수", "color": "구분",
              "colors": {"난방 민원": "#9fb3d1", "7일 이동평균": "#2457a7"}, "rows": records(long),
              "caption": "이 선 옆에 같은 날의 최저기온을 놓으면 '0°C 아래에서 몇 배'를 바로 잴 수 있다."},
         ],
         tables=[{"title": "난방 민원이 가장 많은 날", "rows": records(top[["날짜", "요일", "난방 민원"]])}])


def q058(df):
    s = df[(df.created >= "2026-06-01") & (df.created < "2026-09-01")]
    det = s.detail.astype(str)
    out = s[(s.problem == "ELECTRIC") & (det == "POWER OUTAGE")]
    hyd = s[det.str.contains("Hydrant Running", case=False) & s.problem.astype(str).isin(["Water System", "Water Maintenance"])]
    idx = pd.date_range("2026-06-01", "2026-08-31")
    rows = pd.concat([pd.DataFrame({"날짜": idx, "구분": "정전(주거, HPD)", "민원": out.groupby("date").size().reindex(idx, fill_value=0).values}),
                      pd.DataFrame({"날짜": idx, "구분": "소화전 열림(DEP)", "민원": hyd.groupby("date").size().reindex(idx, fill_value=0).values})])
    save(58,
         metrics=[
             {"label": "기온 자료", "value": "아직 없음", "help": "NOAA 일별 최저기온 20°C 초과 = 열대야 표시"},
             {"label": "여름 정전 민원(6–8월)", "value": f"{len(out):,}건", "help": "ELECTRIC · POWER OUTAGE"},
             {"label": "여름 소화전 열림 민원", "value": f"{len(hyd):,}건", "help": "Hydrant Running 계열"},
         ],
         charts=[
             {"title": "여름 하루 정전·소화전 민원", "kind": "line", "x": "날짜", "y": "민원", "color": "구분",
              "colors": {"정전(주거, HPD)": "#e07b39", "소화전 열림(DEP)": "#2457a7"}, "rows": records(rows),
              "caption": "두 선이 함께 솟는 날이 폭염일 후보다. 기온을 붙이면 확인할 수 있다."},
         ])


def halves(df):
    dt = with_tract(df[["key", "created", "addr_n"]])
    dt["half"] = np.where(dt.created < "2026-05-01", "H1", "H2")
    r = dt.groupby(["GEOID", "half"]).size().unstack().fillna(0)
    r = r.join(tracts().set_index("GEOID").total_pop)
    r["r1"] = r.H1 / r.total_pop * 1000
    r["r2"] = r.H2 / r.total_pop * 1000
    return r


def q059(r):
    top = r.r1 >= r.r1.quantile(0.9)
    stay = (r[top].r2 >= r.r2.quantile(0.9)).mean() * 100
    pts = r.assign(**{"앞 6개월(11–4월) 1,000명당": r.r1.round(0), "뒤 6개월(5–10월) 1,000명당": r.r2.round(0)})
    cap = pts[["앞 6개월(11–4월) 1,000명당", "뒤 6개월(5–10월) 1,000명당"]].quantile(0.99).min()
    pts = pts[(pts["앞 6개월(11–4월) 1,000명당"] <= cap) & (pts["뒤 6개월(5–10월) 1,000명당"] <= cap)]
    save(59,
         metrics=[
             {"label": "앞 상위 10% 중 뒤에도 상위 10%", "value": f"{stay:.0f}%", "help": "우연이라면 10%"},
             {"label": "앞뒤 순위 상관", "value": f"{spearmanr(r.r1, r.r2)[0]:.2f}", "help": f"Tract {len(r):,}개"},
         ],
         charts=[
             {"title": "Tract마다 본 앞 6개월과 뒤 6개월 민원율", "kind": "scatter", "x": "앞 6개월(11–4월) 1,000명당",
              "y": "뒤 6개월(5–10월) 1,000명당", "trend": True,
              "rows": records(pts.reset_index()[["GEOID", "앞 6개월(11–4월) 1,000명당", "뒤 6개월(5–10월) 1,000명당"]]),
              "caption": "점들이 대각선 근처에 모여 있다. 계절이 바뀌어도 동네의 순위는 크게 바뀌지 않는다. 위쪽 1%는 그림에서만 뺐다."},
         ])


def q060(r):
    med1, med2 = r.r1.median(), r.r2.median()
    r = r.assign(dec=pd.qcut(r.r1.rank(method="first"), 10, labels=[f"D{i}" for i in range(1, 11)]))
    rows = []
    for d, g in r.groupby("dec", observed=True):
        rows.append({"앞 6개월 순위 10분위": str(d), "구분": "앞 6개월", "중앙값 대비(배)": round(g.r1.median() / med1, 2)})
        rows.append({"앞 6개월 순위 10분위": str(d), "구분": "뒤 6개월", "중앙값 대비(배)": round(g.r2.median() / med2, 2)})
    top = r.r1 >= r.r1.quantile(0.9)
    low = r.r1 <= r.r1.quantile(0.1)
    save(60,
         metrics=[
             {"label": "앞 상위 10%: 앞 6개월", "value": f"{r[top].r1.median() / med1:.2f}배", "help": "전체 중앙값 대비"},
             {"label": "같은 동네: 뒤 6개월", "value": f"{r[top].r2.median() / med2:.2f}배", "help": "아무 정책 없이 내려왔다"},
             {"label": "앞 하위 10%: 앞 → 뒤", "value": f"{r[low].r1.median() / med1:.2f} → {r[low].r2.median() / med2:.2f}배",
              "help": "아래쪽은 반대로 올라온다"},
         ],
         charts=[
             {"title": "앞 6개월 순위로 나눈 10개 집단의 앞·뒤 민원율", "kind": "line", "x": "앞 6개월 순위 10분위",
              "y": "중앙값 대비(배)", "color": "구분", "colors": {"앞 6개월": "#2457a7", "뒤 6개월": "#e07b39"},
              "rows": rows, "point": True,
              "caption": "주황 선(뒤)은 파랑 선(앞)보다 양 끝이 가운데로 당겨져 있다. 위는 내려오고 아래는 올라온다. 이것이 평균으로의 회귀다."},
         ],
         tables=[{"title": "10분위별 중앙값 대비", "rows": records(pd.DataFrame(rows).pivot(index="앞 6개월 순위 10분위", columns="구분", values="중앙값 대비(배)").reset_index())}])


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} or set(range(49, 61))
    df = load_311()
    r = halves(df) if want & {59, 60} else None
    jobs = {49: q049, 50: q050, 51: q051, 52: q052, 53: q053, 54: q054, 55: q055, 56: q056, 57: q057, 58: q058}
    for k in sorted(want):
        if k in jobs:
            jobs[k](df)
        elif k == 59:
            q059(r)
        elif k == 60:
            q060(r)
