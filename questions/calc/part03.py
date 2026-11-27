"""3부. AOC·선거·정치 지리 — 통계 계산.
문항 25–32. 실행: python questions/calc/part03.py  (일부만: python questions/calc/part03.py 27 30)
선거구 경계·개표·GTFS 같은 외부 자료는 아직 붙이지 않았다. [결합] 문항은 우리 데이터로 보이는 쪽만 계산한다.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BORO_KO, INC_Q, ROOT, borough_pop, category, load_311,  # noqa: E402
                    records, save, tracts, with_tract)

BOROS = list(BORO_KO)
AGENCY_KO = {"NYPD": "경찰(NYPD)", "HPD": "주택보존개발국(HPD)", "DSNY": "위생국(DSNY)", "DOT": "교통국(DOT)",
             "DEP": "환경보호국(DEP)", "DPR": "공원국(DPR)", "DOB": "건축국(DOB)", "DOHMH": "보건국(DOHMH)",
             "DHS": "노숙인서비스국(DHS)", "TLC": "택시리무진위원회(TLC)"}


def q025(dt):
    """NY-14 경계가 없어 대리 지표: 히스패닉 비율 최상위 5분위 Tract의 민원 구성 vs 시 전체."""
    d = dt  # with_tract가 hispanic_rate를 이미 붙인다
    tq = tracts()
    cut = tq.hispanic_rate.quantile(0.8)
    top = d[d.hispanic_rate >= cut]
    cats = ["주거환경", "소음", "도로·교통", "위생", "해충·동물", "건축·안전", "기타"]
    rows = []
    for lab, s in [("히스패닉 비율 최상위 20% Tract", top), ("시 전체(분석 Tract)", d)]:
        share = s.cat.value_counts(normalize=True).reindex(cats).fillna(0) * 100
        for c, v in share.items():
            rows.append({"분야": c, "구분": lab, "비중(%)": round(float(v), 1)})
    pop_top = tq[tq.hispanic_rate >= cut].total_pop.sum()
    r_top = len(top) / pop_top * 1000
    r_all = len(d) / tq.total_pop.sum() * 1000
    save(25,
         metrics=[
             {"label": "NY-14 경계", "value": "아직 없음", "help": "TIGER 119대 의회 선거구를 Tract에 겹쳐야 한다"},
             {"label": "대리: 히스패닉 최상위 20% Tract", "value": f"{r_top:,.0f}건", "help": f"1,000명당, 히스패닉 {cut * 100:.0f}% 이상"},
             {"label": "시 전체(분석 Tract)", "value": f"{r_all:,.0f}건", "help": "1,000명당"},
         ],
         charts=[
             {"title": "민원 구성: 히스패닉 비율 최상위 동네 vs 시 전체", "kind": "group", "x": "분야", "y": "비중(%)",
              "color": "구분", "colors": {"히스패닉 비율 최상위 20% Tract": "#2457a7", "시 전체(분석 Tract)": "#b9c4d4"},
              "rows": rows,
              "caption": ("NY-14 자체가 아니라, NY-14와 인구 구성이 비슷한 동네의 모습이다. "
                          "경계를 붙이면 이 자리에 실제 선거구가 들어간다.")},
         ])


def q026(df):
    nepm = df[df.problem == "Non-Emergency Police Matter"]
    w = nepm[(nepm.created >= "2026-09-01") & (nepm.created < "2026-11-01")]
    zips = {"10474": "헌츠포인트(10474)", "10463": "마블힐·킹스브리지(10463)"}
    z = w[w.zip.astype(str).str[:5].isin(list(zips))]
    daily = z.groupby([z.date, z.zip.astype(str).str[:5].map(zips)]).size().rename("민원").reset_index()
    daily.columns = ["날짜", "지역", "민원"]
    full = pd.MultiIndex.from_product([pd.date_range("2026-09-01", "2026-10-31"), list(zips.values())], names=["날짜", "지역"])
    daily = daily.set_index(["날짜", "지역"]).reindex(full, fill_value=0).reset_index()
    bx = w[w.borough == "BRONX"].groupby("date").size().rename_axis("날짜").reset_index(name="브롱크스 전체")
    save(26,
         metrics=[
             {"label": "비긴급 경찰 민원(12개월)", "value": f"{len(nepm):,}건", "help": "Non-Emergency Police Matter"},
             {"label": "두 우편번호, 9–10월", "value": f"{len(z):,}건", "help": "하루 1–2건 수준"},
             {"label": "사건 날짜", "value": "확인 필요", "help": "원문에 '2026-10'만 있다"},
         ],
         charts=[
             {"title": "두 동네의 하루 비긴급 경찰 민원(9–10월)", "kind": "line", "x": "날짜", "y": "민원", "color": "지역",
              "rows": records(daily), "caption": "하루 몇 건 수준이라 작은 우연에도 크게 출렁인다. 사건 하나의 효과를 읽기에는 수가 너무 적다."},
             {"title": "브롱크스 전체(9–10월)", "kind": "line", "x": "날짜", "y": "브롱크스 전체", "rows": records(bx)},
         ])


def q027(df):
    d = df[df.cd.notna()].copy()
    d["cd"] = pd.to_numeric(d.cd.astype(str), errors="coerce")
    d = d[d.cd.between(1, 51)]
    rows = []
    for k, g in d.groupby("cd"):
        top = g.problem.astype(str).value_counts()
        rows.append({"선거구": int(k), "자치구": BORO_KO.get(g.borough.astype(str).mode().iat[0], "?"), "민원": len(g),
                     "1위 유형": top.index[0], "1위 비중(%)": round(top.iat[0] / len(g) * 100, 1)})
    t = pd.DataFrame(rows).sort_values("민원", ascending=False)
    cnt = t["1위 유형"].value_counts().rename_axis("1위 유형").reset_index(name="선거구 수")
    t["선거구 이름"] = "CD " + t.선거구.astype(str).str.zfill(2)
    # 11번 문항의 이상치 주소가 어느 선거구를 1위로 만들었는지 확인
    hot = d[d.addr_n == "655 EAST 230 STREET"].groupby("cd").size()
    t["이상치 주소 제외"] = t.민원 - t.선거구.map(hot).fillna(0).astype(int)
    hot_cd = int(hot.idxmax())
    rank_ex = int((t["이상치 주소 제외"] > t.set_index("선거구").loc[hot_cd, "이상치 주소 제외"]).sum()) + 1
    save(27,
         metrics=[
             {"label": "선거구가 적힌 민원", "value": f"{len(d) / len(df) * 100:.1f}%", "help": f"{len(df) - len(d):,}건은 비어 있음"},
             {"label": "민원 최다 선거구", "value": f"CD {t.선거구.iat[0]:02d}",
              "help": f"{t.민원.iat[0]:,}건, {t.자치구.iat[0]}"},
             {"label": f"CD {hot_cd:02d}에서 한 주소의 몫", "value": f"{hot.max():,}건",
              "help": f"655 E 230th St(→ 11번). 빼면 {rank_ex}위"},
             {"label": "1위 유형이 불법주차인 선거구", "value": f"{(t['1위 유형'] == 'Illegal Parking').sum()}곳", "help": "51곳 중"},
         ],
         charts=[
             {"title": "선거구 51곳의 민원 1위 유형", "kind": "barh", "x": "선거구 수", "y": "1위 유형", "rows": records(cnt)},
             {"title": "선거구별 민원 건수", "kind": "barh", "x": "민원", "y": "선거구 이름",
              "rows": records(t[["선거구 이름", "민원", "자치구", "1위 유형"]]),
              "height": 1050,
              "caption": ("건수다. 선거구 인구가 비슷하게(약 17만 명) 짜여 있어 대략 비교할 수 있지만, "
                          "정확한 비교에는 선거구 인구가 필요하다.")},
         ],
         tables=[{"title": "선거구 성적표", "rows": records(t[["선거구", "자치구", "민원", "이상치 주소 제외", "1위 유형", "1위 비중(%)"]])}])


def q028(df):
    ag = df.agency.astype(str).value_counts()
    top = ag.head(10)
    rows = pd.DataFrame({"기관": [AGENCY_KO.get(a, a) for a in top.index], "민원": top.values,
                         "비중(%)": (top / len(df) * 100).round(1).values})
    rest = len(df) - top.sum()
    save(28,
         metrics=[
             {"label": "민원을 받은 시 기관", "value": f"{ag.size}곳"},
             {"label": "경찰(NYPD) 몫", "value": f"{ag['NYPD'] / len(df) * 100:.0f}%"},
             {"label": "연방 하원의원 몫", "value": "0%", "help": "311 민원은 모두 시 기관이 처리한다"},
         ],
         charts=[
             {"title": "민원을 처리하는 기관(상위 10곳)", "kind": "barh", "x": "민원", "y": "기관", "rows": records(rows),
              "caption": f"나머지 기관 합계 {rest:,}건. 모두 뉴욕시 기관이다. 시의원은 예산과 감독, 연방 의원은 연방 법과 예산을 다룬다."},
         ],
         tables=[{"title": "기관별 민원", "rows": records(rows)}])


def q029(df):
    ip = df[df.problem == "Illegal Parking"]
    det = ip.detail.astype(str).value_counts().head(12).rename_axis("세부 유형").reset_index(name="민원")
    bus = df[df.detail.astype(str).str.contains("Bus", case=False) & df.problem.astype(str).str.contains("Parking|Sign|Bus Stop")]
    b = bus.groupby(["problem", "detail"], observed=True).size().rename("민원").reset_index()
    b["유형"] = b.problem.astype(str) + " · " + b.detail.astype(str)
    b = b.sort_values("민원", ascending=False)[["유형", "민원"]]
    save(29,
         metrics=[
             {"label": "불법주차 민원", "value": f"{len(ip):,}건"},
             {"label": "버스 관련 세부 유형", "value": f"{int(b.민원.sum()):,}건", "help": "무단 버스 정차, 정류장 표지 등"},
             {"label": "'버스 전용차로 막음' 유형", "value": "없음",
              "help": "이 자료에는 전용차로 세부 유형이 없다. 전용차로 위반은 주로 카메라로 단속된다"},
         ],
         charts=[
             {"title": "불법주차 세부 유형 상위 12개", "kind": "barh", "x": "민원", "y": "세부 유형", "rows": records(det),
              "caption": "소화전·표지판 위반·보도 막음이 대부분이다. 버스와 직접 관련된 것은 '무단 버스 정차'뿐이다."},
             {"title": "버스와 관련된 311 유형", "kind": "barh", "x": "민원", "y": "유형", "rows": records(b)},
         ])


def q030(dt, df, bp):
    road = dt[dt.cat == "도로·교통"]
    pop = dt.drop_duplicates("GEOID").groupby("inc_q", observed=True).total_pop.sum()
    r = (road.groupby("inc_q", observed=True).size() / pop * 1000).reindex(INC_Q)
    rows = pd.DataFrame({"소득 5분위": INC_Q, "1,000명당 도로·교통 민원": r.round(1).values})
    ip = df[df.problem == "Illegal Parking"]
    bb = (ip.borough.value_counts().reindex(BOROS) / bp.reindex(BOROS) * 1000).round(1)
    brows = pd.DataFrame({"자치구": [BORO_KO[x] for x in BOROS], "1,000명당 불법주차": bb.values})
    save(30,
         metrics=[
             {"label": "불법주차(단일 유형 1위)", "value": f"{len(ip):,}건"},
             {"label": "도로·교통: 소득 최하위", "value": f"{r.iat[0]:.1f}건", "help": "1,000명당"},
             {"label": "도로·교통: 중간(Q3)", "value": f"{r.iat[2]:.1f}건", "help": "가장 많은 분위"},
         ],
         charts=[
             {"title": "소득 5분위별 도로·교통 민원", "kind": "bar", "x": "소득 5분위", "y": "1,000명당 도로·교통 민원",
              "rows": records(rows), "caption": "가운데가 가장 높은 '역U자'다. 차가 적은 저소득 동네와 차고가 있는 고소득 동네가 양 끝에 있다."},
             {"title": "자치구별 1,000명당 불법주차", "kind": "bar", "x": "자치구", "y": "1,000명당 불법주차", "rows": records(brows), "sort": "-y"},
         ],
         tables=[{"title": "소득 5분위", "rows": records(rows)}])


def q031(dt):
    ch = dt[dt.channel.notna() & (dt.channel.astype(str) != "UNKNOWN")]  # 경로 미상(약 8%)은 분모에서 뺀다(story_01과 같은 기준)
    mix = (ch.groupby(["inc_q", "channel"], observed=True).size() / ch.groupby("inc_q", observed=True).size() * 100)
    mix = mix.rename("비율(%)").reset_index()
    mix = mix[mix.channel.isin(["PHONE", "ONLINE", "MOBILE"])]
    mix["경로"] = mix.channel.map({"PHONE": "전화", "ONLINE": "온라인(웹)", "MOBILE": "모바일 앱"})
    mix["소득 5분위"] = mix.inc_q.astype(str)
    mix["비율(%)"] = mix["비율(%)"].round(1)
    pop = dt.drop_duplicates("GEOID").groupby("inc_q", observed=True).total_pop.sum()
    rate = (dt.groupby("inc_q", observed=True).size() / pop * 1000).reindex(INC_Q).round(0)
    ph = mix[mix.경로 == "전화"].set_index("소득 5분위")["비율(%)"]
    save(31,
         metrics=[
             {"label": "투표율 자료", "value": "아직 없음", "help": "선거구(ED)별 투표율을 Tract에 붙여야 한다"},
             {"label": "1,000명당 민원: 소득 최하위", "value": f"{rate.iat[0]:,.0f}건"},
             {"label": "1,000명당 민원: 소득 최상위", "value": f"{rate.iat[-1]:,.0f}건"},
             {"label": "전화 신고 비율", "value": f"{ph[INC_Q[0]]:.0f}% → {ph[INC_Q[-1]]:.0f}%", "help": "소득 최하위 → 최상위"},
         ],
         charts=[
             {"title": "소득 5분위별 신고 경로", "kind": "stackh", "x": "비율(%)", "y": "소득 5분위", "color": "경로",
              "colors": {"전화": "#e07b39", "온라인(웹)": "#2457a7", "모바일 앱": "#9fb3d1"},
              "rows": records(mix[["소득 5분위", "경로", "비율(%)"]]),
              "caption": "신고 '양'만이 아니라 '방식'도 동네마다 다르다. 저소득 동네일수록 전화 비율이 높다. 기타 경로(0.1% 안팎)는 뺐다."},
         ])


def q032():
    import geopandas as gpd
    g = gpd.read_file(ROOT / "data" / "processed" / "nyc_acs_2024_5yr.geojson").to_crs(2263)
    g["area"] = g.geometry.area
    g["boro"] = g.borough.map({"Bronx": "BRONX", "Brooklyn (Kings)": "BROOKLYN", "Manhattan (New York)": "MANHATTAN",
                               "Queens": "QUEENS", "Staten Island (Richmond)": "STATEN ISLAND"})
    b = g.groupby("boro").agg(area=("area", "sum"), pop=("total_pop", "sum")).reindex(BOROS)
    rows = []
    for x in BOROS:
        rows.append({"자치구": BORO_KO[x], "구분": "지도 면적 몫(%)", "비율(%)": round(b.area[x] / b.area.sum() * 100, 1)})
        rows.append({"자치구": BORO_KO[x], "구분": "인구 몫(%)", "비율(%)": round(b["pop"][x] / b["pop"].sum() * 100, 1)})
    g = g[g.total_pop > 0].sort_values("area", ascending=False)
    k = int(len(g) * 0.1)
    big_area = g.area.iloc[:k].sum() / g.area.sum() * 100
    big_pop = g.total_pop.iloc[:k].sum() / g.total_pop.sum() * 100
    save(32,
         metrics=[
             {"label": "가장 큰 Tract 10%의 지도 면적", "value": f"{big_area:.0f}%", "help": f"{k}개 Tract"},
             {"label": "그 Tract들의 인구", "value": f"{big_pop:.0f}%"},
             {"label": "스태튼아일랜드", "value": f"면적 {rows[8]['비율(%)']:.0f}% · 인구 {rows[9]['비율(%)']:.0f}%"},
         ],
         charts=[
             {"title": "지도에서 차지하는 넓이 vs 사는 사람", "kind": "group", "x": "자치구", "y": "비율(%)", "color": "구분",
              "colors": {"지도 면적 몫(%)": "#e07b39", "인구 몫(%)": "#2457a7"}, "rows": rows,
              "caption": "단계구분도(choropleth)에서는 주황 막대만큼 눈에 띈다. 실제 사람 수는 파랑 막대다. 면적은 물 위를 뺀 Tract 경계 기준."},
         ])


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} or set(range(25, 33))
    df = load_311() if want - {32} else None
    if want & {25, 30, 31}:
        dt = with_tract(df)
        dt["cat"] = category(dt.problem)
    jobs = {25: lambda: q025(dt), 26: lambda: q026(df), 27: lambda: q027(df), 28: lambda: q028(df),
            29: lambda: q029(df), 30: lambda: q030(dt, df, borough_pop()), 31: lambda: q031(dt), 32: q032}
    for k in sorted(want):
        jobs[k]()
