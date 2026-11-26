"""6부. 소음: 뉴욕의 진짜 사운드트랙 — 통계 계산.
문항 61–68. 실행: python questions/calc/part06.py  (일부만: python questions/calc/part06.py 63 68)
66번(SONYC 센서)·67번(2019–2020 비교)은 외부 자료가 필요해 311 쪽만 계산한다.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chisquare

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BORO_KO, INC_Q, ROOT, borough_pop, load_311, records, save, tracts, with_tract  # noqa: E402

BOROS = list(BORO_KO)
HOT = "655 EAST 230 STREET"
DETAIL_KO = {"Loud Music/Party": "큰 음악·파티", "Banging/Pounding": "쿵쿵 소리", "Loud Talking": "큰 말소리",
             "Car/Truck Music": "차량 음악", "Car/Truck Horn": "경적", "Noise: Construction Before/After Hours (NM1)": "허용 시간 밖 공사",
             "Other": "기타", "Engine Idling": "공회전", "Construction": "공사", "Loud Television": "큰 TV 소리",
             "Noise, Barking Dog (NR5)": "개 짖는 소리", "Noise: Alarms (NR3)": "경보기"}


def noise(df):
    return df[df.problem.astype(str).str.startswith("Noise")]


def q061(df):
    nz = noise(df)
    top = nz.detail.astype(str).value_counts().head(12)
    rows = pd.DataFrame({"세부 유형": [DETAIL_KO.get(k, k) for k in top.index], "민원": top.values,
                         "소음 중 %": (top / len(nz) * 100).round(1).values})
    save(61,
         metrics=[
             {"label": "1위 큰 음악·파티", "value": f"{top.iat[0]:,}건", "help": f"소음의 {top.iat[0] / len(nz) * 100:.0f}%"},
             {"label": "2위 쿵쿵 소리", "value": f"{top.iat[1]:,}건"},
             {"label": "3위 큰 말소리", "value": f"{top.iat[2]:,}건"},
             {"label": "상위 3개 몫", "value": f"{top.iloc[:3].sum() / len(nz) * 100:.0f}%", "help": f"소음 전체 {len(nz):,}건 중"},
         ],
         charts=[
             {"title": "소음 세부 유형 상위 12", "kind": "barh", "x": "민원", "y": "세부 유형", "rows": records(rows),
              "caption": "상위 세 가지는 모두 '이웃이 내는 소리'다. 공사·차량·경보기는 훨씬 적다."},
         ],
         tables=[{"title": "소음 세부 유형", "rows": records(rows)}])


ODD = [("개 짖는 소리", r"Barking"), ("헬리콥터", r"Helicopter"), ("아이스크림 트럭", r"Ice Cream"),
       ("경보기", r"Alarms"), ("공회전", r"Idling"), ("새·수탉", r"Rooster|Bird"), ("드론", r"Drone")]


def q062(df):
    df = noise(df)  # '공회전'처럼 대기질 민원에도 같은 단어가 있어 소음 유형으로 한정
    det, prob = df.detail.fillna("").astype(str), df.problem.astype(str)
    rows = []
    for lab, pat in ODD:
        s = df[det.str.contains(pat, case=False) | prob.str.contains(pat, case=False)]
        if len(s):
            rows.append({"소리": lab, "민원": len(s)})
    rows = pd.DataFrame(rows).sort_values("민원", ascending=False)
    ic = df[det.str.contains("Ice Cream", case=False)]
    ic_codes = ic.detail.astype(str).value_counts()
    hel = df[prob.str.contains("Helicopter", case=False)]
    save(62,
         metrics=[
             {"label": "개 짖는 소리", "value": f"{int(rows.set_index('소리').loc['개 짖는 소리', '민원']):,}건"},
             {"label": "헬리콥터", "value": f"{len(hel):,}건", "help": "별도 유형 'Noise - Helicopter'"},
             {"label": "아이스크림 트럭", "value": f"{len(ic):,}건",
              "help": " + ".join(f"{k} {v:,}" for k, v in ic_codes.items())},
         ],
         charts=[
             {"title": "뉴욕다운 소리들", "kind": "barh", "x": "민원", "y": "소리", "rows": records(rows),
              "caption": "세부 유형 이름에 그 단어가 들어간 민원을 셌다. 같은 소리가 두 코드로 나뉜 경우(아이스크림 트럭)도 합쳤다."},
         ],
         tables=[{"title": "아이스크림 트럭 세부 코드", "rows": [{"세부 코드": k, "민원": int(v)} for k, v in ic_codes.items()]}])


def q063(df):
    h = df[df.addr_n == HOT]
    m = h.groupby(h.created.dt.to_period("M").dt.start_time).size().rename_axis("월").reset_index(name="민원")
    nd = h[(h.created >= "2025-11-01") & (h.created < "2026-01-01")]
    days = nd.date.nunique()
    d = h.groupby("date").size().rename_axis("날짜").reset_index(name="민원")
    hr = h.created.dt.hour.value_counts().sort_index()
    hrows = pd.DataFrame({"시각": [f"{i:02d}시" for i in hr.index], "민원": hr.values})
    save(63,
         metrics=[
             {"label": "1년 민원", "value": f"{len(h):,}건", "help": f"그중 주거 소음 {(h.problem == 'Noise - Residential').sum():,}건"},
             {"label": "2025-11", "value": f"{int(m.민원.iat[0]):,}건"},
             {"label": "2025-12", "value": f"{int(m.민원.iat[1]):,}건"},
             {"label": "11–12월 하루 평균", "value": f"{len(nd) / 61:,.0f}건",
              "help": f"달력 61일 기준. 민원이 있던 {days}일만 보면 {len(nd) / days:,.0f}건, 최다 {d.민원.max():,}건"},
         ],
         charts=[
             {"title": "655 E 230th St의 하루 민원", "kind": "line", "x": "날짜", "y": "민원", "rows": records(d),
              "caption": "2025년 11월 초에 시작해 12월에 정점을 찍고 1월에 거의 끊긴다. 사람의 생활 리듬보다 '켜졌다 꺼진' 모양이다."},
             {"title": "시각별 민원", "kind": "bar", "x": "시각", "y": "민원", "rows": records(hrows),
              "caption": "보통 소음 민원은 밤 10시 ~ 자정에 몰리는데(→ 49번), 이 주소는 하루 내내 고르게 들어온다."},
         ])


def q064(df, bp):
    nz = noise(df)
    a = (nz.borough.value_counts().reindex(BOROS) / bp.reindex(BOROS) * 1000).round(1)
    b = (nz[nz.addr_n != HOT].borough.value_counts().reindex(BOROS) / bp.reindex(BOROS) * 1000).round(1)
    rows = []
    for x in BOROS:
        rows.append({"자치구": BORO_KO[x], "구분": "전체", "1,000명당 소음": float(a[x])})
        rows.append({"자치구": BORO_KO[x], "구분": "한 주소 제외", "1,000명당 소음": float(b[x])})
    rank_a = a.rank(ascending=False).astype(int)
    rank_b = b.rank(ascending=False).astype(int)
    save(64,
         metrics=[
             {"label": "브롱크스: 전체", "value": f"{a['BRONX']:.1f}건", "help": f"{rank_a['BRONX']}위"},
             {"label": "브롱크스: 한 주소 제외", "value": f"{b['BRONX']:.1f}건", "help": f"{rank_b['BRONX']}위"},
             {"label": "2위 맨해튼", "value": f"{a['MANHATTAN']:.1f}건"},
             {"label": "1위와 2위 격차", "value": f"{a['BRONX'] / a['MANHATTAN']:.2f} → {b['BRONX'] / b['MANHATTAN']:.2f}배"},
         ],
         charts=[
             {"title": "자치구별 1,000명당 소음 민원: 한 주소를 빼기 전과 후", "kind": "group", "x": "자치구", "y": "1,000명당 소음",
              "color": "구분", "colors": {"전체": "#9fb3d1", "한 주소 제외": "#2457a7"}, "rows": rows,
              "caption": "빼도 브롱크스가 1위지만, 맨해튼과의 격차는 1.42배에서 1.11배로 크게 줄어든다."},
         ])


def q065(df):
    k = df[df.addr_n != ""].assign(m=lambda x: x.created.dt.floor("min"))
    dup = k.duplicated(["addr_n", "problem", "m"])
    by = k[dup].problem.astype(str).value_counts().head(8)
    share = (k[dup].problem.astype(str).value_counts() / k.problem.astype(str).value_counts()).dropna()
    rows = pd.DataFrame({"유형": by.index, "같은 분 반복": by.values,
                         "그 유형 중 %": [round(float(share[p]) * 100, 1) for p in by.index]})
    hot = k[k.addr_n == HOT]
    hot_dup = hot.duplicated(["addr_n", "problem", "m"]).mean() * 100
    save(65,
         metrics=[
             {"label": "같은 주소·유형·분에 또 들어온 민원", "value": f"{dup.sum() / len(df) * 100:.1f}%", "help": f"{dup.sum():,}건"},
             {"label": "655 E 230th St에서", "value": f"{hot_dup:.0f}%", "help": "같은 분 반복 비율"},
             {"label": "신고자 ID", "value": "없음", "help": "공개 자료에는 신고자 정보가 없다"},
         ],
         charts=[
             {"title": "같은 분에 같은 주소·유형으로 또 들어온 민원(유형별)", "kind": "barh", "x": "같은 분 반복", "y": "유형",
              "rows": records(rows), "caption": "1분 안에 같은 주소에서 같은 유형이 또 들어오면 반복 신고로 추정했다. 여러 이웃의 동시 신고도 섞인다."},
         ],
         tables=[{"title": "유형별 같은 분 반복", "rows": records(rows)}])


def q066(df):
    import geopandas as gpd
    g = gpd.read_file(ROOT / "data" / "processed" / "nyc_acs_2024_5yr.geojson").to_crs(2263)
    g["km2"] = g.geometry.area * 0.09290304 / 1e6
    area = g.groupby("borough").km2.sum().rename(index={"Bronx": "BRONX", "Brooklyn (Kings)": "BROOKLYN",
                                                         "Manhattan (New York)": "MANHATTAN", "Queens": "QUEENS",
                                                         "Staten Island (Richmond)": "STATEN ISLAND"})
    nz = noise(df)
    n = nz.borough.value_counts().reindex(BOROS)
    rows = pd.DataFrame({"자치구": [BORO_KO[b] for b in BOROS], "㎢당 소음 민원": (n / area.reindex(BOROS)).round(0).values,
                         "1,000명당 소음 민원": (n / borough_pop().reindex(BOROS) * 1000).round(1).values})
    save(66,
         metrics=[
             {"label": "SONYC 센서 자료", "value": "아직 없음", "help": "NYU CUSP 공개 자료"},
             {"label": "맨해튼 ㎢당 소음", "value": f"{rows.set_index('자치구').loc['맨해튼', '㎢당 소음 민원']:,.0f}건"},
             {"label": "스태튼아일랜드 ㎢당", "value": f"{rows.set_index('자치구').loc['스태튼아일랜드', '㎢당 소음 민원']:,.0f}건"},
         ],
         charts=[
             {"title": "넓이로 나눈 소음 민원(센서와 같은 기준)", "kind": "bar", "x": "자치구", "y": "㎢당 소음 민원",
              "alt_y": "1,000명당 소음 민원", "rows": records(rows), "sort": "-y",
              "caption": "센서는 '사람 수'가 아니라 '자리'를 잰다. 넓이로 나누면 맨해튼이 압도적으로 1위가 된다. 세로축을 바꿔 사람 기준과 비교해 보자."},
         ])


def q067(df):
    nz = noise(df)
    dt = with_tract(nz[nz.addr_n != HOT][["key", "created"]])  # 이상치 주소가 소득 최하위 분위의 11–12월을 부풀린다
    pop = tracts().groupby("inc_q", observed=True).total_pop.sum()
    jul = dt[(dt.created >= "2026-07-01") & (dt.created < "2026-08-01")].groupby("inc_q", observed=True).size()
    mon = dt.groupby("inc_q", observed=True).size() / 12
    rows = pd.DataFrame({"소득 5분위": INC_Q, "7월 1,000명당": (jul / pop * 1000).reindex(INC_Q).round(1).values,
                         "월평균 1,000명당": (mon / pop * 1000).reindex(INC_Q).round(1).values})
    rows["7월 ÷ 월평균"] = (rows["7월 1,000명당"] / rows["월평균 1,000명당"]).round(2)
    save(67,
         metrics=[
             {"label": "2019–2020 자료", "value": "아직 없음", "help": "같은 원본에서 더 이른 기간을 뽑아야 한다"},
             {"label": "7월 ÷ 월평균: 소득 최하위", "value": f"{rows['7월 ÷ 월평균'].iat[0]:.2f}배"},
             {"label": "7월 ÷ 월평균: 소득 최상위", "value": f"{rows['7월 ÷ 월평균'].iat[-1]:.2f}배"},
         ],
         charts=[
             {"title": "2026년 7월 소음 민원: 1년 월평균 대비", "kind": "bar", "x": "소득 5분위", "y": "7월 ÷ 월평균",
              "alt_y": "7월 1,000명당", "rows": records(rows),
              "caption": "여름이 소음을 키우는 정도가 소득 분위마다 다른지 본다. 팬데믹(2020)과 비교하려면 2019–2020년 7월이 필요하다."},
         ],
         tables=[{"title": "소득 5분위별 7월 소음", "rows": records(rows)}])


def q068(df):
    nz = noise(df)
    h = nz.created.dt.hour
    night = h.isin([22, 23, 0, 1, 2, 3, 4, 5]).mean() * 100
    wk = (nz.created.dt.dayofweek >= 5).mean() * 100
    rows = [{"구분": "밤 10시 ~ 새벽 6시", "기준": "고르게 나눴다면(기대)", "비율(%)": round(8 / 24 * 100, 1)},
            {"구분": "밤 10시 ~ 새벽 6시", "기준": "실제(관측)", "비율(%)": round(night, 1)},
            {"구분": "토·일요일", "기준": "고르게 나눴다면(기대)", "비율(%)": round(2 / 7 * 100, 1)},
            {"구분": "토·일요일", "기준": "실제(관측)", "비율(%)": round(wk, 1)}]
    obs = h.value_counts().sort_index().values
    chi = chisquare(obs)
    save(68,
         metrics=[
             {"label": "밤 8시간: 기대 → 관측", "value": f"33% → {night:.0f}%"},
             {"label": "토·일: 기대 → 관측", "value": f"29% → {wk:.0f}%"},
             {"label": "시각 분포 카이제곱", "value": f"{chi.statistic:,.0f}", "help": "자유도 23. 고르게 나뉘었다는 가정과 크게 다르다"},
         ],
         charts=[
             {"title": "기대값 vs 관측값", "kind": "group", "x": "구분", "y": "비율(%)", "color": "기준",
              "colors": {"고르게 나눴다면(기대)": "#b9c4d4", "실제(관측)": "#2457a7"}, "rows": rows,
              "caption": "'시간·요일과 상관없이 고르게 들어온다'면 회색 막대만큼이어야 한다. 파랑 막대와의 차이가 '쏠림'이다."},
         ])


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} or set(range(61, 69))
    df = load_311()
    jobs = {61: q061, 62: q062, 63: q063, 65: q065, 66: q066, 67: q067, 68: q068}
    for k in sorted(want):
        if k == 64:
            q064(df, borough_pop())
        else:
            jobs[k](df)
