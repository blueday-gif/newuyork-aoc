"""10부. 두 데이터를 합치면 새 이야기가 나온다 — 통계 계산.
문항 95–100. 실행: python questions/calc/part10.py  (일부만: python questions/calc/part10.py 96 100)
모두 [결합] 문항이다. 95번(ACS)만 실제로 합쳤고, 나머지는 311 쪽에서 결합 준비가 된 부분을 계산한다.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BORO_KO, INC_Q, ROOT, category, load_311, records,  # noqa: E402
                    save, tracts, with_tract)

BOROS = list(BORO_KO)
FLOOD_PAT = r"Street Flooding|Flooding on Street|Catch Basin Clogged|Sewer Backup"
CATS = ["주거환경", "소음", "도로·교통", "위생", "해충·동물"]


def flood(df):
    p = df.problem.astype(str)
    return df[p.isin(["Sewer", "Sewer Maintenance"]) & df.detail.astype(str).str.contains(FLOOD_PAT, case=False)]


def q095(df, dt):
    pg = pd.read_parquet(ROOT / "data" / "processed" / "nyc311_point_geoid.parquet")
    t = tracts()
    rows = []
    pop = t.groupby("boro_acs").total_pop.sum()
    for c in CATS:
        r = dt[dt.cat == c].groupby("boro_acs").size() / pop * 1000
        for b in BOROS:
            rows.append({"자치구": BORO_KO[b], "분야": c, "1,000명당": round(float(r.get(b, 0)), 1)})
    save(95,
         metrics=[
             {"label": "좌표로 Tract를 찾은 민원", "value": f"{len(pg) / len(df) * 100:.1f}%", "help": f"{len(pg):,} / {len(df):,}건"},
             {"label": "분석 대상 Tract", "value": f"{len(t):,}개", "help": "인구 1,000명 이상"},
             {"label": "분석에 쓴 민원", "value": f"{len(dt):,}건", "help": "분석 대상 Tract 안의 민원"},
         ],
         charts=[
             {"title": "자치구 × 분야, 1,000명당 민원", "kind": "group", "x": "분야", "y": "1,000명당", "color": "자치구", "rows": rows,
              "caption": "'어떤 동네가 무엇을 신고하나'. 브롱크스는 주거·소음이, 퀸스·브루클린·스태튼아일랜드는 도로·교통이 두드러진다."},
         ])


WEATHER = {
    "눈·얼음": lambda p, d: p == "Snow or Ice",
    "난방·온수": lambda p, d: p == "HEAT/HOT WATER",
    "빗물받이 막힘·도로 침수": lambda p, d: (
        p.isin(["Sewer", "Sewer Maintenance"])
        & d.str.contains("Street Flooding|Flooding on Street|Catch Basin Clogged", case=False)
    ),
    "소화전 열림": lambda p, d: (
        p.isin(["Water System", "Water Maintenance"])
        & d.str.contains("Hydrant Running", case=False)
    ),
}


def q096(df):
    p, d = df.problem.astype(str), df.detail.astype(str)
    rows, peaks = [], []
    for lab, f in WEATHER.items():
        s = df[f(p, d)].groupby("date").size()
        idx = (s / s.max() * 100).round(1)
        rows += [{"날짜": k, "민원": lab, "최대 날=100": float(v)} for k, v in idx.items()]
        peaks.append({"민원": lab, "가장 많은 날": s.idxmax().strftime("%Y-%m-%d"), "그날 건수": int(s.max()),
                      "하루 중앙값": int(s.median()), "최대 ÷ 중앙값": round(float(s.max() / max(s.median(), 1)), 0)})
    save(96,
         metrics=[{"label": r["민원"], "value": f"{r['그날 건수']:,}건",
                   "help": f"{r['가장 많은 날']}, 하루 중앙값의 {r['최대 ÷ 중앙값']:.0f}배"} for r in peaks],
         charts=[
             {"title": "날씨에 반응하는 민원(각자 가장 많은 날 = 100)", "kind": "line", "x": "날짜", "y": "최대 날=100", "color": "민원",
              "colors": {"눈·얼음": "#2457a7", "난방·온수": "#8e5cc4", "빗물받이 막힘·도로 침수": "#3a9d6e", "소화전 열림": "#e07b39"},
              "rows": records(pd.DataFrame(rows)),
              "caption": "날씨 자료가 없어도 날씨의 흔적이 보인다. 뾰족한 날에 기온·강수량을 붙이면 '얼마나 추우면, 얼마나 비가 오면'을 잴 수 있다."},
         ],
         tables=[{"title": "가장 많은 날", "rows": peaks}])


def q097():
    import json
    d39 = json.loads((ROOT / "questions" / "data" / "q039.json").read_text(encoding="utf-8"))
    d37 = json.loads((ROOT / "questions" / "data" / "q037.json").read_text(encoding="utf-8"))
    rows = [{"소득 5분위": r["소득 5분위"], "점검에서 위반 발견(%)": r["점검에서 위반 발견(%)"]} for r in d39["tables"][0]["rows"]]
    save(97,
         metrics=[
             {"label": "HPD 위반·보건국 점검 자료", "value": "아직 없음", "help": "BBL·좌표로 붙일 수 있다"},
             {"label": "쥐: 점검에서 위반 발견(최하위→최상위)",
              "value": f"{rows[0]['점검에서 위반 발견(%)']:.0f}% → {rows[-1]['점검에서 위반 발견(%)']:.0f}%",
              "help": "39번, 311 결과문 대리 지표"},
             {"label": "난방: '위반 발부' 비율",
              "value": " · ".join(
                  f"{r[chr(39) + '위반' if False else '결과문 ' + chr(39) + '위반 발부' + chr(39) + ' 비율(%)']:.1f}"
                  for r in d37["tables"][0]["rows"][:1]
              ) + "% 안팎",
              "help": "37번. 히스패닉 비율 분위마다 거의 같다"},
         ],
         charts=[
             {"title": "311 안의 대리 지표: 쥐 신고가 점검에서 맞은 비율", "kind": "bar", "x": "소득 5분위", "y": "점검에서 위반 발견(%)",
              "rows": rows, "caption": "가난한 동네의 신고일수록 실제로 문제가 확인된다. 독립된 점검 자료를 붙이면 '과소신고 지도'를 그릴 수 있다."},
         ])


def q098(df):
    hpd = df[df.agency.astype(str) == "HPD"]
    s = hpd.bbl.astype(str).str.strip()
    hb = hpd[hpd.bbl.notna() & (s != "") & (s != "nan")]
    m = hpd.groupby(hpd.created.dt.to_period("M").dt.start_time).size().rename_axis("월").reset_index(name="HPD 주거 민원")
    save(98,
         metrics=[
             {"label": "RGB 안정화 건물 목록", "value": "아직 없음", "help": "BBL로 바로 붙는다"},
             {"label": "HPD 민원 중 BBL 있음", "value": f"{len(hb) / len(hpd) * 100:.1f}%"},
             {"label": "HPD 민원이 있는 건물", "value": f"{hb.bbl.astype(str).nunique():,}동"},
             {"label": "동결 뒤 자료", "value": "1개월", "help": "2026-10. 한 시즌은 2027년 봄"},
         ],
         charts=[
             {"title": "동결 전 기준선: 월별 HPD 주거 민원", "kind": "bar", "x": "월", "y": "HPD 주거 민원", "rows": records(m),
              "caption": "이 기준선을 '안정화 건물'과 '그 밖의 건물' 두 줄로 나누는 것이 첫 단계다(→ 15번)."},
         ])


def q099(dt, t):
    pop = t.groupby("ren_q", observed=True).total_pop.sum()
    r = (dt.groupby("ren_q", observed=True).size() / pop * 1000).reindex(["Q1(최저)", "Q2", "Q3", "Q4", "Q5(최고)"])
    rows = pd.DataFrame({"임차율 5분위": r.index.astype(str), "1,000명당 민원": r.round(0).values})
    save(99,
         metrics=[
             {"label": "선거구(ED) 개표 결과", "value": "아직 없음", "help": "면적·인구 비율로 Tract에 보간"},
             {"label": "311의 선거 관련 열", "value": "시의회 선거구", "help": "27번에서 이미 사용. 투표구(ED)는 없다"},
             {"label": "통제할 변수", "value": "임차율", "help": "민원과 표 모두와 엮인다(→ 17번)"},
         ],
         charts=[
             {"title": "선거 결과를 붙이기 전에: 임차율과 민원", "kind": "bar", "x": "임차율 5분위", "y": "1,000명당 민원", "rows": records(rows),
              "caption": "맘다니 득표도 임차율을 따라간다. 표와 민원의 관계는 임차율 분위 '안에서' 봐야 한다."},
         ])


def q100(df, dt, t):
    fl = flood(df)
    fdt = flood(dt)
    per_tract = fdt.groupby("GEOID").size().reindex(t.GEOID).fillna(0)
    zero = (per_tract == 0)
    zpop = t.set_index("GEOID").total_pop[zero.values].sum()
    by_inc = t.assign(n=per_tract.values).groupby("inc_q", observed=True).apply(lambda g: (g.n == 0).mean() * 100).reindex(INC_Q)
    rows = pd.DataFrame({"소득 5분위": INC_Q, "홍수 민원 0건인 Tract(%)": by_inc.round(1).values})
    d = fl.groupby("date").size().rename_axis("날짜").reset_index(name="홍수 관련 민원")
    top = d.sort_values("홍수 관련 민원", ascending=False).head(5)
    save(100,
         metrics=[
             {"label": "홍수 관련 민원(12개월)", "value": f"{len(fl):,}건", "help": "도로 침수, 빗물받이 막힘, 하수 역류(옛·새 이름 모두)"},
             {"label": "1년 내내 0건인 Tract", "value": f"{zero.mean() * 100:.0f}%", "help": f"{int(zero.sum()):,}개, 주민 {zpop / 1e6:.1f}백만 명"},
             {"label": "가장 많은 날", "value": top.날짜.iat[0].strftime("%Y-%m-%d"), "help": f"{int(top['홍수 관련 민원'].iat[0]):,}건"},
             {"label": "FloodNet·FEMA 자료", "value": "아직 없음", "help": "센서 수위와 홍수 위험 지도"},
         ],
         charts=[
             {"title": "하루 홍수 관련 민원", "kind": "line", "x": "날짜", "y": "홍수 관련 민원", "rows": records(d),
              "caption": "폭우가 온 날 솟는다. 7월 말 유형 이름이 바뀐 뒤에도 끊기지 않도록 옛·새 이름을 함께 셌다(→ 94번)."},
             {"title": "1년 내내 홍수 민원이 0건인 Tract 비율(소득 5분위)", "kind": "bar", "x": "소득 5분위", "y": "홍수 민원 0건인 Tract(%)",
              "rows": records(rows),
              "caption": ("0건이 '물이 차지 않는다'는 뜻인지 '신고하지 않는다'는 뜻인지는 "
                          "센서와 위험 지도를 붙여야 가릴 수 있다.")},
         ],
         tables=[{"title": "홍수 관련 민원이 가장 많은 날", "rows": records(top)}])


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} or set(range(95, 101))
    df = load_311()
    dt = with_tract(df) if want & {95, 99, 100} else None
    if dt is not None:
        dt["cat"] = category(dt.problem)
    t = tracts()
    jobs = {95: lambda: q095(df, dt), 96: lambda: q096(df), 97: q097, 98: lambda: q098(df), 99: lambda: q099(dt, t),
            100: lambda: q100(df, dt, t)}
    for k in sorted(want):
        jobs[k]()
